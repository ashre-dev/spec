"""
Tests for the buying agent.

Tool-level tests use httpx.ASGITransport to route HTTP calls directly through
the FastAPI app — no running server needed.

Agent-loop tests mock the Anthropic client to simulate the full
tool-use conversation without network calls to Claude.
"""

import json
import pytest
import httpx
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.vendor_server.main import app
from src.agent.tools import get_catalog, pay_vendor, buy_product, dispatch_tool
from src.agent.agent import run_agent


# ---------------------------------------------------------------------------
# Sync transport: routes httpx calls through Starlette's TestClient.
# ASGITransport is async-only; this bridges sync tool functions to the app.
# ---------------------------------------------------------------------------

class _StarletteTransport(httpx.BaseTransport):
    def __init__(self, starlette_app):
        self._tc = TestClient(starlette_app, raise_server_exceptions=False)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        method = request.method.lower()
        fn = getattr(self._tc, method)
        body = request.read()
        kwargs: dict = {"headers": dict(request.headers)}
        if method not in ("get", "head", "options") and body:
            kwargs["content"] = body
        resp = fn(str(request.url), **kwargs)
        return httpx.Response(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            content=resp.content,
        )


@pytest.fixture
def vendor_client() -> httpx.Client:
    return httpx.Client(
        transport=_StarletteTransport(app),
        base_url="http://testserver",
    )


HELSINKI_WALLET = "0xABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"


@pytest.fixture
def auth_token(vendor_client) -> str:
    """Pay the vendor and return a fresh session token."""
    result = pay_vendor(
        "http://testserver",
        recipient_address=HELSINKI_WALLET,
        amount="0.05",
        payer_address="0xAgent",
        http_client=vendor_client,
    )
    return result["token"]


# ---------------------------------------------------------------------------
# Tool: get_catalog
# ---------------------------------------------------------------------------

def test_get_catalog_without_token_returns_402(vendor_client):
    result = get_catalog("http://testserver", http_client=vendor_client)
    assert result["status"] == 402
    pr = result["payment_required"]
    assert pr["x402_version"] == 1
    assert pr["accepts"][0]["currency"] == "USDC"


def test_get_catalog_with_valid_token_returns_catalog(vendor_client, auth_token):
    result = get_catalog("http://testserver", token=auth_token, http_client=vendor_client)
    assert result["status"] == 200
    catalog = result["catalog"]
    assert catalog["vendor_id"] == "helsinki-maker-store"
    assert len(catalog["products"]) > 0


# ---------------------------------------------------------------------------
# Tool: pay_vendor
# ---------------------------------------------------------------------------

def test_pay_vendor_success(vendor_client):
    result = pay_vendor(
        "http://testserver",
        recipient_address=HELSINKI_WALLET,
        amount="0.05",
        payer_address="0xSomeAgent",
        http_client=vendor_client,
    )
    assert "token" in result
    assert result["expires_in"] == 3600


def test_pay_vendor_insufficient_amount_raises(vendor_client):
    with pytest.raises(httpx.HTTPStatusError):
        pay_vendor(
            "http://testserver",
            recipient_address=HELSINKI_WALLET,
            amount="0.01",  # too low
            payer_address="0xAgent",
            http_client=vendor_client,
        )


# ---------------------------------------------------------------------------
# Tool: buy_product
# ---------------------------------------------------------------------------

def test_buy_product_success(vendor_client, auth_token):
    result = buy_product(
        "http://testserver",
        product_id="hms-tee-001",
        quantity=1,
        shipping_address="Mannerheimintie 1, Helsinki",
        payer_address="0xAgent",
        token=auth_token,
        http_client=vendor_client,
    )
    assert result["status"] == "confirmed"
    assert result["product_id"] == "hms-tee-001"
    assert "order_id" in result


def test_buy_product_out_of_stock_raises(vendor_client, auth_token):
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        buy_product(
            "http://testserver",
            product_id="hms-mug-001",  # in_stock=False
            quantity=1,
            shipping_address="somewhere",
            payer_address="0xAgent",
            token=auth_token,
            http_client=vendor_client,
        )
    assert exc_info.value.response.status_code == 409


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def test_dispatch_tool_unknown_returns_error(vendor_client):
    result = json.loads(dispatch_tool("nonexistent_tool", {}, vendor_client))
    assert "error" in result


def test_dispatch_get_catalog_no_token(vendor_client):
    result = json.loads(
        dispatch_tool("get_catalog", {"vendor_url": "http://testserver"}, vendor_client)
    )
    assert result["status"] == 402


# ---------------------------------------------------------------------------
# Agent loop (mocked Anthropic client)
# ---------------------------------------------------------------------------

def _make_tool_use_block(tool_id: str, name: str, inputs: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = inputs
    return block


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_response(stop_reason: str, content: list):
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content
    return resp


def test_agent_full_flow(vendor_client):
    """
    Simulate Claude driving the full 402 → pay → catalog → buy flow.
    The mock returns tool_use blocks in sequence; the agent executes them
    against the real vendor server via ASGI transport.
    """
    # We'll capture tokens issued during the flow using a closure
    issued_tokens: list[str] = []

    def mock_create(**kwargs):
        messages = kwargs["messages"]

        # Turn 1: no tool results yet → Claude asks to get_catalog (no token)
        if len(messages) == 1:
            return _make_response("tool_use", [
                _make_tool_use_block("tu1", "get_catalog", {"vendor_url": "http://testserver"})
            ])

        # Turn 2: tool result is the 402 → Claude pays
        if len(messages) == 3:
            # Extract price and recipient from the tool result
            tr_content = json.loads(messages[2]["content"][0]["content"])
            accepts = tr_content["payment_required"]["accepts"][0]
            amount = accepts["price_per_query"]
            recipient = accepts["address"]
            return _make_response("tool_use", [
                _make_tool_use_block("tu2", "pay_vendor", {
                    "vendor_url": "http://testserver",
                    "recipient_address": recipient,
                    "amount": amount,
                    "payer_address": "0xAgentWallet",
                })
            ])

        # Turn 3: tool result has the token → Claude gets catalog
        if len(messages) == 5:
            token = json.loads(messages[4]["content"][0]["content"])["token"]
            issued_tokens.append(token)
            return _make_response("tool_use", [
                _make_tool_use_block("tu3", "get_catalog", {
                    "vendor_url": "http://testserver",
                    "token": token,
                })
            ])

        # Turn 4: Claude has catalog → buys a product
        if len(messages) == 7:
            token = issued_tokens[0]
            return _make_response("tool_use", [
                _make_tool_use_block("tu4", "buy_product", {
                    "vendor_url": "http://testserver",
                    "product_id": "hms-tee-001",
                    "quantity": 1,
                    "shipping_address": "123 Agent Street, Helsinki, FI",
                    "payer_address": "0xAgentWallet",
                    "token": token,
                })
            ])

        # Turn 5: purchase confirmed → Claude summarises
        return _make_response("end_turn", [
            _make_text_block("Purchased Helsinki Maker Tee × 1 for 18.00 USDC. Order confirmed.")
        ])

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = mock_create

    result = run_agent(
        shopping_request="I want a t-shirt",
        vendor_url="http://testserver",
        http_client=vendor_client,
        anthropic_client=mock_anthropic,
    )

    assert "confirmed" in result.lower() or "purchased" in result.lower()
    assert mock_anthropic.messages.create.call_count == 5
