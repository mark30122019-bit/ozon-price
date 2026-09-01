import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.config import get_target_market_price

logger = logging.getLogger(__name__)


def to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def get_price_with_ozon_card(item: dict[str, Any]) -> Optional[Decimal]:
    """Извлекает актуальную цену для покупателя с Ozon Картой."""
    price_indexes = item.get("price_indexes") or {}
    return to_decimal(price_indexes.get("price_with_ozon_card"))


def get_base_price(item: dict[str, Any]) -> Optional[Decimal]:
    price_block = item.get("price") or {}
    return to_decimal(price_block.get("price"))


def calculate_new_base_price(
    price_with_ozon_card: Decimal,
    current_base_price: Decimal,
    target_market_price: Optional[Decimal] = None,
) -> Optional[Decimal]:
    """
    Формула пересчёта базовой цены.

    Если цена с Ozon Картой ниже желаемой рыночной цены,
    увеличиваем базовую цену на разницу.
    """
    if target_market_price is None:
        target_market_price = get_target_market_price()

    if price_with_ozon_card >= target_market_price:
        return None

    difference = target_market_price - price_with_ozon_card
    new_price = current_base_price + difference
    return new_price.quantize(Decimal("1"))


def build_price_updates(
    items: list[dict[str, Any]],
    target_market_price: Optional[Decimal] = None,
) -> list[dict[str, str]]:
    if target_market_price is None:
        target_market_price = get_target_market_price()

    updates: list[dict[str, str]] = []

    for item in items:
        offer_id = item.get("offer_id")
        product_id = item.get("product_id")

        price_with_ozon_card = get_price_with_ozon_card(item)
        current_base_price = get_base_price(item)

        if not offer_id:
            logger.warning("Пропуск товара product_id=%s: отсутствует offer_id", product_id)
            continue

        if price_with_ozon_card is None:
            logger.warning(
                "Пропуск товара offer_id=%s (product_id=%s): нет price_with_ozon_card",
                offer_id,
                product_id,
            )
            continue

        if current_base_price is None:
            logger.warning(
                "Пропуск товара offer_id=%s (product_id=%s): нет базовой цены",
                offer_id,
                product_id,
            )
            continue

        new_price = calculate_new_base_price(
            price_with_ozon_card,
            current_base_price,
            target_market_price=target_market_price,
        )
        if new_price is None:
            logger.info(
                "Товар offer_id=%s: цена с картой %s >= TARGET %s, обновление не требуется",
                offer_id,
                price_with_ozon_card,
                target_market_price,
            )
            continue

        if new_price == current_base_price.quantize(Decimal("1")):
            continue

        logger.info(
            "Товар offer_id=%s: карта=%s, база=%s -> новая база=%s",
            offer_id,
            price_with_ozon_card,
            current_base_price,
            new_price,
        )
        updates.append({"offer_id": offer_id, "price": str(int(new_price))})

    logger.info("Товаров к обновлению: %s", len(updates))
    return updates
