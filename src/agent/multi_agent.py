"""
ASHRE Multi-Vendor Buying Agent

Queries multiple vendor servers in parallel using asyncio + httpx.AsyncClient.
Each vendor's 402 → pay → catalog flow runs concurrently.
Claude then reasons over all combined catalogs to pick the best product and
executes the purchase on the winning vendor.
"""

import asyncio
import json
import anthropic
import httpx

AGENT_WALLET = "0xAgentWallet0000000000000000000000000000"

SYSTEM_PROMPT = f"""\
You are an AI shopping agent operating on the ASHRE protocol.

You will receive a shopping request and the combined catalogs from multiple vendors.
Each catalog entry includes the vendor URL and all available products with prices.

Your task:
1. Identify the best matching product across all vendors.
   - Prefer in-stock items
   - Match category, name, and description to the user's intent
   - Consider price — cheaper is better when quality is similar
2. State clearly which vendor and product you chose, and why.
3. Return a JSON object (and nothing else) in this exact shape:

{{
  "vendor_url": "<url>",
  "product_id": "<id>",
  "quantity": 1,
  "reasoning": "<one sentence explaining the choice>"
}}
"""


async def _fetch_vendor_catalog(
    vendor_url: str,
    http: httpx.AsyncClient,
) -> dict:
    """
    Full 402 → pay → catalog flow for one vendor.
    Returns a dict with vendor_url, token, and catalog (or error).
    """
    # Step 1: probe catalog — expect 402
    resp = await http.get(f"{vendor_url}/catalog")

    if resp.status_code == 402:
        challenge = resp.json()
        amount = challenge["accepts"][0]["price_per_query"]

        # Step 2: pay
        pay_resp = await http.post(
            f"{vendor_url}/pay",
            json={
                "tx_hash": f"0xmocktx-{vendor_url[-4:]}",
                "amount": amount,
                "payer_address": AGENT_WALLET,
            },
        )
        pay_resp.raise_for_status()
        token = pay_resp.json()["token"]

        # Step 3: fetch catalog with token
        catalog_resp = await http.get(
            f"{vendor_url}/catalog",
            headers={"Authorization": f"Bearer {token}"},
        )
        catalog_resp.raise_for_status()
        return {
            "vendor_url": vendor_url,
            "token": token,
            "catalog": catalog_resp.json(),
        }

    resp.raise_for_status()
    return {"vendor_url": vendor_url, "token": None, "catalog": resp.json()}


async def _buy_from_vendor(
    vendor_url: str,
    token: str,
    product_id: str,
    quantity: int,
    shipping_address: str,
    http: httpx.AsyncClient,
) -> dict:
    resp = await http.post(
        f"{vendor_url}/buy",
        json={
            "product_id": product_id,
            "quantity": quantity,
            "shipping_address": shipping_address,
            "payer_address": AGENT_WALLET,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


async def run_multi_agent(
    shopping_request: str,
    vendor_urls: list[str],
    shipping_address: str = "123 Agent Street, Helsinki, FI",
    http_client: httpx.AsyncClient | None = None,
    anthropic_client: anthropic.Anthropic | None = None,
) -> dict:
    """
    Query all vendors in parallel, have Claude pick the best product, execute purchase.

    Returns a dict with keys: vendor_url, product_id, order, reasoning, catalogs_queried.
    """
    claude = anthropic_client or anthropic.Anthropic()

    async def _run(http: httpx.AsyncClient) -> dict:
        # --- Phase 1: parallel catalog fetch ---
        tasks = [_fetch_vendor_catalog(url, http) for url in vendor_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        vendor_data: list[dict] = []
        for url, result in zip(vendor_urls, results):
            if isinstance(result, Exception):
                print(f"[multi-agent] skipping {url}: {result}")
            else:
                vendor_data.append(result)

        if not vendor_data:
            raise RuntimeError("All vendor queries failed")

        # --- Phase 2: Claude picks the best product ---
        catalogs_summary = json.dumps(
            [
                {
                    "vendor_url": vd["vendor_url"],
                    "vendor_id": vd["catalog"]["vendor_id"],
                    "vendor_name": vd["catalog"]["vendor_name"],
                    "products": vd["catalog"]["products"],
                }
                for vd in vendor_data
            ],
            indent=2,
        )

        response = claude.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Shopping request: {shopping_request}\n\n"
                        f"Available catalogs:\n{catalogs_summary}"
                    ),
                }
            ],
        )

        raw = next(b.text for b in response.content if b.type == "text")
        # Strip markdown fences if Claude wraps in ```json ... ```
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        pick = json.loads(raw)

        # --- Phase 3: execute purchase ---
        chosen_vendor = next(
            vd for vd in vendor_data if vd["vendor_url"] == pick["vendor_url"]
        )
        order = await _buy_from_vendor(
            vendor_url=pick["vendor_url"],
            token=chosen_vendor["token"],
            product_id=pick["product_id"],
            quantity=pick.get("quantity", 1),
            shipping_address=shipping_address,
            http=http,
        )

        return {
            "vendor_url": pick["vendor_url"],
            "product_id": pick["product_id"],
            "reasoning": pick.get("reasoning", ""),
            "order": order,
            "catalogs_queried": len(vendor_data),
        }

    if http_client is not None:
        return await _run(http_client)

    async with httpx.AsyncClient() as http:
        return await _run(http)
