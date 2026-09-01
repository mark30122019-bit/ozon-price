import json
import logging
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OZON_API_BASE_URL = "https://api-seller.ozon.ru"
PRICES_INFO_ENDPOINT = "/v5/product/info/prices"
PRICES_IMPORT_ENDPOINT = "/v1/product/import/prices"

PAGE_LIMIT = 1000
MAX_PAGES = 100
IMPORT_BATCH_SIZE = 1000

# Желаемая рыночная цена для покупателя с Ozon Картой (руб.)
TARGET_MARKET_PRICE = 1500

LOCAL_ENV_FILE = Path(__file__).resolve().parent / ".env"


def load_local_env() -> bool:
    """
    Загружает переменные из локального .env (только если файл существует).

    В Yandex Cloud Functions файл .env обычно отсутствует —
    там используются переменные окружения, заданные в консоли Yandex Cloud.
    Уже установленные переменные не перезаписываются.
    """
    if not LOCAL_ENV_FILE.exists():
        return False

    loaded = 0
    with LOCAL_ENV_FILE.open(encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            key, separator, value = line.partition("=")
            if not separator:
                continue

            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded += 1

    logger.info("Загружено переменных из %s: %s", LOCAL_ENV_FILE.name, loaded)
    return True


def is_dry_run() -> bool:
    return os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}


def get_auth_headers() -> dict[str, str]:
    client_id = os.getenv("OZON_CLIENT_ID")
    api_key = os.getenv("OZON_API_KEY")

    if not client_id or not api_key:
        raise ValueError("Переменные окружения OZON_CLIENT_ID и OZON_API_KEY обязательны")

    return {
        "Client-Id": client_id,
        "Api-Key": api_key,
        "Content-Type": "application/json",
    }


def ozon_post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{OZON_API_BASE_URL}{endpoint}"
    headers = get_auth_headers()

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("Ошибка запроса к Ozon API (%s): %s", endpoint, exc)
        if getattr(exc, "response", None) is not None:
            logger.error("Ответ Ozon: %s", exc.response.text)
        raise


def fetch_all_product_prices() -> list[dict[str, Any]]:
    """Получает все товары с ценами через /v5/product/info/prices с пагинацией."""
    all_items: list[dict[str, Any]] = []
    cursor = ""

    for page_num in range(1, MAX_PAGES + 1):
        payload = {
            "cursor": cursor,
            "limit": PAGE_LIMIT,
            "filter": {"visibility": "ALL"},
        }

        logger.info("Запрос цен, страница %s, cursor=%r", page_num, cursor or "<пусто>")
        data = ozon_post(PRICES_INFO_ENDPOINT, payload)

        items = data.get("items", [])
        all_items.extend(items)
        logger.info("Страница %s: получено %s товаров", page_num, len(items))

        cursor = data.get("cursor") or ""
        if not cursor:
            break
    else:
        logger.warning("Достигнут лимит страниц (%s), пагинация прервана", MAX_PAGES)

    logger.info("Всего найдено товаров: %s", len(all_items))
    return all_items


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
    target_market_price: Decimal = Decimal(TARGET_MARKET_PRICE),
) -> Optional[Decimal]:
    """
    Формула пересчёта базовой цены.

    Если цена с Ozon Картой ниже желаемой рыночной цены,
    увеличиваем базовую цену на разницу.
    """
    if price_with_ozon_card >= target_market_price:
        return None

    difference = target_market_price - price_with_ozon_card
    new_price = current_base_price + difference
    return new_price.quantize(Decimal("1"))


def build_price_updates(items: list[dict[str, Any]]) -> list[dict[str, str]]:
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

        new_price = calculate_new_base_price(price_with_ozon_card, current_base_price)
        if new_price is None:
            logger.info(
                "Товар offer_id=%s: цена с картой %s >= TARGET %s, обновление не требуется",
                offer_id,
                price_with_ozon_card,
                TARGET_MARKET_PRICE,
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


def import_prices(updates: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Отправляет обновления цен батчами на /v1/product/import/prices."""
    responses: list[dict[str, Any]] = []

    for batch_start in range(0, len(updates), IMPORT_BATCH_SIZE):
        batch = updates[batch_start : batch_start + IMPORT_BATCH_SIZE]
        offer_ids = [item["offer_id"] for item in batch]

        logger.info(
            "Отправка батча цен: %s товаров, offer_id=%s",
            len(batch),
            offer_ids,
        )

        data = ozon_post(PRICES_IMPORT_ENDPOINT, {"prices": batch})
        responses.append(data)

        task_id = data.get("result", {}).get("task_id") if isinstance(data.get("result"), dict) else data.get("task_id")
        logger.info("Ответ Ozon на import/prices: %s", json.dumps(data, ensure_ascii=False))
        if task_id is not None:
            logger.info("task_id: %s", task_id)

    return responses


def handler(event, context):
    try:
        logger.info("Старт корректировки цен Ozon")

        items = fetch_all_product_prices()
        if not items:
            body = "Товары не найдены, обновление не выполнялось"
            logger.info(body)
            return {"statusCode": 200, "body": body}

        updates = build_price_updates(items)
        if not updates:
            body = "Цены проверены, обновлений не требуется"
            logger.info(body)
            return {"statusCode": 200, "body": body}

        if is_dry_run():
            body = f"DRY_RUN: обновления не отправлены ({len(updates)} товаров рассчитано)"
            logger.info(body)
            logger.info("Планируемые обновления: %s", json.dumps(updates, ensure_ascii=False))
            return {"statusCode": 200, "body": body}

        import_prices(updates)

        body = f"Цены успешно проверены и обновлены ({len(updates)} товаров)"
        logger.info(body)
        return {"statusCode": 200, "body": body}

    except ValueError as exc:
        logger.error("Ошибка конфигурации: %s", exc)
        return {"statusCode": 500, "body": str(exc)}

    except requests.RequestException as exc:
        logger.error("Сетевая ошибка при работе с Ozon API: %s", exc)
        return {"statusCode": 502, "body": f"Ошибка Ozon API: {exc}"}

    except Exception as exc:
        logger.exception("Непредвиденная ошибка: %s", exc)
        return {"statusCode": 500, "body": f"Внутренняя ошибка: {exc}"}
