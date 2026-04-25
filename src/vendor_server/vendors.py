"""
All vendor catalog data. Add new vendors here; select via VENDOR_ID env var.
"""

from .models import Product

_HELSINKI_SHIPS_TO = ["FI", "SE", "NO", "DK", "DE", "NL", "EE", "LV", "LT"]
_BERLIN_SHIPS_TO = ["DE", "AT", "CH", "NL", "BE", "FR", "PL", "CZ"]
_CHENNAI_SHIPS_TO = ["IN", "LK", "SG", "MY", "AE"]

VENDOR_CATALOG: dict[str, dict] = {
    "helsinki-maker-store": {
        "vendor_id": "helsinki-maker-store",
        "name": "Helsinki Maker Store",
        "wallet_address": "0xABCD1234ABCD1234ABCD1234ABCD1234ABCD1234",
        "price_per_query": "0.05",
        "ships_to": _HELSINKI_SHIPS_TO,
        "products": [
            Product(
                id="hms-tee-001",
                name="Helsinki Maker Tee",
                description="Classic black t-shirt with Helsinki Maker Store logo, 100% organic cotton.",
                price_usdc="18.00",
                category="clothing",
                ships_to=_HELSINKI_SHIPS_TO,
            ),
            Product(
                id="hms-hoodie-001",
                name="Soldering Iron Hoodie",
                description="Warm pullover hoodie with embroidered soldering iron graphic. Unisex fit.",
                price_usdc="42.00",
                category="clothing",
                ships_to=_HELSINKI_SHIPS_TO,
            ),
            Product(
                id="hms-pin-001",
                name="Circuit Board Enamel Pin",
                description="Hard enamel pin shaped like a PCB. 3cm wide, butterfly clutch.",
                price_usdc="6.00",
                category="accessories",
                ships_to=_HELSINKI_SHIPS_TO,
            ),
            Product(
                id="hms-tote-001",
                name="Maker Tote Bag",
                description="Heavy-duty canvas tote bag with screen-printed maker logo. Holds a laptop.",
                price_usdc="22.00",
                category="accessories",
                ships_to=_HELSINKI_SHIPS_TO,
            ),
            Product(
                id="hms-sticker-pack-001",
                name="Maker Sticker Pack",
                description="10-pack of die-cut vinyl stickers — tools, components, Finnish icons.",
                price_usdc="9.00",
                category="merchandise",
                ships_to=_HELSINKI_SHIPS_TO,
            ),
            Product(
                id="hms-mug-001",
                name="Byte-Sized Mug",
                description="350ml ceramic mug printed with a binary joke. Dishwasher safe.",
                price_usdc="14.00",
                category="merchandise",
                in_stock=False,
                ships_to=_HELSINKI_SHIPS_TO,
            ),
        ],
    },
    "berlin-hacker-space": {
        "vendor_id": "berlin-hacker-space",
        "name": "Berlin Hacker Space",
        "wallet_address": "0x1234ABCD1234ABCD1234ABCD1234ABCD1234ABCD",
        "price_per_query": "0.03",
        "ships_to": _BERLIN_SHIPS_TO,
        "products": [
            Product(
                id="bhs-rpi-001",
                name="Raspberry Pi 5 Starter Kit",
                description="Raspberry Pi 5 (4GB), 32GB SD card, official case, power supply, and HDMI cable.",
                price_usdc="95.00",
                category="electronics",
                ships_to=_BERLIN_SHIPS_TO,
            ),
            Product(
                id="bhs-arduino-001",
                name="Arduino Mega 2560 Rev3",
                description="Official Arduino Mega 2560 Rev3 microcontroller board with USB cable.",
                price_usdc="38.00",
                category="electronics",
                ships_to=_BERLIN_SHIPS_TO,
            ),
            Product(
                id="bhs-solder-001",
                name="Hakko FX-888D Soldering Station",
                description="Digital soldering station with adjustable temperature 200–480°C. Includes T18-B tip.",
                price_usdc="120.00",
                category="tools",
                ships_to=_BERLIN_SHIPS_TO,
            ),
            Product(
                id="bhs-led-001",
                name="LED Component Pack (500pcs)",
                description="Assorted 5mm LEDs: red, green, blue, yellow, white. 100 of each colour.",
                price_usdc="12.00",
                category="components",
                ships_to=_BERLIN_SHIPS_TO,
            ),
            Product(
                id="bhs-usbc-001",
                name="7-Port USB-C Hub",
                description="USB-C hub with 3×USB-A 3.0, 2×USB-C, HDMI, and SD card reader.",
                price_usdc="29.00",
                category="electronics",
                ships_to=_BERLIN_SHIPS_TO,
            ),
            Product(
                id="bhs-multimeter-001",
                name="Fluke 117 Digital Multimeter",
                description="True-RMS multimeter for electricians. Auto voltage detection, non-contact voltage.",
                price_usdc="175.00",
                category="tools",
                ships_to=_BERLIN_SHIPS_TO,
            ),
            Product(
                id="bhs-tee-001",
                name="Hacker Space Tee",
                description="100% cotton t-shirt with Berlin Hacker Space logo on the chest.",
                price_usdc="16.00",
                category="clothing",
                ships_to=_BERLIN_SHIPS_TO,
            ),
        ],
    },
    "chennai-threads": {
        "vendor_id": "chennai-threads",
        "name": "Chennai Threads",
        "wallet_address": "0xCHENNAI0000THREADS0000WALLET000000000001",
        "price_per_query": "0.02",
        "ships_to": _CHENNAI_SHIPS_TO,
        "products": [
            Product(
                id="ct-tee-blue-001",
                name="Blue Cotton Tee",
                description="Soft 100% Madras cotton crew-neck t-shirt in sky blue. Sizes S–XXL.",
                price_usdc="25.00",
                category="clothing",
                ships_to=_CHENNAI_SHIPS_TO,
            ),
            Product(
                id="ct-kurta-001",
                name="Hand-Block Printed Kurta",
                description="Lightweight cotton kurta with traditional block-print pattern. Unisex.",
                price_usdc="35.00",
                category="clothing",
                ships_to=_CHENNAI_SHIPS_TO,
            ),
            Product(
                id="ct-polo-001",
                name="Organic Polo Shirt",
                description="GOTS-certified organic cotton polo in charcoal grey. Slim fit.",
                price_usdc="30.00",
                category="clothing",
                ships_to=_CHENNAI_SHIPS_TO,
            ),
            Product(
                id="ct-scarf-001",
                name="Silk-Cotton Scarf",
                description="Handwoven Kanchipuram silk-cotton blend scarf, 180cm × 50cm.",
                price_usdc="40.00",
                category="accessories",
                ships_to=_CHENNAI_SHIPS_TO,
            ),
            Product(
                id="ct-tote-001",
                name="Kalamkari Tote Bag",
                description="Canvas tote with hand-painted Kalamkari art. Reinforced straps.",
                price_usdc="20.00",
                category="accessories",
                ships_to=_CHENNAI_SHIPS_TO,
                in_stock=False,
            ),
        ],
    },
}


def load_vendor(vendor_id: str) -> dict:
    """
    Return vendor config for the given vendor_id.
    Adds a `products_by_id` lookup dict.
    Raises ValueError for unknown vendor IDs.
    """
    if vendor_id not in VENDOR_CATALOG:
        available = list(VENDOR_CATALOG.keys())
        raise ValueError(f"Unknown vendor_id {vendor_id!r}. Available: {available}")
    cfg = dict(VENDOR_CATALOG[vendor_id])
    cfg["products_by_id"] = {p.id: p for p in cfg["products"]}
    return cfg
