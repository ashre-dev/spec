from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import VendorManifest, VendorRegistration, HealthStatus, DiscoverResponse
from .store import VendorStore, registry as _default_registry
from .health import check_vendor_health


def create_registry_app(store: VendorStore | None = None) -> FastAPI:
    """
    Factory — creates the registry FastAPI app.
    Pass a custom `store` for testing (isolated, empty store per test).
    """
    _store = store or _default_registry

    app = FastAPI(title="ASHRE Registry", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://ashre.dev", "https://www.ashre.dev"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.post("/vendors/register", response_model=VendorRegistration, status_code=201)
    def register_vendor(manifest: VendorManifest):
        """
        Register a new vendor manifest.
        Returns 409 if the vendor_id is already registered.
        """
        if _store.exists(manifest.vendor_id):
            raise HTTPException(
                status_code=409,
                detail=f"Vendor '{manifest.vendor_id}' is already registered. "
                       "Use a unique vendor_id or contact ASHRE to update an existing entry.",
            )
        return _store.register(manifest)

    @app.get("/vendors/discover", response_model=DiscoverResponse)
    def discover_vendors(
        category: Optional[list[str]] = Query(default=None),
        ships_to: Optional[str] = Query(default=None),
        verified: Optional[bool] = Query(default=None),
    ):
        """
        Discover registered vendors.

        All filters are optional and combinable:
        - `category` — match any of the supplied categories (repeat for multiple)
        - `ships_to` — ISO 3166-1 alpha-2 country code the vendor must ship to
        - `verified` — true/false to filter by ASHRE-verified status
        """
        results = _store.discover(
            categories=category,
            ships_to=ships_to,
            verified=verified,
        )
        return DiscoverResponse(count=len(results), vendors=results)

    @app.get("/vendors/{vendor_id}/health", response_model=HealthStatus)
    def vendor_health(vendor_id: str):
        """
        Probe the vendor's MCP endpoint and return a health status.
        Returns 404 if the vendor_id is not registered.
        """
        reg = _store.get(vendor_id)
        if reg is None:
            raise HTTPException(status_code=404, detail=f"Vendor '{vendor_id}' not found")
        return check_vendor_health(vendor_id, reg.manifest.mcp_endpoint)

    return app


# Default app backed by the shared in-memory registry
app = create_registry_app()
