"""Academy scoping helper (ARCHITECTURE.md §2: 'All queries on root tables go through one helper').

The platform is single-academy for now (spec §2), but every root table already carries academy_id so
teacher/parent roles and, eventually, more academies need no restructuring later.
"""

from __future__ import annotations

from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.models.academy import Academy

_DEFAULT_ACADEMY_ID: int | None = None


def get_default_academy_id(db: Session) -> int:
    global _DEFAULT_ACADEMY_ID
    if _DEFAULT_ACADEMY_ID is None:
        academy = db.query(Academy).order_by(Academy.id).first()
        if not academy:
            raise RuntimeError("No academy row found. Run migrations/seed before starting the app.")
        _DEFAULT_ACADEMY_ID = academy.id
    return _DEFAULT_ACADEMY_ID


def scoped(stmt: Select, model: type, academy_id: int) -> Select:
    """Add `model.academy_id == academy_id` to a select statement."""
    return stmt.where(model.academy_id == academy_id)
