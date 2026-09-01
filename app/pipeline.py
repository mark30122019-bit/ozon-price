import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.env import is_dry_run
from app.firestore_service import fetch_catalog_targets, fetch_global_settings, write_audit_log
from app.models import AuditLogEntry, GlobalSettings, PipelineResult
from app.ozon_client import OzonClient
from app.prices_service import extract_task_ids, fetch_all_product_prices, import_prices
from app.pricing import build_price_updates

logger = logging.getLogger(__name__)

DISABLED_MESSAGE = "Скрипт отключен пользователем через мобильное приложение"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _should_dry_run(settings: GlobalSettings) -> bool:
    """DRY_RUN из env имеет приоритет над settings.dryRun (для локальной отладки)."""
    return is_dry_run() or settings.dry_run


def _write_audit(
    level: str,
    message: str,
    details: Optional[dict] = None,
) -> None:
    write_audit_log(
        AuditLogEntry(
            level=level,
            message=message,
            timestamp_iso=_utc_now_iso(),
            details=json.dumps(details, ensure_ascii=False) if details else None,
        )
    )


def run_price_adjustment() -> PipelineResult:
    logger.info("Старт корректировки цен Ozon")

    settings = fetch_global_settings()
    if not settings.auto_script_enabled:
        logger.info(DISABLED_MESSAGE)
        _write_audit(level="info", message=DISABLED_MESSAGE)
        return PipelineResult(body=DISABLED_MESSAGE, status="disabled")

    catalog_targets = fetch_catalog_targets()
    if not catalog_targets:
        body = "В Firestore catalog нет активных товаров с targetPrice"
        logger.warning(body)
        _write_audit(level="warning", message=body)
        return PipelineResult(body=body, status="noop")

    client = OzonClient.from_env()
    items = fetch_all_product_prices(client)

    if not items:
        body = "Товары не найдены в Ozon, обновление не выполнялось"
        logger.info(body)
        _write_audit(level="info", message=body)
        return PipelineResult(body=body, status="noop")

    updates = build_price_updates(
        items,
        product_targets=catalog_targets,
        markup_percent=settings.markup_percent,
    )
    if not updates:
        body = "Цены проверены, обновлений не требуется"
        logger.info(body)
        _write_audit(level="info", message=body)
        return PipelineResult(body=body, status="noop")

    if _should_dry_run(settings):
        body = f"DRY_RUN: обновления не отправлены ({len(updates)} товаров рассчитано)"
        logger.info(body)
        logger.info("Планируемые обновления: %s", json.dumps(updates, ensure_ascii=False))
        _write_audit(
            level="info",
            message=body,
            details={"updated_count": len(updates), "updates": updates},
        )
        return PipelineResult(
            body=body,
            status="dry_run",
            updated_count=len(updates),
        )

    responses = import_prices(client, updates)
    task_ids = extract_task_ids(responses)

    body = f"Цены успешно проверены и обновлены ({len(updates)} товаров)"
    logger.info(body)
    _write_audit(
        level="success",
        message=body,
        details={"updated_count": len(updates), "task_ids": task_ids},
    )
    return PipelineResult(
        body=body,
        status="success",
        updated_count=len(updates),
        task_ids=task_ids,
    )
