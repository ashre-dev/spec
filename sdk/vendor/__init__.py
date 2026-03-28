"""
ASHRE Vendor SDK
~~~~~~~~~~~~~~~~
High-level helpers for running an ASHRE-compliant vendor server.

Usage::

    from ashre.vendor import VendorApp

    app = VendorApp("my-vendor-id")
    app.run()                        # starts uvicorn on port 8000

Or pass the underlying FastAPI app to an ASGI server directly::

    from ashre.vendor import VendorApp
    fastapi_app = VendorApp("my-vendor-id").app
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI

from src.vendor_server.main import create_vendor_app
from src.vendor_server.vendors import VENDOR_CATALOG, load_vendor


@dataclass
class Product:
    """A single product offered by a vendor."""

    id: str
    name: str
    description: str
    price_usdc: str
    category: str
    in_stock: bool
    ships_to: list[str]


class VendorApp:
    """
    Wraps a FastAPI vendor server with a convenient Python API.

    Parameters
    ----------
    vendor_id:
        The vendor identifier (must exist in the vendor catalog or be registered
        via *catalog* kwarg).
    """

    def __init__(self, vendor_id: str) -> None:
        self._vendor_id = vendor_id
        self._app: FastAPI = create_vendor_app(vendor_id)

    # ------------------------------------------------------------------
    # FastAPI app
    # ------------------------------------------------------------------

    @property
    def app(self) -> FastAPI:
        """The underlying FastAPI application (pass to any ASGI server)."""
        return self._app

    # ------------------------------------------------------------------
    # Catalog helpers
    # ------------------------------------------------------------------

    @property
    def products(self) -> list[Product]:
        """All products offered by this vendor."""
        cfg = load_vendor(self._vendor_id)
        return [
            Product(
                id=p.id,
                name=p.name,
                description=p.description,
                price_usdc=p.price_usdc,
                category=p.category,
                in_stock=p.in_stock,
                ships_to=p.ships_to,
            )
            for p in cfg["products"]
        ]

    def get_product(self, product_id: str) -> Product | None:
        """Return a single product by ID, or *None* if not found."""
        cfg = load_vendor(self._vendor_id)
        p = cfg["products_by_id"].get(product_id)
        if p is None:
            return None
        return Product(
            id=p.id,
            name=p.name,
            description=p.description,
            price_usdc=p.price_usdc,
            category=p.category,
            in_stock=p.in_stock,
            ships_to=p.ships_to,
        )

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------

    def run(self, host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
        """Start the vendor server with uvicorn (blocking)."""
        uvicorn.run(self._app, host=host, port=port, reload=reload)

    # ------------------------------------------------------------------
    # Catalog registry
    # ------------------------------------------------------------------

    @staticmethod
    def available_vendor_ids() -> list[str]:
        """Return all vendor IDs present in the built-in catalog."""
        return list(VENDOR_CATALOG.keys())
