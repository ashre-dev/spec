"""
Payment handling.

Mock mode (default): accepts any non-empty payment_id with the correct amount.
Production mode: will integrate with Stripe Connect for real payment verification.
"""

import os
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta

# token -> {expires_at, payer_id}
_active_tokens: dict[str, dict] = {}

TOKEN_TTL = 3600  # seconds

# reservation_id -> {product_id, quantity, expires_at}
_reservations: dict[str, dict] = {}

RESERVATION_TTL = 300  # 5 minutes


def issue_token(payer_id: str) -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    _active_tokens[token] = {
        "expires_at": time.time() + TOKEN_TTL,
        "payer_id": payer_id,
    }
    return token, TOKEN_TTL


def validate_token(token: str) -> bool:
    entry = _active_tokens.get(token)
    if not entry:
        return False
    if time.time() > entry["expires_at"]:
        del _active_tokens[token]
        return False
    return True


def create_reservation(product_id: str, quantity: int) -> tuple[str, str]:
    """Create a reservation hold. Returns (reservation_id, held_until ISO string)."""
    reservation_id = str(uuid.uuid4())
    expires_at = time.time() + RESERVATION_TTL
    held_until = datetime.now(timezone.utc) + timedelta(seconds=RESERVATION_TTL)
    _reservations[reservation_id] = {
        "product_id": product_id,
        "quantity": quantity,
        "expires_at": expires_at,
    }
    return reservation_id, held_until.isoformat()


def validate_reservation(reservation_id: str, product_id: str, quantity: int) -> bool:
    """Check reservation exists, matches product/quantity, and hasn't expired."""
    entry = _reservations.get(reservation_id)
    if not entry:
        return False
    if time.time() > entry["expires_at"]:
        del _reservations[reservation_id]
        return False
    return entry["product_id"] == product_id and entry["quantity"] == quantity


def consume_reservation(reservation_id: str) -> None:
    """Remove a reservation after successful purchase."""
    _reservations.pop(reservation_id, None)


def mock_verify_payment(payment_id: str, amount: str, expected_amount: str) -> bool:
    """Stub — accepts any non-empty payment_id with correct amount."""
    if not payment_id:
        return False
    try:
        paid = float(amount)
        required = float(expected_amount)
        return paid >= required
    except ValueError:
        return False


def verify_payment(
    payment_id: str,
    amount: str,
    expected_amount: str,
) -> bool:
    """
    Verify a payment. Currently uses mock verification.
    Production: will verify via Stripe API.
    """
    return mock_verify_payment(payment_id, amount, expected_amount)
