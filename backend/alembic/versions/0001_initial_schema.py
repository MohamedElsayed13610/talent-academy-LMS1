"""Initial schema: all tables from docs/ARCHITECTURE.md §2, plus partial indexes, trigram search
indexes, and the file-deletion triggers described in §2.1/§3.

Revision ID: 0001
Revises:
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa

from app.db.base import Base
import app.models  # noqa: F401

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- All tables, from the SQLAlchemy models (first migration only; every later change is a
    # normal explicit Alembic migration, per docs/ARCHITECTURE.md §11 row 59 / spec §14.3). ---
    Base.metadata.create_all(bind=bind, checkfirst=False)

    # --- Partial-unique indexes (can't be expressed with SQLAlchemy's declarative UniqueConstraint) ---
    op.execute(
        "CREATE UNIQUE INDEX uq_users_academy_student_code "
        "ON users (academy_id, student_code) WHERE student_code IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_users_academy_email "
        "ON users (academy_id, email) WHERE email IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_exam_choices_one_correct "
        "ON exam_choices (question_id) WHERE is_correct"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_exam_attempts_open "
        "ON exam_attempts (exam_id, user_id) WHERE status IN ('granted', 'in_progress', 'locked')"
    )

    # --- CHECK constraints ---
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role_identifier CHECK ("
        "  (role <> 'student' OR student_code IS NOT NULL) AND"
        "  (role <> 'admin' OR email IS NOT NULL)"
        ")"
    )
    op.execute(
        "ALTER TABLE lesson_materials ADD CONSTRAINT ck_material_one_source CHECK ("
        "  (url IS NOT NULL AND file_id IS NULL) OR (url IS NULL AND file_id IS NOT NULL)"
        ")"
    )
    op.execute(
        "ALTER TABLE live_sessions ADD CONSTRAINT ck_live_session_times CHECK (ends_at > starts_at)"
    )

    # --- Trigram search indexes (Arabic-normalised *_search columns, populated by the app layer) ---
    op.execute("CREATE INDEX ix_users_full_name_search_trgm ON users USING gin (full_name_search gin_trgm_ops)")
    op.execute("CREATE INDEX ix_users_student_code_trgm ON users USING gin (student_code gin_trgm_ops)")
    op.execute("CREATE INDEX ix_groups_name_search_trgm ON student_groups USING gin (name_search gin_trgm_ops)")
    op.execute("CREATE INDEX ix_courses_title_search_trgm ON courses USING gin (title_search gin_trgm_ops)")

    # --- Extra composite indexes named in ARCHITECTURE.md §2.2 not already covered by a FK/unique index ---
    op.execute("CREATE INDEX ix_users_academy_role_active ON users (academy_id, role, is_active)")
    op.execute("CREATE INDEX ix_student_profiles_type_subscription ON student_profiles (student_type, subscription_status)")
    op.execute("CREATE INDEX ix_student_profiles_total_points ON student_profiles (total_points DESC)")
    op.execute("CREATE INDEX ix_lesson_progress_user_completed ON lesson_progress (user_id, completed)")
    op.execute("CREATE INDEX ix_live_sessions_course_starts ON live_sessions (course_id, starts_at)")
    op.execute("CREATE INDEX ix_attendance_user_session ON attendance_records (user_id, live_session_id)")
    op.execute("CREATE INDEX ix_attendance_session_status ON attendance_records (live_session_id, status)")
    op.execute("CREATE INDEX ix_exams_course_published ON exams (course_id, is_published)")
    op.execute("CREATE INDEX ix_exam_attempts_user_exam ON exam_attempts (user_id, exam_id)")
    op.execute("CREATE INDEX ix_exam_attempts_exam_status ON exam_attempts (exam_id, status)")
    op.execute("CREATE INDEX ix_exam_attempts_status_expires ON exam_attempts (status, expires_at)")
    op.execute("CREATE INDEX ix_exam_attempt_events_attempt_created ON exam_attempt_events (attempt_id, created_at)")
    op.execute("CREATE INDEX ix_point_ledger_user_created ON point_ledger (user_id, created_at DESC)")
    op.execute("CREATE INDEX ix_point_ledger_source ON point_ledger (source_type, source_id)")
    op.execute("CREATE INDEX ix_point_ledger_course_user ON point_ledger (course_id, user_id)")
    op.execute("CREATE INDEX ix_announcements_academy_active_created ON announcements (academy_id, is_active, created_at DESC)")
    op.execute("CREATE INDEX ix_pending_file_deletions_next_attempt ON pending_file_deletions (next_attempt_at)")
    op.execute("CREATE INDEX ix_audit_logs_entity ON audit_logs (entity_type, entity_id)")
    op.execute("CREATE INDEX ix_audit_logs_created ON audit_logs (created_at DESC)")

    # --- File-deletion triggers (ARCHITECTURE.md §2.1: queue the R2 object whenever a referencing
    # row is deleted or its file column is replaced, including via a CASCADE delete). One small
    # trigger function per (table, column) pair — simpler and fully correct than a single generic
    # function trying to read a dynamic column name inside PL/pgSQL. ---
    def _file_trigger(table: str, column: str) -> None:
        func_name = f"queue_file_deletion_{table}_{column}"
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {func_name}() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.{column} IS NOT NULL THEN
                        INSERT INTO pending_file_deletions (file_id, bucket, storage_key, reason)
                        SELECT OLD.{column}::text, f.bucket, f.storage_key, '{table}.{column} delete'
                        FROM files f WHERE f.id = OLD.{column};
                    END IF;
                    RETURN OLD;
                ELSIF TG_OP = 'UPDATE' THEN
                    IF OLD.{column} IS NOT NULL AND OLD.{column} IS DISTINCT FROM NEW.{column} THEN
                        INSERT INTO pending_file_deletions (file_id, bucket, storage_key, reason)
                        SELECT OLD.{column}::text, f.bucket, f.storage_key, '{table}.{column} replaced'
                        FROM files f WHERE f.id = OLD.{column};
                    END IF;
                    RETURN NEW;
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"CREATE TRIGGER trg_{func_name} AFTER DELETE OR UPDATE OF {column} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {func_name}()"
        )

    _file_trigger("lesson_materials", "file_id")
    _file_trigger("exam_questions", "image_file_id")
    _file_trigger("courses", "cover_file_id")
    _file_trigger("academy_settings", "logo_file_id")

    # --- Seed the single academy row + default settings (spec §2: one seeded row) ---
    # Bound as a real parameter (not string-interpolated SQL) so the colons inside the JSON text
    # are never mistaken for sa.text() bind-parameter markers.
    import json

    op.execute(
        "INSERT INTO academies (name, slug, created_at, updated_at) "
        "VALUES ('Talent Academy', 'talent-academy', now(), now())"
    )
    point_values_json = json.dumps({
        "lesson_complete": 3, "attendance_manual": 5, "attendance_on_time": 7, "attendance_late": 2,
        "exam_submit": 5, "exam_60_79": 5, "exam_80_89": 10, "exam_90_99": 15, "exam_100": 20,
    })
    bind.execute(
        sa.text(
            "INSERT INTO academy_settings (academy_id, display_name, primary_color, accent_color, "
            "whatsapp_url, point_values, late_threshold_minutes, violation_limit, "
            "join_open_minutes_before, exam_submit_grace_seconds) "
            "SELECT id, 'Talent Academy', '#1a5ad9', '#d99f1f', '', "
            "CAST(:point_values AS jsonb), 10, 2, 15, 30 FROM academies"
        ),
        {"point_values": point_values_json},
    )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
