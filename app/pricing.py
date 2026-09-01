import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

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


def calculate_desired_site_price(
    price_with_ozon_card: Decimal,
    markup_percent: Decimal,
) -> Decimal:
    """Целевая витринная цена: текущая цена на сайте + наценка (%)."""
    multiplier = Decimal("1") + markup_percent / Decimal("100")
    return (price_with_ozon_card * multiplier).quantize(Decimal("1"))


def calculate_new_base_price(
    price_with_ozon_card: Decimal,
    current_base_price: Decimal,
    target_price: Decimal,
    markup_percent: Decimal,
) -> Optional[Decimal]:
    """
    Пересчёт базовой цены для конкретного товара.

    Если цена с Ozon Картой ниже персонального target_price из Firestore,
    поднимаем базовую цену так, чтобы витринная цена выросла на markup_percent
    от текущей цены на сайте.
    """
    if price_with_ozon_card >= target_price:
        return None

    desired_site_price = calculate_desired_site_price(price_with_ozon_card, markup_percent)
    difference = desired_site_price - price_with_ozon_card
    new_price = current_base_price + difference
    return new_price.quantize(Decimal("1"))


def build_price_updates(
    items: list[dict[str, Any]],
    product_targets: Mapping[str, Decimal],
    markup_percent: Decimal,
) -> list[dict[str, str]]:
    """
    Формирует обновления цен только для товаров, присутствующих в Firestore.

    product_targets: offer_id -> target_price из коллекции products.
    """
    updates: list[dict[str, str]] = []

    for item in items:
        offer_id = item.get("offer_id")
        product_id = item.get("product_id")

        if not offer_id:
            logger.warning("Пропуск товара product_id=%s: отсутствует offer_id", product_id)
            continue

        target_price = product_targets.get(str(offer_id))
        if target_price is None:
            logger.warning(
                "Пропуск товара offer_id=%s (product_id=%s): нет в Firestore catalog",
                offer_id,
                product_id,
            )
            continue

        price_with_ozon_card = get_price_with_ozon_card(item)
        current_base_price = get_base_price(item)

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
            target_price=target_price,
            markup_percent=markup_percent,
        )
        if new_price is None:
            logger.info(
                "Товар offer_id=%s: цена с картой %s >= target_price %s, обновление не требуется",
                offer_id,
                price_with_ozon_card,
                target_price,
            )
            continue

        if new_price == current_base_price.quantize(Decimal("1")):
            continue

        desired_site_price = calculate_desired_site_price(price_with_ozon_card, markup_percent)
        logger.info(
            "Товар offer_id=%s: карта=%s, база=%s, target=%s -> цель на сайте=%s (+%s%%) -> новая база=%s",
            offer_id,
            price_with_ozon_card,
            current_base_price,
            target_price,
            desired_site_price,
            markup_percent,
            new_price,
        )
        updates.append({"offer_id": str(offer_id), "price": str(int(new_price))})

    logger.info("Товаров к обновлению: %s", len(updates))
    return updates
