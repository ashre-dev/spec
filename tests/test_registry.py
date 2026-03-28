"""
Registry API tests.

Each test gets its own isolated VendorStore via the factory function,
so tests are fully independent of one another.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.registry.main import create_registry_app
from src.registry.store import VendorStore
from src.registry.models import HealthStatus


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store() -> VendorStore:
    return VendorStore()


@pytest.fixture
def client(store) -> TestClient:
    return TestClient(create_registry_app(store=store))


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


# ---------------------------------------------------------------------------
# POST /vendors/register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_returns_201(self, client):
        resp = client.post("/vendors/register", json=HELSINKI_MANIFEST)
        assert resp.status_code == 201

    def test_register_response_has_manifest_and_timestamp(self, client):
        resp = client.post("/vendors/register", json=HELSINKI_MANIFEST)
        body = resp.json()
        assert body["manifest"]["vendor_id"] == "helsinki-maker-store"
        assert "registered_at" in body

    def test_verified_flag_always_false_on_register(self, client):
        """ASHRE controls verified status — callers cannot set it."""
        manifest = {**HELSINKI_MANIFEST, "verified": True}  # caller tries to self-verify
        resp = client.post("/vendors/register", json=manifest)
        assert resp.status_code == 201
        assert resp.json()["manifest"]["verified"] is False

    def test_duplicate_vendor_id_returns_409(self, client):
        client.post("/vendors/register", json=HELSINKI_MANIFEST)
        resp = client.post("/vendors/register", json=HELSINKI_MANIFEST)
        assert resp.status_code == 409

    def test_invalid_vendor_id_format_returns_422(self, client):
        bad = {**HELSINKI_MANIFEST, "vendor_id": "UPPER_CASE"}
        resp = client.post("/vendors/register", json=bad)
        assert resp.status_code == 422

    def test_empty_category_returns_422(self, client):
        bad = {**HELSINKI_MANIFEST, "category": []}
        resp = client.post("/vendors/register", json=bad)
        assert resp.status_code == 422

    def test_unsupported_schema_version_returns_422(self, client):
        bad = {**HELSINKI_MANIFEST, "schema_version": "99.0.0"}
        resp = client.post("/vendors/register", json=bad)
        assert resp.status_code == 422

    def test_missing_required_field_returns_422(self, client):
        bad = {k: v for k, v in HELSINKI_MANIFEST.items() if k != "mcp_endpoint"}
        resp = client.post("/vendors/register", json=bad)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /vendors/discover
# ---------------------------------------------------------------------------

class TestDiscover:
    @pytest.fixture(autouse=True)
    def seed(self, client):
        client.post("/vendors/register", json=HELSINKI_MANIFEST)
        client.post("/vendors/register", json=BERLIN_MANIFEST)

    def test_discover_all_returns_both(self, client):
        resp = client.get("/vendors/discover")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert len(body["vendors"]) == 2

    def test_discover_by_category_clothing(self, client):
        resp = client.get("/vendors/discover?category=clothing")
        body = resp.json()
        assert body["count"] == 1
        assert body["vendors"][0]["manifest"]["vendor_id"] == "helsinki-maker-store"

    def test_discover_by_category_electronics(self, client):
        resp = client.get("/vendors/discover?category=electronics")
        body = resp.json()
        assert body["count"] == 1
        assert body["vendors"][0]["manifest"]["vendor_id"] == "berlin-hacker-space"

    def test_discover_multiple_categories_returns_union(self, client):
        resp = client.get("/vendors/discover?category=clothing&category=electronics")
        body = resp.json()
        assert body["count"] == 2

    def test_discover_by_ships_to_fi(self, client):
        resp = client.get("/vendors/discover?ships_to=FI")
        body = resp.json()
        assert body["count"] == 1
        assert body["vendors"][0]["manifest"]["vendor_id"] == "helsinki-maker-store"

    def test_discover_ships_to_case_insensitive(self, client):
        resp = client.get("/vendors/discover?ships_to=fi")
        body = resp.json()
        assert body["count"] == 1

    def test_discover_ships_to_de_returns_both(self, client):
        """DE is in both vendor ship lists."""
        resp = client.get("/vendors/discover?ships_to=DE")
        body = resp.json()
        assert body["count"] == 2

    def test_discover_by_verified_false_returns_both(self, client):
        resp = client.get("/vendors/discover?verified=false")
        body = resp.json()
        assert body["count"] == 2

    def test_discover_by_verified_true_returns_none(self, client):
        resp = client.get("/vendors/discover?verified=true")
        body = resp.json()
        assert body["count"] == 0

    def test_discover_combined_filter(self, client):
        resp = client.get("/vendors/discover?category=electronics&ships_to=AT")
        body = resp.json()
        assert body["count"] == 1
        assert body["vendors"][0]["manifest"]["vendor_id"] == "berlin-hacker-space"

    def test_discover_no_match_returns_empty(self, client):
        resp = client.get("/vendors/discover?ships_to=JP")
        body = resp.json()
        assert body["count"] == 0
        assert body["vendors"] == []


# ---------------------------------------------------------------------------
# GET /vendors/{vendor_id}/health
# ---------------------------------------------------------------------------

class TestHealth:
    @pytest.fixture(autouse=True)
    def seed(self, client):
        client.post("/vendors/register", json=HELSINKI_MANIFEST)

    def test_health_not_found_returns_404(self, client):
        resp = client.get("/vendors/nonexistent/health")
        assert resp.status_code == 404

    def test_health_healthy_vendor(self, client):
        mock_status = HealthStatus(
            vendor_id="helsinki-maker-store",
            status="healthy",
            latency_ms=42.5,
            checked_at=datetime.now(timezone.utc),
        )
        with patch("src.registry.main.check_vendor_health", return_value=mock_status):
            resp = client.get("/vendors/helsinki-maker-store/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["latency_ms"] == 42.5
        assert body["vendor_id"] == "helsinki-maker-store"

    def test_health_unreachable_vendor(self, client):
        mock_status = HealthStatus(
            vendor_id="helsinki-maker-store",
            status="unreachable",
            checked_at=datetime.now(timezone.utc),
            detail="Connection timed out",
        )
        with patch("src.registry.main.check_vendor_health", return_value=mock_status):
            resp = client.get("/vendors/helsinki-maker-store/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "unreachable"
        assert body["detail"] == "Connection timed out"
        assert body["latency_ms"] is None


# ---------------------------------------------------------------------------
# check_vendor_health (unit tests — mock httpx)
# ---------------------------------------------------------------------------

class TestCheckVendorHealth:
    def _run(self, status_code: int | None = 402, exc: Exception | None = None):
        from src.registry.health import check_vendor_health
        import httpx

        mock_http = MagicMock(spec=httpx.Client)
        if exc:
            mock_http.get.side_effect = exc
        else:
            mock_resp = MagicMock()
            mock_resp.status_code = status_code
            mock_http.get.return_value = mock_resp

        return check_vendor_health("test-vendor", "https://example.com/mcp", mock_http)

    def test_402_is_healthy(self):
        result = self._run(status_code=402)
        assert result.status == "healthy"
        assert result.latency_ms is not None

    def test_200_is_healthy(self):
        result = self._run(status_code=200)
        assert result.status == "healthy"

    def test_500_is_degraded(self):
        result = self._run(status_code=500)
        assert result.status == "degraded"
        assert "500" in result.detail

    def test_timeout_is_unreachable(self):
        import httpx
        result = self._run(exc=httpx.TimeoutException("timed out"))
        assert result.status == "unreachable"
        assert result.latency_ms is None
        assert "timed out" in result.detail.lower()

    def test_connection_error_is_unreachable(self):
        import httpx
        result = self._run(exc=httpx.ConnectError("refused"))
        assert result.status == "unreachable"
