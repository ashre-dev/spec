"""
In-memory vendor store.

A single shared instance (`registry`) is imported by main.py.
Tests can instantiate their own VendorStore for isolation.
"""

from datetime import datetime, timezone
from .models import VendorManifest, VendorRegistration


class VendorStore:
    def __init__(self) -> None:
        self._vendors: dict[str, VendorRegistration] = {}

    def register(self, manifest: VendorManifest) -> VendorRegistration:
        # ASHRE always overrides the caller-supplied `verified` flag
        manifest = manifest.model_copy(update={"verified": False})
        reg = VendorRegistration(
            manifest=manifest,
            registered_at=datetime.now(timezone.utc),
        )
        self._vendors[manifest.vendor_id] = reg
        return reg

    def exists(self, vendor_id: str) -> bool:
        return vendor_id in self._vendors

    def get(self, vendor_id: str) -> VendorRegistration | None:
        return self._vendors.get(vendor_id)

    def discover(
        self,
        categories: list[str] | None = None,
        ships_to: str | None = None,
        verified: bool | None = None,
    ) -> list[VendorRegistration]:
        results = list(self._vendors.values())

        if categories:
            results = [
                r for r in results
                if any(c in r.manifest.category for c in categories)
            ]

        if ships_to:
            results = [
                r for r in results
                if r.manifest.ships_to and ships_to.upper() in r.manifest.ships_to
            ]

        if verified is not None:
            results = [r for r in results if r.manifest.verified == verified]

        return results

    def all(self) -> list[VendorRegistration]:
        return list(self._vendors.values())


# Shared singleton used by the registry API
registry = VendorStore()
