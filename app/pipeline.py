import json
import logging

from app.config import get_target_market_price
from app.env import is_dry_run
from app.ozon_client import OzonClient
from app.prices_service import fetch_all_product_prices, import_prices
from app.pricing import build_price_updates

logger = logging.getLogger(__name__)


def run_price_adjustment() -> str:
    logger.info("Старт корректировки цен Ozon")

    client = OzonClient.from_env()
    items = fetch_all_product_prices(client)

    if not items:
        body = "Товары не найдены, обновление не выполнялось"
        logger.info(body)
        return body

    updates = build_price_updates(items, target_market_price=get_target_market_price())
    if not updates:
        body = "Цены проверены, обновлений не требуется"
        logger.info(body)
        return body

    if is_dry_run():
        body = f"DRY_RUN: обновления не отправлены ({len(updates)} товаров рассчитано)"
        logger.info(body)
        logger.info("Планируемые обновления: %s", json.dumps(updates, ensure_ascii=False))
        return body

    import_prices(client, updates)

    body = f"Цены успешно проверены и обновлены ({len(updates)} товаров)"
    logger.info(body)
    return body
