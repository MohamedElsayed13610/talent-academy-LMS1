"""Widen exam_answers.client_seq from integer to bigint, as docs/ARCHITECTURE.md specifies.

On a brand-new database, migration 0001's Base.metadata.create_all() already creates this column
as bigint straight from the current model; ALTER ... TYPE bigint on a column that is already bigint
is a harmless no-op, so this is safe on both new and existing databases.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-25
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE exam_answers ALTER COLUMN client_seq TYPE bigint")


def downgrade() -> None:
    # Fails loudly if any stored value no longer fits in an integer, instead of truncating it.
    op.execute("ALTER TABLE exam_answers ALTER COLUMN client_seq TYPE integer")
