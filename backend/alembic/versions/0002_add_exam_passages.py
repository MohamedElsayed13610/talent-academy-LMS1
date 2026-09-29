"""Add exam_passages (Phase 6 passage support): a reading passage belongs to one exam and zero or
more of that exam's questions may link to it via exam_questions.passage_id (ON DELETE SET NULL, so
deleting a passage never deletes its questions).

Written defensively (checks what already exists before creating it) because this repo is still in
its single-squashed-migration phase: a database that ran migration 0001 *before* ExamPassage
existed in app/models/exams.py is missing the table/column outright, while a database recreated
from the current 0001 (e.g. the test suite, which runs Base.metadata.create_all() fresh every
test) already has them structurally and only needs the extra index/trigger that 0001 adds by hand.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Postgres native enums are frozen at creation time -- adding "passage_image" to the Python
    # FilePurpose enum does nothing to an already-created database (caught by actually running
    # this against a real long-lived dev Postgres, not just the test suite, which always creates
    # the enum fresh from the current model). ADD VALUE is a no-op if it's already there (e.g. a
    # database recreated from the current 0001, which already bakes this value in).
    op.execute("ALTER TYPE file_purpose ADD VALUE IF NOT EXISTS 'passage_image'")

    if "exam_passages" not in inspector.get_table_names():
        op.create_table(
            "exam_passages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(180), nullable=False, server_default=""),
            sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("image_file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_exam_passages_exam_id", "exam_passages", ["exam_id"])

    question_columns = {c["name"] for c in inspector.get_columns("exam_questions")}
    if "passage_id" not in question_columns:
        op.add_column("exam_questions", sa.Column("passage_id", sa.Integer(), sa.ForeignKey("exam_passages.id", ondelete="SET NULL"), nullable=True))
        op.create_index("ix_exam_questions_passage_id", "exam_questions", ["passage_id"])

    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_passages_exam_position ON exam_passages (exam_id, position)")

    # File-deletion trigger for exam_passages.image_file_id -- same pattern as the Phase 1 triggers.
    # DROP + CREATE (not just CREATE OR REPLACE, which Postgres doesn't support for triggers) so
    # this is safe to run whether or not 0001 already created it.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION queue_file_deletion_exam_passages_image_file_id() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.image_file_id IS NOT NULL THEN
                    INSERT INTO pending_file_deletions (file_id, bucket, storage_key, reason)
                    SELECT OLD.image_file_id::text, f.bucket, f.storage_key, 'exam_passages.image_file_id delete'
                    FROM files f WHERE f.id = OLD.image_file_id;
                END IF;
                RETURN OLD;
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.image_file_id IS NOT NULL AND OLD.image_file_id IS DISTINCT FROM NEW.image_file_id THEN
                    INSERT INTO pending_file_deletions (file_id, bucket, storage_key, reason)
                    SELECT OLD.image_file_id::text, f.bucket, f.storage_key, 'exam_passages.image_file_id replaced'
                    FROM files f WHERE f.id = OLD.image_file_id;
                END IF;
                RETURN NEW;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_queue_file_deletion_exam_passages_image_file_id ON exam_passages")
    op.execute(
        "CREATE TRIGGER trg_queue_file_deletion_exam_passages_image_file_id AFTER DELETE OR UPDATE OF image_file_id ON exam_passages "
        "FOR EACH ROW EXECUTE FUNCTION queue_file_deletion_exam_passages_image_file_id()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_queue_file_deletion_exam_passages_image_file_id ON exam_passages")
    op.execute("DROP FUNCTION IF EXISTS queue_file_deletion_exam_passages_image_file_id()")
    op.drop_index("ix_exam_questions_passage_id", table_name="exam_questions")
    op.drop_column("exam_questions", "passage_id")
    op.drop_table("exam_passages")
