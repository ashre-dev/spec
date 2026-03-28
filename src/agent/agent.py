"""
ASHRE Buying Agent

Uses Claude Opus 4.6 with tool use to:
  1. Query a vendor catalog (handles HTTP 402 automatically)
  2. Pay via mock x402
  3. Reason over the catalog and pick the best matching product
  4. Execute the purchase
"""

import anthropic
import httpx

from .tools import TOOL_SCHEMAS, dispatch_tool

AGENT_WALLET = "0xAgentWallet0000000000000000000000000000"

SYSTEM_PROMPT = f"""\
You are an autonomous AI shopping agent operating on the ASHRE protocol.

## Your job
Given a shopping request and a vendor URL, complete the full purchase workflow:

1. **get_catalog** — fetch the catalog (no token on first call)
2. If you receive a 402 response, **pay_vendor** using:
   - recipient_address: the `address` from the 402 `accepts[0]` field
   - amount: the `price_per_query` from the 402 `accepts[0]` field
   - payer_address: "{AGENT_WALLET}"
   (The tool handles the USDC transaction internally — do not generate tx_hash)
3. **get_catalog** again — now pass the token from pay_vendor
4. Browse the catalog, pick the product that best matches the request
   - Prefer in-stock items
   - Match category, name, and description to the user's intent
5. **buy_product** — complete the purchase:
   - Use the token from step 2
   - payer_address: "{AGENT_WALLET}"
   - shipping_address: use "123 Agent Street, Helsinki, FI" unless the user specified one

## Output
After completing the purchase, summarise what you bought, the order ID, quantity,
total cost in USDC, and estimated delivery. Be concise.
"""


def run_agent(
    shopping_request: str,
    vendor_url: str,
    http_client: httpx.Client | None = None,
    anthropic_client: anthropic.Anthropic | None = None,
) -> str:
    """
    Run the buying agent for a given shopping request.

    Args:
        shopping_request: Natural-language description of what the user wants.
        vendor_url: Base URL of the vendor server.
        http_client: Optional httpx.Client (inject for testing via ASGITransport).
        anthropic_client: Optional Anthropic client (inject for testing).

    Returns:
        The agent's final response text.
    """
    claude = anthropic_client or anthropic.Anthropic()
    _http = http_client or httpx.Client()

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Vendor URL: {vendor_url}\n\n"
                f"Shopping request: {shopping_request}"
            ),
        }
    ]

    while True:
        response = claude.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return next(
                (b.text for b in response.content if b.type == "text"), ""
            )

        if response.stop_reason != "tool_use":
            return f"[agent stopped: {response.stop_reason}]"

        # Append assistant turn (contains tool_use blocks)
        messages.append({"role": "assistant", "content": response.content})

        # Execute all requested tools, collect results
        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": dispatch_tool(block.name, block.input, _http),
            }
            for block in response.content
            if block.type == "tool_use"
        ]

        messages.append({"role": "user", "content": tool_results})
