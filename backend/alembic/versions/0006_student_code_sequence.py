"""Add a database sequence backing automatically-generated student codes (Scope B).

A Postgres SEQUENCE gives exactly the guarantees required: nextval() is atomic across concurrent
transactions (two simultaneous student creations can never receive the same value), it is not
transactional (a rolled-back or later-deleted student's number is never handed out again -- the
sequence simply has a permanent gap), and it needs no row locking or retry loop the app has to get
right itself.

The sequence starts one past the highest `TA-NNNNNN`-shaped code already in use, so it continues
the existing numbering instead of colliding with real, currently-assigned codes (requirement:
"continue from the highest permanently allocated number, including deleted records" -- codes
belonging to students already deleted before this migration ran are, unavoidably, unknowable; this
sets the floor as high as it can be determined from what still exists today, and every code issued
after this point is genuinely gap-safe going forward).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS student_code_seq")
    # A sequence's minvalue is 1 -- setval(seq, 0) itself raises, so skip the call entirely on a
    # database with no matching codes yet and just leave the sequence at its default (next
    # nextval() = 1, i.e. TA-000001).
    op.execute(
        """
        DO $$
        DECLARE
            max_code integer;
        BEGIN
            SELECT MAX((substring(student_code FROM 'TA-(\\d{6})$'))::integer) INTO max_code
            FROM users WHERE student_code ~ '^TA-\\d{6}$';
            IF max_code IS NOT NULL THEN
                PERFORM setval('student_code_seq', max_code);
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS student_code_seq")
