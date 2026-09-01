import json
import logging
from typing import Any

from app.config import (
    IMPORT_BATCH_SIZE,
    MAX_PAGES,
    PAGE_LIMIT,
    PRICES_IMPORT_ENDPOINT,
    PRICES_INFO_ENDPOINT,
)
from app.ozon_client import OzonClient

logger = logging.getLogger(__name__)


def fetch_all_product_prices(client: OzonClient) -> list[dict[str, Any]]:
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
        data = client.post(PRICES_INFO_ENDPOINT, payload)

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


def import_prices(client: OzonClient, updates: list[dict[str, str]]) -> list[dict[str, Any]]:
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

        data = client.post(PRICES_IMPORT_ENDPOINT, {"prices": batch})
        responses.append(data)

        task_id = (
            data.get("result", {}).get("task_id")
            if isinstance(data.get("result"), dict)
            else data.get("task_id")
        )
        logger.info("Ответ Ozon на import/prices: %s", json.dumps(data, ensure_ascii=False))
        if task_id is not None:
            logger.info("task_id: %s", task_id)

    return responses


def extract_task_ids(responses: list[dict[str, Any]]) -> list[str]:
    task_ids: list[str] = []

    for data in responses:
        task_id = (
            data.get("result", {}).get("task_id")
            if isinstance(data.get("result"), dict)
            else data.get("task_id")
        )
        if task_id is not None:
            task_ids.append(str(task_id))

    return task_ids
