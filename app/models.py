from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class GlobalSettings:
    """Схема settings/global из ozon-price-react-native."""

    auto_script_enabled: bool
    target_market_price: Decimal = Decimal("1500")
    markup_percent: Decimal = Decimal("5")
    dry_run: bool = False


@dataclass(frozen=True)
class PipelineResult:
    body: str
    status: str
    updated_count: int = 0
    task_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditLogEntry:
    """Схема audit_logs из ozon-price-react-native."""

    level: str
    message: str
    timestamp_iso: str
    details: str | None = None
