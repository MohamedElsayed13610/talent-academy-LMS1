"""Repair file-cleanup defaults on databases that already ran migration 0001.

The defaults were added to the SQLAlchemy model and the original squashed migration after the
file-deletion triggers were introduced.  That fixes newly-created databases, but PostgreSQL
databases which had already applied 0001 keep the old columns without defaults.  On those
databases, deleting or replacing an image makes the trigger's partial INSERT fail on a NOT NULL
column and rolls back the parent operation.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN reason SET DEFAULT ''")
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN attempts SET DEFAULT 0")
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN last_error SET DEFAULT ''")
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN next_attempt_at SET DEFAULT now()")
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN created_at SET DEFAULT now()")


def downgrade() -> None:
    # Restores the schema that an already-running pre-fix database had.  New databases created
    # directly from 0001 still retain the model-declared defaults, which is acceptable for this
    # repair migration's downgrade path.
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN reason DROP DEFAULT")
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN attempts DROP DEFAULT")
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN last_error DROP DEFAULT")
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN next_attempt_at DROP DEFAULT")
    op.execute("ALTER TABLE pending_file_deletions ALTER COLUMN created_at DROP DEFAULT")
