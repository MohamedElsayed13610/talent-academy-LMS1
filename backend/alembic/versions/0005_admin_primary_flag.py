"""Add admin_profiles.is_primary and backfill it for existing databases.

The earliest-created admin per academy (lowest user id, since users.id is a plain serial and
academies are created before their first admin) becomes primary -- this preserves today's real
admin as the one who can manage other admin accounts, rather than leaving every academy with zero
primary admins after upgrade.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-30
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: on a brand-new database, migration 0001's Base.metadata.create_all() already
    # creates this column straight from the current model (which now declares is_primary) -- only
    # a database that ran 0001 before the model gained this field needs the ALTER.
    op.execute("ALTER TABLE admin_profiles ADD COLUMN IF NOT EXISTS is_primary boolean NOT NULL DEFAULT false")
    op.execute(
        """
        UPDATE admin_profiles SET is_primary = true
        WHERE user_id IN (
            SELECT DISTINCT ON (u.academy_id) u.id
            FROM users u
            WHERE u.role = 'admin'
            ORDER BY u.academy_id, u.id ASC
        )
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE admin_profiles DROP COLUMN IF EXISTS is_primary")
