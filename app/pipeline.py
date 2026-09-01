import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.env import is_dry_run
from app.firestore_service import fetch_global_settings, fetch_product_targets, write_audit_log
from app.models import AuditLogEntry, PipelineResult
from app.ozon_client import OzonClient
from app.prices_service import extract_task_ids, fetch_all_product_prices, import_prices
from app.pricing import build_price_updates

logger = logging.getLogger(__name__)

DISABLED_MESSAGE = "Скрипт отключен пользователем через мобильное приложение"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_audit(
    status: str,
    message: str,
    updated_count: int = 0,
    task_ids: Optional[list[str]] = None,
) -> None:
    write_audit_log(
        AuditLogEntry(
            status=status,
            message=message,
            updated_count=updated_count,
            task_ids=task_ids or [],
            timestamp_iso=_utc_now_iso(),
        )
    )


def run_price_adjustment() -> PipelineResult:
    logger.info("Старт корректировки цен Ozon")

    settings = fetch_global_settings()
    if not settings.is_active:
        logger.info(DISABLED_MESSAGE)
        _write_audit(status="disabled", message=DISABLED_MESSAGE)
        return PipelineResult(
            body=DISABLED_MESSAGE,
            status="disabled",
            skipped_firestore=False,
        )

    product_targets = fetch_product_targets()
    if not product_targets:
        body = "В Firestore нет товаров с target_price, обновление не выполнялось"
        logger.warning(body)
        _write_audit(status="noop", message=body)
        return PipelineResult(body=body, status="noop")

    client = OzonClient.from_env()
    items = fetch_all_product_prices(client)

    if not items:
        body = "Товары не найдены в Ozon, обновление не выполнялось"
        logger.info(body)
        _write_audit(status="noop", message=body)
        return PipelineResult(body=body, status="noop")

    updates = build_price_updates(
        items,
        product_targets=product_targets,
        markup_percent=settings.site_price_markup_percent,
    )
    if not updates:
        body = "Цены проверены, обновлений не требуется"
        logger.info(body)
        _write_audit(status="noop", message=body)
        return PipelineResult(body=body, status="noop")

    if is_dry_run():
        body = f"DRY_RUN: обновления не отправлены ({len(updates)} товаров рассчитано)"
        logger.info(body)
        logger.info("Планируемые обновления: %s", json.dumps(updates, ensure_ascii=False))
        _write_audit(status="dry_run", message=body, updated_count=len(updates))
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
        status="success",
        message=body,
        updated_count=len(updates),
        task_ids=task_ids,
    )
    return PipelineResult(
        body=body,
        status="success",
        updated_count=len(updates),
        task_ids=task_ids,
    )
