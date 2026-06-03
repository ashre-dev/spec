"""
Tool implementations for the ASHRE buying agent.

Each function makes HTTP calls to a vendor server. An optional `http_client`
parameter lets tests inject a transport that routes requests to the FastAPI app
directly (httpx.ASGITransport) without needing a running server.
"""

import json
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
            "The tool handles the payment internally — in production it uses Stripe; "
            "in dev/test it uses a mock payment. "
            "Pass amount from the 402 accepts[0] fields."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_url": {"type": "string", "description": "Base URL of the vendor server"},
                "amount": {
                    "type": "string",
                    "description": "Amount to pay, from the 402 price_per_query field",
                },
                "payer_id": {
                    "type": "string",
                    "description": "Agent or buyer identifier",
                },
            },
            "required": ["vendor_url", "amount", "payer_id"],
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
                "payer_id": {"type": "string", "description": "Agent or buyer identifier"},
                "token": {"type": "string", "description": "Bearer token from pay_vendor"},
            },
            "required": [
                "vendor_url",
                "product_id",
                "quantity",
                "shipping_address",
                "payer_id",
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
    amount: str,
    payer_id: str,
    http_client: httpx.Client | None = None,
) -> dict:
    """
    Pay the vendor and return a session token.
    Currently uses mock payments. Production: will use Stripe.
    """
    payment_id = f"pay-{uuid.uuid4().hex[:16]}"

    client = http_client or httpx.Client()
    resp = client.post(
        f"{vendor_url}/pay",
        json={"payment_id": payment_id, "amount": amount, "payer_id": payer_id},
    )
    resp.raise_for_status()
    return resp.json()


def buy_product(
    vendor_url: str,
    product_id: str,
    quantity: int,
    shipping_address: str,
    payer_id: str,
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
            "payer_id": payer_id,
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
                inputs["amount"],
                inputs["payer_id"],
                http_client,
            )
        elif name == "buy_product":
            result = buy_product(
                inputs["vendor_url"],
                inputs["product_id"],
                inputs["quantity"],
                inputs["shipping_address"],
                inputs["payer_id"],
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
