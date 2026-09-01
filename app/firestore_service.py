import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from google.cloud.firestore_v1 import Client as FirestoreClient

from app.env import get_firestore_client
from app.models import AuditLogEntry, GlobalSettings

logger = logging.getLogger(__name__)

SETTINGS_COLLECTION = "settings"
GLOBAL_SETTINGS_DOCUMENT = "global"
PRODUCTS_COLLECTION = "products"
AUDIT_LOGS_COLLECTION = "audit_logs"


def _to_decimal(value: object, default: Decimal) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        logger.warning("Некорректное числовое значение %r, используется %s", value, default)
        return default


def fetch_global_settings(db: Optional[FirestoreClient] = None) -> GlobalSettings:
    client = db or get_firestore_client()
    snapshot = client.collection(SETTINGS_COLLECTION).document(GLOBAL_SETTINGS_DOCUMENT).get()

    if not snapshot.exists:
        logger.warning("Документ settings/global не найден, скрипт считается отключённым")
        return GlobalSettings(is_active=False)

    data = snapshot.to_dict() or {}
    return GlobalSettings(
        is_active=bool(data.get("is_active", False)),
        site_price_markup_percent=_to_decimal(data.get("site_price_markup_percent"), Decimal("5")),
    )


def fetch_product_targets(db: Optional[FirestoreClient] = None) -> dict[str, Decimal]:
    client = db or get_firestore_client()
    targets: dict[str, Decimal] = {}

    for snapshot in client.collection(PRODUCTS_COLLECTION).stream():
        data = snapshot.to_dict() or {}
        offer_id = data.get("offer_id") or snapshot.id
        target_price = data.get("target_price")

        if not offer_id:
            logger.warning("Пропуск документа products/%s: отсутствует offer_id", snapshot.id)
            continue

        if target_price is None:
            logger.warning("Пропуск products/%s (offer_id=%s): нет target_price", snapshot.id, offer_id)
            continue

        targets[str(offer_id)] = Decimal(str(target_price))

    logger.info("Загружено целевых цен из Firestore: %s товаров", len(targets))
    return targets


def write_audit_log(
    entry: AuditLogEntry,
    db: Optional[FirestoreClient] = None,
) -> str:
    client = db or get_firestore_client()
    payload = {
        "timestamp": entry.timestamp_iso,
        "status": entry.status,
        "message": entry.message,
        "updated_count": entry.updated_count,
        "task_ids": entry.task_ids,
        "created_at": datetime.now(timezone.utc),
    }
    _, doc_ref = client.collection(AUDIT_LOGS_COLLECTION).add(payload)
    logger.info("Запись audit_logs/%s сохранена в Firestore", doc_ref.id)
    return doc_ref.id
