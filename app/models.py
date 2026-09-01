from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class GlobalSettings:
    is_active: bool
    site_price_markup_percent: Decimal = Decimal("5")


@dataclass(frozen=True)
class PipelineResult:
    body: str
    status: str
    updated_count: int = 0
    task_ids: list[str] = field(default_factory=list)
    skipped_firestore: bool = False


@dataclass(frozen=True)
class AuditLogEntry:
    status: str
    message: str
    updated_count: int
    task_ids: list[str]
    timestamp_iso: str
