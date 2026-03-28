"""
Vendor health check.

Probes the vendor's mcp_endpoint with a GET request.
- HTTP 200 or 402 → healthy (402 means the server is up and gating correctly)
- Any other 4xx/5xx → degraded
- Connection error / timeout → unreachable
"""

import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from .models import HealthStatus


def check_vendor_health(
    vendor_id: str,
    mcp_endpoint: str,
    http_client: Optional[httpx.Client] = None,
    timeout: float = 8.0,
) -> HealthStatus:
    """
    Probe `mcp_endpoint` and return a HealthStatus.

    An optional `http_client` can be injected for testing (e.g. to route
    through a mock or the FastAPI test transport).
    """
    client = http_client or httpx.Client(timeout=timeout)
    start = time.monotonic()

    try:
        resp = client.get(mcp_endpoint)
        latency_ms = round((time.monotonic() - start) * 1000, 2)

        if resp.status_code in (200, 402):
            return HealthStatus(
                vendor_id=vendor_id,
                status="healthy",
                latency_ms=latency_ms,
                checked_at=datetime.now(timezone.utc),
            )
        else:
            return HealthStatus(
                vendor_id=vendor_id,
                status="degraded",
                latency_ms=latency_ms,
                checked_at=datetime.now(timezone.utc),
                detail=f"Unexpected HTTP {resp.status_code}",
            )

    except httpx.TimeoutException:
        return HealthStatus(
            vendor_id=vendor_id,
            status="unreachable",
            checked_at=datetime.now(timezone.utc),
            detail="Connection timed out",
        )
    except Exception as exc:
        return HealthStatus(
            vendor_id=vendor_id,
            status="unreachable",
            checked_at=datetime.now(timezone.utc),
            detail=str(exc),
        )
