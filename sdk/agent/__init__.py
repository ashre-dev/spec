"""
ASHRE Agent SDK
~~~~~~~~~~~~~~~
High-level helpers for building ASHRE-aware buying agents.

Usage::

    from ashre.agent import AshreAgent, RegistryClient

    # Discover vendors from the registry
    registry = RegistryClient("https://registry.ashre.dev")
    vendors = registry.discover(category="clothing", ships_to="FI")

    # Run a single-vendor shopping agent
    agent = AshreAgent()
    result = agent.shop("I need a warm hoodie", vendor_url=vendors[0].mcp_endpoint)

    # Or query multiple vendors in parallel
    result = agent.shop_multi(
        "I need electronics under $50",
        vendor_urls=[v.mcp_endpoint for v in vendors],
    )
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.agent.agent import run_agent
from src.agent.multi_agent import run_multi_agent
from src.registry.models import VendorManifest


# ---------------------------------------------------------------------------
# Data classes returned to callers
# ---------------------------------------------------------------------------


@dataclass
class VendorInfo:
    """A vendor entry returned from the ASHRE registry."""

    vendor_id: str
    name: str
    description: str
    category: list[str]
    mcp_endpoint: str
    ships_to: list[str]
    verified: bool
    payment_address: str
    price_per_query: str


@dataclass
class ShopResult:
    """The outcome of a shopping run."""

    success: bool
    summary: str
    vendor_url: str
    order: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class MultiShopResult:
    """The outcome of a multi-vendor shopping run."""

    success: bool
    summary: str
    chosen_vendor: str | None
    order: dict[str, Any] = field(default_factory=dict)
    all_catalogs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# RegistryClient
# ---------------------------------------------------------------------------


class RegistryClient:
    """
    HTTP client for the ASHRE vendor registry.

    Parameters
    ----------
    base_url:
        Base URL of the registry, e.g. ``"https://registry.ashre.dev"``.
    timeout:
        HTTP timeout in seconds (default 10).
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def register(self, manifest: dict) -> dict:
        """
        Register a vendor manifest with the registry.

        Returns the created registration record or raises on error.
        """
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(f"{self._base_url}/vendors/register", json=manifest)
            resp.raise_for_status()
            return resp.json()

    def discover(
        self,
        *,
        category: str | list[str] | None = None,
        ships_to: str | None = None,
        verified: bool | None = None,
    ) -> list[VendorInfo]:
        """
        Discover vendors matching the given filters.

        Parameters
        ----------
        category:
            One or more product categories (e.g. ``"clothing"``).
        ships_to:
            ISO 3166-1 alpha-2 country code (e.g. ``"FI"``).
        verified:
            If set, only return ASHRE-verified (or unverified) vendors.
        """
        params: list[tuple[str, str]] = []
        if category:
            cats = [category] if isinstance(category, str) else category
            for c in cats:
                params.append(("category", c))
        if ships_to:
            params.append(("ships_to", ships_to))
        if verified is not None:
            params.append(("verified", str(verified).lower()))

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._base_url}/vendors/discover", params=params)
            resp.raise_for_status()

        vendors = []
        for entry in resp.json().get("vendors", []):
            m = entry["manifest"]
            vendors.append(
                VendorInfo(
                    vendor_id=m["vendor_id"],
                    name=m["name"],
                    description=m.get("description", ""),
                    category=m["category"],
                    mcp_endpoint=m["mcp_endpoint"],
                    ships_to=m.get("ships_to", []),
                    verified=m.get("verified", False),
                    payment_address=m["payment"]["address"],
                    price_per_query=m["payment"]["price_per_query"],
                )
            )
        return vendors

    def health(self, vendor_id: str) -> dict:
        """Probe a registered vendor's MCP endpoint and return its health status."""
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._base_url}/vendors/{vendor_id}/health")
            resp.raise_for_status()
            return resp.json()


# ---------------------------------------------------------------------------
# AshreAgent
# ---------------------------------------------------------------------------


class AshreAgent:
    """
    A high-level ASHRE buying agent.

    Wraps the low-level ``run_agent`` and ``run_multi_agent`` functions with a
    clean, batteries-included interface.

    Parameters
    ----------
    anthropic_api_key:
        Anthropic API key.  If *None*, the ``ANTHROPIC_API_KEY`` env var is
        used automatically.
    payer_address:
        On-chain wallet address used as the ``payer_address`` in x402 payment
        requests.  Defaults to the built-in demo address.
    """

    _DEFAULT_PAYER = "0xAgentWallet0000000000000000000000000000"

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        payer_address: str = _DEFAULT_PAYER,
    ) -> None:
        import anthropic

        self._client = anthropic.Anthropic(
            **({"api_key": anthropic_api_key} if anthropic_api_key else {})
        )
        self._payer_address = payer_address

    # ------------------------------------------------------------------
    # Single-vendor shopping
    # ------------------------------------------------------------------

    def shop(
        self,
        request: str,
        *,
        vendor_url: str,
        http_client: httpx.Client | None = None,
    ) -> ShopResult:
        """
        Run a single-vendor shopping agent.

        Parameters
        ----------
        request:
            Natural-language shopping request (e.g. ``"I need a warm hoodie"``).
        vendor_url:
            Base URL of the vendor's MCP server (e.g. ``"http://localhost:8001"``).
        http_client:
            Optional custom ``httpx.Client`` (useful in tests).

        Returns
        -------
        ShopResult
        """
        try:
            summary = run_agent(
                request,
                vendor_url,
                http_client=http_client,
                anthropic_client=self._client,
            )
            return ShopResult(success=True, summary=summary, vendor_url=vendor_url)
        except Exception as exc:
            return ShopResult(
                success=False,
                summary="",
                vendor_url=vendor_url,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Multi-vendor shopping
    # ------------------------------------------------------------------

    def shop_multi(
        self,
        request: str,
        *,
        vendor_urls: list[str],
        shipping_address: str = "123 Main St, Helsinki, Finland",
        http_client: httpx.AsyncClient | None = None,
    ) -> MultiShopResult:
        """
        Query multiple vendors in parallel and pick the best match.

        Parameters
        ----------
        request:
            Natural-language shopping request.
        vendor_urls:
            List of vendor MCP server base URLs to query.
        shipping_address:
            Delivery address passed to the winning vendor.
        http_client:
            Optional custom ``httpx.AsyncClient`` (useful in tests).

        Returns
        -------
        MultiShopResult
        """
        try:
            raw = asyncio.run(
                run_multi_agent(
                    request,
                    vendor_urls,
                    shipping_address=shipping_address,
                    http_client=http_client,
                    anthropic_client=self._client,
                )
            )
            return MultiShopResult(
                success=True,
                summary=raw.get("summary", ""),
                chosen_vendor=raw.get("chosen_vendor"),
                order=raw.get("order", {}),
                all_catalogs=raw.get("all_catalogs", {}),
            )
        except Exception as exc:
            return MultiShopResult(
                success=False,
                summary="",
                chosen_vendor=None,
                error=str(exc),
            )
