from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.identity import User


def record_audit(
    db: Session,
    *,
    academy_id: int,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Adds an audit_logs row to the current (uncommitted) transaction. The caller commits."""
    ip = ""
    if request is not None:
        ip = request.headers.get("x-forwarded-for", "") or (request.client.host if request.client else "")
    db.add(
        AuditLog(
            academy_id=academy_id,
            actor_id=actor.id if actor else None,
            actor_label=actor.full_name if actor else "",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            summary=summary or {},
            ip=ip[:64],
        )
    )
