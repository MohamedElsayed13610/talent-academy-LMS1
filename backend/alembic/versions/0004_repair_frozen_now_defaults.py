"""Repair frozen `now()` server defaults left over from a stale 0001 run.

Discovered while building the Phase 9 admin audit log: every column across this database that
declares `server_default="now()"` (a plain Python string, not `sa.text("now()")`) has a column
default in Postgres that is a *literal* timestamp baked in at whatever instant this database's
migration 0001 first ran, not the live `now()` function -- so every row ever inserted through the
ORM's server-side default on these columns shares the exact same microsecond-precision timestamp
(confirmed directly against this database: 15 columns across 12 tables, all defaulting to the
identical frozen instant). This is the same class of drift migration 0003 already repaired for
`pending_file_deletions` (a database that already ran 0001 keeps whatever the column looked like
at that time, even after the model source changes later) -- this migration sweeps up every other
column left with the same problem.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("announcement_reads", "read_at"),
    ("attendance_records", "updated_at"),
    ("audit_logs", "created_at"),
    ("auth_sessions", "created_at"),
    ("enrollments", "created_at"),
    ("exam_answers", "answered_at"),
    ("exam_attempt_events", "created_at"),
    ("exam_attempts", "created_at"),
    ("exam_attempts", "started_at"),
    ("files", "created_at"),
    ("group_course_enrollments", "created_at"),
    ("group_memberships", "created_at"),
    ("lesson_progress", "updated_at"),
    ("point_ledger", "created_at"),
    ("point_ledger", "updated_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT now()")


def downgrade() -> None:
    # Mirrors 0003's downgrade: restores "no default" rather than the frozen literal, since the
    # literal was never a value anyone should reintroduce on purpose.
    for table, column in _COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
