"""
Tool implementations for the ASHRE buying agent.

Each function makes HTTP calls to a vendor server. An optional `http_client`
parameter lets tests inject a transport that routes requests to the FastAPI app
directly (httpx.ASGITransport) without needing a running server.
"""

import json
import os
import uuid
import httpx


# Tool definitions passed to the Claude Messages API
TOOL_SCHEMAS = [
    {
        "name": "get_catalog",
        "description": (
            "Fetch the vendor's product catalog. "
            "Returns the catalog if you have a valid Bearer token. "
            "Returns HTTP 402 with payment requirements if no token or token expired — "
            "in that case, call pay_vendor first, then retry with the token."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_url": {
                    "type": "string",
                    "description": "Base URL of the vendor server, e.g. http://localhost:8000",
                },
                "token": {
                    "type": "string",
                    "description": "Bearer token obtained from pay_vendor. Omit on first call.",
                },
            },
            "required": ["vendor_url"],
        },
    },
    {
        "name": "pay_vendor",
        "description": (
            "Pay the vendor to unlock the catalog. Call this after get_catalog returns a 402. "
            "The tool handles the transaction internally — in production it sends real USDC on "
            "Base Sepolia; in dev/test it uses a mock tx. "
            "Pass recipient_address and amount from the 402 accepts[0] fields."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_url": {"type": "string", "description": "Base URL of the vendor server"},
                "recipient_address": {
                    "type": "string",
                    "description": "Vendor wallet address from the 402 challenge (accepts[0].address)",
                },
                "amount": {
                    "type": "string",
                    "description": "USDC amount to pay, from the 402 price_per_query field",
                },
                "payer_address": {
                    "type": "string",
                    "description": "Agent wallet address",
                },
            },
            "required": ["vendor_url", "recipient_address", "amount", "payer_address"],
        },
    },
    {
        "name": "buy_product",
        "description": (
            "Purchase a product from the vendor. "
            "Requires a valid Bearer token from pay_vendor. "
            "Returns an order confirmation with order_id and status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_url": {"type": "string"},
                "product_id": {
                    "type": "string",
                    "description": "Product ID from the catalog, e.g. hms-tee-001",
                },
                "quantity": {"type": "integer", "description": "Number of units to purchase"},
                "shipping_address": {
                    "type": "string",
                    "description": "Full shipping address",
                },
                "payer_address": {"type": "string", "description": "Agent wallet address"},
                "token": {"type": "string", "description": "Bearer token from pay_vendor"},
            },
            "required": [
                "vendor_url",
                "product_id",
                "quantity",
                "shipping_address",
                "payer_address",
                "token",
            ],
        },
    },
]


def get_catalog(
    vendor_url: str,
    token: str | None = None,
    http_client: httpx.Client | None = None,
) -> dict:
    client = http_client or httpx.Client()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = client.get(f"{vendor_url}/catalog", headers=headers)
    if resp.status_code == 402:
        return {"status": 402, "payment_required": resp.json()}
    resp.raise_for_status()
    return {"status": 200, "catalog": resp.json()}


def pay_vendor(
    vendor_url: str,
    recipient_address: str,
    amount: str,
    payer_address: str,
    http_client: httpx.Client | None = None,
) -> dict:
    """
    Pay the vendor and return a session token.

    Real mode (SEPOLIA_RPC_URL + AGENT_PRIVATE_KEY both set):
      signs and broadcasts a USDC transfer, submits the real tx_hash.
    Mock mode (default):
      generates a deterministic mock tx_hash — no blockchain interaction.
    """
    rpc_url = os.getenv("SEPOLIA_RPC_URL")
    private_key = os.getenv("AGENT_PRIVATE_KEY")

    if rpc_url and private_key:
        from .wallet import send_usdc
        tx_hash = send_usdc(recipient_address, amount, private_key, rpc_url)
    else:
        tx_hash = f"0xmocktx-{uuid.uuid4().hex[:16]}"

    client = http_client or httpx.Client()
    resp = client.post(
        f"{vendor_url}/pay",
        json={"tx_hash": tx_hash, "amount": amount, "payer_address": payer_address},
    )
    resp.raise_for_status()
    return resp.json()


def buy_product(
    vendor_url: str,
    product_id: str,
    quantity: int,
    shipping_address: str,
    payer_address: str,
    token: str,
    http_client: httpx.Client | None = None,
) -> dict:
    client = http_client or httpx.Client()
    resp = client.post(
        f"{vendor_url}/buy",
        json={
            "product_id": product_id,
            "quantity": quantity,
            "shipping_address": shipping_address,
            "payer_address": payer_address,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def dispatch_tool(name: str, inputs: dict, http_client: httpx.Client) -> str:
    """Route a tool_use block from Claude to the correct function."""
    try:
        if name == "get_catalog":
            result = get_catalog(inputs["vendor_url"], inputs.get("token"), http_client)
        elif name == "pay_vendor":
            result = pay_vendor(
                inputs["vendor_url"],
                inputs["recipient_address"],
                inputs["amount"],
                inputs["payer_address"],
                http_client,
            )
        elif name == "buy_product":
            result = buy_product(
                inputs["vendor_url"],
                inputs["product_id"],
                inputs["quantity"],
                inputs["shipping_address"],
                inputs["payer_address"],
                inputs["token"],
                http_client,
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
    except httpx.HTTPStatusError as e:
        result = {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        result = {"error": str(e)}

    return json.dumps(result)
