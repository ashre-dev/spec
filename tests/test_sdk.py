"""
SDK smoke tests.

These tests verify that the public SDK interfaces work correctly end-to-end
without a running server, using the same in-process transport tricks as the
other test files.
"""

from __future__ import annotations

import json
import pytest
import httpx
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.vendor_server.main import create_vendor_app
from src.registry.main import create_registry_app
from src.registry.store import VendorStore

from sdk.vendor import VendorApp, Product
from sdk.agent import AshreAgent, RegistryClient, VendorInfo, ShopResult, MultiShopResult


# ---------------------------------------------------------------------------
# Shared transports
# ---------------------------------------------------------------------------


class _SyncTransport(httpx.BaseTransport):
    """Bridges sync httpx calls to a Starlette TestClient."""

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


# ---------------------------------------------------------------------------
# VendorApp SDK tests
# ---------------------------------------------------------------------------


class TestVendorAppSDK:
    def test_products_returns_list(self):
        va = VendorApp("helsinki-maker-store")
        products = va.products
        assert len(products) > 0
        assert all(isinstance(p, Product) for p in products)

    def test_product_fields(self):
        va = VendorApp("helsinki-maker-store")
        p = va.products[0]
        assert p.id
        assert p.name
        assert p.price_usdc

    def test_get_product_found(self):
        va = VendorApp("helsinki-maker-store")
        first_id = va.products[0].id
        p = va.get_product(first_id)
        assert p is not None
        assert p.id == first_id

    def test_get_product_not_found(self):
        va = VendorApp("helsinki-maker-store")
        assert va.get_product("nonexistent-id") is None

    def test_app_is_fastapi(self):
        from fastapi import FastAPI
        va = VendorApp("helsinki-maker-store")
        assert isinstance(va.app, FastAPI)

    def test_available_vendor_ids(self):
        ids = VendorApp.available_vendor_ids()
        assert "helsinki-maker-store" in ids
        assert "berlin-hacker-space" in ids

    def test_berlin_products(self):
        va = VendorApp("berlin-hacker-space")
        products = va.products
        assert len(products) > 0

    def test_unknown_vendor_raises(self):
        with pytest.raises((KeyError, ValueError)):
            VendorApp("nonexistent-vendor").products


# ---------------------------------------------------------------------------
# RegistryClient SDK tests
# ---------------------------------------------------------------------------


HELSINKI_MANIFEST = {
    "vendor_id": "helsinki-maker-store",
    "name": "Helsinki Maker Store",
    "description": "Maker merch shipped across Europe.",
    "category": ["clothing", "accessories"],
    "mcp_endpoint": "https://api.helsinkimakerstore.fi/mcp",
    "payment": {
        "protocol": "x402",
        "address": "0xABCD1234ABCD1234ABCD1234ABCD1234ABCD1234",
        "currency": "USDC",
        "network": "base-sepolia",
        "price_per_query": "0.05",
    },
    "ships_to": ["FI", "SE", "DE"],
    "verified": False,
    "schema_version": "0.1.0",
}

BERLIN_MANIFEST = {
    "vendor_id": "berlin-hacker-space",
    "name": "Berlin Hacker Space",
    "description": "Electronics and tools shipped across Central Europe.",
    "category": ["electronics", "tools"],
    "mcp_endpoint": "https://api.berlinhackerspace.de/mcp",
    "payment": {
        "protocol": "x402",
        "address": "0x1234ABCD1234ABCD1234ABCD1234ABCD1234ABCD",
        "currency": "USDC",
        "network": "base-sepolia",
        "price_per_query": "0.03",
    },
    "ships_to": ["DE", "AT", "CH"],
    "verified": False,
    "schema_version": "0.1.0",
}


@pytest.fixture
def registry_client_with_data():
    """Return a RegistryClient backed by an in-process registry with two vendors."""
    store = VendorStore()
    registry_app = create_registry_app(store=store)
    transport = _SyncTransport(registry_app)
    http = httpx.Client(transport=transport, base_url="http://testserver")

    # Seed the registry directly via HTTP
    http.post("/vendors/register", json=HELSINKI_MANIFEST)
    http.post("/vendors/register", json=BERLIN_MANIFEST)

    # Build RegistryClient with patched httpx internals
    rc = RegistryClient.__new__(RegistryClient)
    rc._base_url = "http://testserver"
    rc._timeout = 10.0
    rc._http = http  # store for use in patched methods
    return rc, http


class TestRegistryClientSDK:
    def _make_client(self, http: httpx.Client) -> RegistryClient:
        """Patch httpx.Client so RegistryClient uses our in-process transport."""
        rc = RegistryClient("http://testserver")
        rc._http_override = http
        return rc

    def test_register_via_sdk(self):
        store = VendorStore()
        registry_app = create_registry_app(store=store)
        transport = _SyncTransport(registry_app)

        rc = RegistryClient("http://testserver")

        with patch("httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = lambda s: mock_instance
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "manifest": HELSINKI_MANIFEST,
                "registered_at": "2026-01-01T00:00:00Z",
            }
            mock_resp.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_resp

            result = rc.register(HELSINKI_MANIFEST)
            assert result["manifest"]["vendor_id"] == "helsinki-maker-store"

    def test_discover_returns_vendor_info(self):
        rc = RegistryClient("http://testserver")

        with patch("httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = lambda s: mock_instance
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "count": 1,
                "vendors": [{"manifest": HELSINKI_MANIFEST, "registered_at": "2026-01-01T00:00:00Z"}],
            }
            mock_resp.raise_for_status = MagicMock()
            mock_instance.get.return_value = mock_resp

            vendors = rc.discover(category="clothing", ships_to="FI")
            assert len(vendors) == 1
            v = vendors[0]
            assert isinstance(v, VendorInfo)
            assert v.vendor_id == "helsinki-maker-store"
            assert v.mcp_endpoint == "https://api.helsinkimakerstore.fi/mcp"
            assert v.price_per_query == "0.05"

    def test_discover_no_results(self):
        rc = RegistryClient("http://testserver")

        with patch("httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = lambda s: mock_instance
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_resp = MagicMock()
            mock_resp.json.return_value = {"count": 0, "vendors": []}
            mock_resp.raise_for_status = MagicMock()
            mock_instance.get.return_value = mock_resp

            vendors = rc.discover(ships_to="JP")
            assert vendors == []

    def test_health_returns_dict(self):
        rc = RegistryClient("http://testserver")

        with patch("httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = lambda s: mock_instance
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "vendor_id": "helsinki-maker-store",
                "status": "healthy",
                "latency_ms": 12.3,
                "checked_at": "2026-01-01T00:00:00Z",
            }
            mock_resp.raise_for_status = MagicMock()
            mock_instance.get.return_value = mock_resp

            health = rc.health("helsinki-maker-store")
            assert health["status"] == "healthy"


# ---------------------------------------------------------------------------
# AshreAgent SDK tests
# ---------------------------------------------------------------------------


def _mock_claude(tool_calls: list[dict], final_text: str):
    """Build a minimal mock Anthropic client that drives one pass of tool use."""
    mock_anthropic = MagicMock()

    # Build tool-use response
    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_blocks = []
    for tc in tool_calls:
        tb = MagicMock()
        tb.type = "tool_use"
        tb.name = tc["name"]
        tb.id = tc.get("id", "tu_1")
        tb.input = tc["input"]
        tool_blocks.append(tb)
    tool_response.content = tool_blocks

    # Build final text response
    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = final_text
    final_response.content = [text_block]

    mock_anthropic.messages.create.side_effect = [tool_response, final_response]
    return mock_anthropic


class TestAshreAgentSDK:
    @pytest.fixture
    def vendor_http(self):
        """httpx.Client wired to the Helsinki vendor app."""
        vendor_app = create_vendor_app("helsinki-maker-store")
        return httpx.Client(
            transport=_SyncTransport(vendor_app),
            base_url="http://testserver",
        )

    def test_shop_returns_shop_result(self, vendor_http):
        """shop() returns a ShopResult with success=True on a happy path."""
        mock_anthropic = MagicMock()
        final = MagicMock()
        final.stop_reason = "end_turn"
        tb = MagicMock()
        tb.type = "text"
        tb.text = "I found a great hoodie for you!"
        final.content = [tb]
        mock_anthropic.messages.create.return_value = final

        agent = AshreAgent.__new__(AshreAgent)
        agent._client = mock_anthropic
        agent._payer_address = "0xAgentWallet0000000000000000000000000000"

        result = agent.shop(
            "I need a warm hoodie",
            vendor_url="http://testserver",
            http_client=vendor_http,
        )

        assert isinstance(result, ShopResult)
        assert result.success is True
        assert result.vendor_url == "http://testserver"

    def test_shop_error_returns_failure(self):
        """shop() returns success=False when the agent raises."""
        mock_anthropic = MagicMock()
        mock_anthropic.messages.create.side_effect = RuntimeError("API down")

        agent = AshreAgent.__new__(AshreAgent)
        agent._client = mock_anthropic
        agent._payer_address = "0xAgentWallet0000000000000000000000000000"

        result = agent.shop(
            "I need a hoodie",
            vendor_url="http://testserver",
        )

        assert result.success is False
        assert result.error is not None

    def test_ashre_agent_init_uses_api_key(self):
        """AshreAgent passes api_key to Anthropic if provided."""
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value = MagicMock()
            agent = AshreAgent(anthropic_api_key="sk-test-key")
            MockAnthropic.assert_called_once_with(api_key="sk-test-key")

    def test_ashre_agent_init_no_key(self):
        """AshreAgent uses env var when no api_key is given."""
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value = MagicMock()
            agent = AshreAgent()
            MockAnthropic.assert_called_once_with()

    def test_shop_multi_returns_multi_result(self):
        """shop_multi() wraps run_multi_agent and returns MultiShopResult."""
        mock_result = {
            "summary": "Bought a soldering iron from Berlin",
            "chosen_vendor": "http://berlin",
            "order": {"product_id": "sol-iron", "quantity": 1},
            "all_catalogs": {},
        }

        agent = AshreAgent.__new__(AshreAgent)
        agent._client = MagicMock()
        agent._payer_address = "0xAgent"

        import asyncio as _asyncio
        with patch("sdk.agent.run_multi_agent") as mock_rma, \
             patch("sdk.agent.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = mock_result
            result = agent.shop_multi(
                "I need a soldering iron",
                vendor_urls=["http://helsinki", "http://berlin"],
            )

        assert isinstance(result, MultiShopResult)
        assert result.success is True
        assert result.summary == "Bought a soldering iron from Berlin"
        assert result.chosen_vendor == "http://berlin"

    def test_shop_multi_error_returns_failure(self):
        """shop_multi() returns success=False when run_multi_agent raises."""
        agent = AshreAgent.__new__(AshreAgent)
        agent._client = MagicMock()
        agent._payer_address = "0xAgent"

        with patch("sdk.agent.asyncio") as mock_asyncio:
            mock_asyncio.run.side_effect = RuntimeError("network error")
            result = agent.shop_multi(
                "I need tools",
                vendor_urls=["http://helsinki"],
            )

        assert result.success is False
        assert result.error == "network error"
