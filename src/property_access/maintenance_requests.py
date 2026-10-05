from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID, uuid4


class MaintenancePriority(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"


@dataclass(frozen=True)
class TenantDocument:
    name: str
    reference: str


@dataclass(frozen=True)
class MaintenanceRequest:
    request_id: UUID
    tenant_phone: str
    unit: str
    summary: str
    priority: MaintenancePriority
    documents: tuple[TenantDocument, ...]
    inspection_reminder_at: datetime


def open_maintenance_request(
    *,
    tenant_phone: str,
    unit: str,
    summary: str,
    priority: MaintenancePriority,
    documents: tuple[TenantDocument, ...],
    verified_at: datetime,
) -> MaintenanceRequest:
    """Turn a verified tenant identity into a scheduled maintenance request."""
    reminder_delay = timedelta(hours=2) if priority is MaintenancePriority.URGENT else timedelta(days=2)
    return MaintenanceRequest(
        request_id=uuid4(),
        tenant_phone=tenant_phone,
        unit=unit,
        summary=summary,
        priority=priority,
        documents=documents,
        inspection_reminder_at=verified_at.astimezone(timezone.utc) + reminder_delay,
    )

