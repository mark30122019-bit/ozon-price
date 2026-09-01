import json
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
CATALOG_COLLECTION = "catalog"
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
    """
    Читает settings/global в формате React Native-приложения:
    autoScriptEnabled, targetMarketPrice, markupPercent, dryRun.
    """
    client = db or get_firestore_client()
    snapshot = client.collection(SETTINGS_COLLECTION).document(GLOBAL_SETTINGS_DOCUMENT).get()

    if not snapshot.exists:
        logger.warning("Документ settings/global не найден, скрипт считается отключённым")
        return GlobalSettings(auto_script_enabled=False)

    data = snapshot.to_dict() or {}
    return GlobalSettings(
        auto_script_enabled=bool(data.get("autoScriptEnabled", False)),
        target_market_price=_to_decimal(data.get("targetMarketPrice"), Decimal("1500")),
        markup_percent=_to_decimal(data.get("markupPercent"), Decimal("5")),
        dry_run=bool(data.get("dryRun", False)),
    )


def fetch_catalog_targets(db: Optional[FirestoreClient] = None) -> dict[str, Decimal]:
    """
    Читает catalog/{offerId} в формате React Native-приложения:
    offerId, targetPrice, isActive.
    """
    client = db or get_firestore_client()
    targets: dict[str, Decimal] = {}

    for snapshot in client.collection(CATALOG_COLLECTION).stream():
        data = snapshot.to_dict() or {}
        offer_id = data.get("offerId") or snapshot.id

        if not offer_id:
            logger.warning("Пропуск документа catalog/%s: отсутствует offerId", snapshot.id)
            continue

        if not bool(data.get("isActive", True)):
            logger.info("Пропуск catalog/%s (offerId=%s): isActive=false", snapshot.id, offer_id)
            continue

        target_price = data.get("targetPrice")
        if target_price is None:
            logger.warning(
                "Пропуск catalog/%s (offerId=%s): нет targetPrice",
                snapshot.id,
                offer_id,
            )
            continue

        targets[str(offer_id)] = Decimal(str(target_price))

    logger.info("Загружено целевых цен из catalog: %s товаров", len(targets))
    return targets


def write_audit_log(
    entry: AuditLogEntry,
    db: Optional[FirestoreClient] = None,
) -> str:
    """
    Пишет audit_logs в формате React Native-приложения:
    timestamp, level, message, details.
    """
    client = db or get_firestore_client()
    payload = {
        "timestamp": entry.timestamp_iso,
        "level": entry.level,
        "message": entry.message,
        "details": entry.details,
    }
    _, doc_ref = client.collection(AUDIT_LOGS_COLLECTION).add(payload)
    logger.info("Запись audit_logs/%s сохранена в Firestore", doc_ref.id)
    return doc_ref.id
