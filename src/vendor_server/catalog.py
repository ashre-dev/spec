from .models import Product

VENDOR_ID = "helsinki-maker-store"
VENDOR_NAME = "Helsinki Maker Store"
WALLET_ADDRESS = "0xABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
PRICE_PER_QUERY = "0.05"
SHIPS_TO = ["FI", "SE", "NO", "DK", "DE", "NL", "EE", "LV", "LT"]

PRODUCTS: list[Product] = [
    Product(
        id="hms-tee-001",
        name="Helsinki Maker Tee",
        description="Classic black t-shirt with Helsinki Maker Store logo, 100% organic cotton.",
        price_usdc="18.00",
        category="clothing",
        ships_to=SHIPS_TO,
    ),
    Product(
        id="hms-hoodie-001",
        name="Soldering Iron Hoodie",
        description="Warm pullover hoodie with embroidered soldering iron graphic. Unisex fit.",
        price_usdc="42.00",
        category="clothing",
        ships_to=SHIPS_TO,
    ),
    Product(
        id="hms-pin-001",
        name="Circuit Board Enamel Pin",
        description="Hard enamel pin shaped like a PCB. 3cm wide, butterfly clutch.",
        price_usdc="6.00",
        category="accessories",
        ships_to=SHIPS_TO,
    ),
    Product(
        id="hms-tote-001",
        name="Maker Tote Bag",
        description="Heavy-duty canvas tote bag with screen-printed maker logo. Holds a laptop.",
        price_usdc="22.00",
        category="accessories",
        ships_to=SHIPS_TO,
    ),
    Product(
        id="hms-sticker-pack-001",
        name="Maker Sticker Pack",
        description="10-pack of die-cut vinyl stickers — tools, components, Finnish icons.",
        price_usdc="9.00",
        category="merchandise",
        ships_to=SHIPS_TO,
    ),
    Product(
        id="hms-mug-001",
        name="Byte-Sized Mug",
        description="350ml ceramic mug printed with a binary joke. Dishwasher safe.",
        price_usdc="14.00",
        category="merchandise",
        in_stock=False,
        ships_to=SHIPS_TO,
    ),
]

PRODUCTS_BY_ID: dict[str, Product] = {p.id: p for p in PRODUCTS}
