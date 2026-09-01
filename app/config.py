import os
from decimal import Decimal
from pathlib import Path

OZON_API_BASE_URL = "https://api-seller.ozon.ru"
PRICES_INFO_ENDPOINT = "/v5/product/info/prices"
PRICES_IMPORT_ENDPOINT = "/v1/product/import/prices"

PAGE_LIMIT = 1000
MAX_PAGES = 100
IMPORT_BATCH_SIZE = 1000

TARGET_MARKET_PRICE = Decimal("1500")
SITE_PRICE_MARKUP_PERCENT = Decimal("5")


def get_target_market_price() -> Decimal:
    return Decimal(os.getenv("TARGET_MARKET_PRICE", str(TARGET_MARKET_PRICE)))


def get_site_price_markup_percent() -> Decimal:
    return Decimal(os.getenv("SITE_PRICE_MARKUP_PERCENT", str(SITE_PRICE_MARKUP_PERCENT)))

LOCAL_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
