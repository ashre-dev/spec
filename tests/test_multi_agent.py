"""
Multi-vendor agent tests.

Uses httpx.ASGITransport (properly async) to route calls through both
vendor FastAPI apps without a running server.
"""

import json
import pytest
import pytest_asyncio
import httpx
from unittest.mock import MagicMock

from src.vendor_server.main import create_vendor_app
from src.agent.multi_agent import run_multi_agent, _fetch_vendor_catalog

HELSINKI_URL = "http://helsinki"
BERLIN_URL = "http://berlin"


# ---------------------------------------------------------------------------
# Async transport that routes to the right vendor app by hostname
# ---------------------------------------------------------------------------

class MultiVendorTransport(httpx.AsyncBaseTransport):
    """
    Routes async httpx requests to the appropriate FastAPI app
    based on the request hostname, without needing a real server.
    """

    def __init__(self):
        self._apps = {
            "helsinki": httpx.ASGITransport(app=create_vendor_app("helsinki-maker-store")),
            "berlin": httpx.ASGITransport(app=create_vendor_app("berlin-hacker-space")),
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        transport = self._apps.get(host)
        if transport is None:
            raise httpx.ConnectError(f"No vendor app for host '{host}'")
        return await transport.handle_async_request(request)


@pytest_asyncio.fixture
async def multi_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(transport=MultiVendorTransport()) as client:
        yield client


# ---------------------------------------------------------------------------
# _fetch_vendor_catalog — per-vendor flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_helsinki_catalog(multi_client):
    result = await _fetch_vendor_catalog(HELSINKI_URL, multi_client)
    assert result["vendor_url"] == HELSINKI_URL
    assert result["token"] is not None
    assert result["catalog"]["vendor_id"] == "helsinki-maker-store"
    assert len(result["catalog"]["products"]) > 0


@pytest.mark.asyncio
async def test_fetch_berlin_catalog(multi_client):
    result = await _fetch_vendor_catalog(BERLIN_URL, multi_client)
    assert result["vendor_url"] == BERLIN_URL
    assert result["token"] is not None
    assert result["catalog"]["vendor_id"] == "berlin-hacker-space"
    products = result["catalog"]["products"]
    assert any(p["category"] == "electronics" for p in products)


@pytest.mark.asyncio
async def test_both_vendors_queried_in_parallel(multi_client):
    """Both catalogs should be returned when querying in parallel."""
    import asyncio
    from src.agent.multi_agent import _fetch_vendor_catalog

    results = await asyncio.gather(
        _fetch_vendor_catalog(HELSINKI_URL, multi_client),
        _fetch_vendor_catalog(BERLIN_URL, multi_client),
    )
    vendor_ids = {r["catalog"]["vendor_id"] for r in results}
    assert vendor_ids == {"helsinki-maker-store", "berlin-hacker-space"}


# ---------------------------------------------------------------------------
# run_multi_agent — full flow with mocked Claude
# ---------------------------------------------------------------------------

def _mock_pick(vendor_url: str, product_id: str) -> MagicMock:
    """Build a mock Anthropic response that picks a specific product."""
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps({
        "vendor_url": vendor_url,
        "product_id": product_id,
        "quantity": 1,
        "reasoning": "Best match for the request.",
    })
    response = MagicMock()
    response.content = [block]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = response
    return mock_client


@pytest.mark.asyncio
async def test_multi_agent_picks_helsinki_product(multi_client):
    """Agent picks a Helsinki product when Claude says so."""
    mock_claude = _mock_pick(HELSINKI_URL, "hms-tee-001")

    result = await run_multi_agent(
        shopping_request="I want a maker t-shirt",
        vendor_urls=[HELSINKI_URL, BERLIN_URL],
        http_client=multi_client,
        anthropic_client=mock_claude,
    )

    assert result["vendor_url"] == HELSINKI_URL
    assert result["product_id"] == "hms-tee-001"
    assert result["order"]["status"] == "confirmed"
    assert result["catalogs_queried"] == 2


@pytest.mark.asyncio
async def test_multi_agent_picks_berlin_product(multi_client):
    """Agent picks a Berlin product (electronics) when Claude says so."""
    mock_claude = _mock_pick(BERLIN_URL, "bhs-arduino-001")

    result = await run_multi_agent(
        shopping_request="I need a microcontroller for a project",
        vendor_urls=[HELSINKI_URL, BERLIN_URL],
        http_client=multi_client,
        anthropic_client=mock_claude,
    )

    assert result["vendor_url"] == BERLIN_URL
    assert result["product_id"] == "bhs-arduino-001"
    assert result["order"]["status"] == "confirmed"
    assert result["catalogs_queried"] == 2


@pytest.mark.asyncio
async def test_multi_agent_skips_failed_vendor(multi_client):
    """If one vendor URL is unreachable, agent continues with the rest."""
    mock_claude = _mock_pick(HELSINKI_URL, "hms-sticker-pack-001")

    result = await run_multi_agent(
        shopping_request="stickers",
        vendor_urls=[HELSINKI_URL, "http://nonexistent-vendor"],
        http_client=multi_client,
        anthropic_client=mock_claude,
    )

    assert result["vendor_url"] == HELSINKI_URL
    assert result["catalogs_queried"] == 1  # only Helsinki succeeded


@pytest.mark.asyncio
async def test_multi_agent_claude_receives_both_catalogs(multi_client):
    """Verify Claude is called with product data from both vendors."""
    captured_messages: list = []

    def capture_and_return(**kwargs):
        captured_messages.extend(kwargs["messages"])
        block = MagicMock()
        block.type = "text"
        block.text = json.dumps({
            "vendor_url": BERLIN_URL,
            "product_id": "bhs-led-001",
            "quantity": 1,
            "reasoning": "Cheapest option.",
        })
        resp = MagicMock()
        resp.content = [block]
        return resp

    mock_claude = MagicMock()
    mock_claude.messages.create.side_effect = capture_and_return

    await run_multi_agent(
        shopping_request="some LEDs",
        vendor_urls=[HELSINKI_URL, BERLIN_URL],
        http_client=multi_client,
        anthropic_client=mock_claude,
    )

    # The user message content should mention both vendors
    user_content = captured_messages[0]["content"]
    assert "helsinki-maker-store" in user_content
    assert "berlin-hacker-space" in user_content
