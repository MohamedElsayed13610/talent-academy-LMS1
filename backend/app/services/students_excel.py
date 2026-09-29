"""Bulk Excel/CSV import with a per-row validation preview, and Excel export (spec §4, §10;
ARCHITECTURE.md §5.3). Header cells are `"<key>: <English label> / <Arabic label>"` — human-readable
and bilingual as the spec asks, while the leading `<key>` before the colon is what parsing keys off
of, so re-ordered or re-labelled columns still import correctly as long as the key survives.
"""

from __future__ import annotations

import csv
import io
from datetime import timezone

from fastapi import Request
from openpyxl import Workbook, load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.search import normalize_search_text
from app.core.security import generate_password, hash_password
from app.models.identity import GradeLevel, StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.services.audit import record_audit
from app.services.excel_style import write_report_sheet
from app.services.students import generate_student_code
from app.schemas.students import (
    CredentialsRow,
    ImportCommitOut,
    ImportCreatedRow,
    ImportFailedRow,
    ImportRowResult,
    StudentRow,
)

# Scope B import policy (documented + tested in tests/test_students.py): Student ID is optional in
# the import file. A row that supplies one keeps it (validated for format/uniqueness like before --
# this is the backward-compatible path for admins with existing prepared import sheets). A row that
# leaves it blank gets one generated the same way normal creation does (student_code_seq), at
# commit time. Preview never consumes a sequence number for a row that might not end up committed.
COLUMNS: list[tuple[str, str, str, bool]] = [
    # (key, english label, arabic label, required)
    ("student_code", "Student ID (leave blank to auto-generate)", "كود الطالب (اتركه فارغًا للتوليد التلقائي)", False),
    ("full_name", "Full Name", "الاسم الكامل", True),
    ("email", "Email", "البريد الإلكتروني", False),
    ("guardian_phone", "Guardian Phone", "هاتف ولي الأمر", False),
    ("grade_level", "Grade (G10/G11/G12)", "الصف", False),
    ("student_type", "Type (academy/external)", "النوع", False),
    ("subscription_status", "Subscription (active/pending/expired/suspended)", "حالة الاشتراك", False),
]
MAX_ROWS = 2000
MAX_BYTES = 2 * 1024 * 1024


def build_template_workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append([f"{key}: {en} / {ar}" for key, en, ar, _ in COLUMNS])
    ws.append(["", "محمد أحمد", "", "", "G12", "academy", "active"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _header_key(cell_text: str) -> str | None:
    if not cell_text or ":" not in cell_text:
        return None
    key = cell_text.split(":", 1)[0].strip()
    return key if key in {c[0] for c in COLUMNS} else None


def _parse_rows(content: bytes, filename: str) -> list[dict]:
    if len(content) > MAX_BYTES:
        raise ValueError("الملف أكبر من 2 ميجابايت")

    if filename.lower().endswith(".csv"):
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    else:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = [[cell if cell is not None else "" for cell in row] for row in ws.iter_rows(values_only=True)]

    if not rows:
        return []
    header = [_header_key(str(cell)) for cell in rows[0]]
    if "full_name" not in header:
        raise ValueError("رأس الملف غير صحيح — استخدم القالب المتاح للتحميل")

    data_rows = rows[1 : MAX_ROWS + 1]
    result = []
    for raw in data_rows:
        if all(str(cell).strip() == "" for cell in raw):
            continue
        record = {}
        for idx, key in enumerate(header):
            if key and idx < len(raw):
                record[key] = str(raw[idx]).strip() if raw[idx] is not None else ""
        result.append(record)
    return result


def _validate_row(db: Session, academy_id: int, row_no: int, data: dict, seen_codes: set[str], seen_emails: set[str]) -> ImportRowResult:
    errors: list[str] = []
    warnings: list[str] = []

    code = (data.get("student_code") or "").strip().upper() or None
    name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower() or None
    grade = (data.get("grade_level") or "").strip().upper() or None
    student_type = (data.get("student_type") or "academy").strip().lower() or "academy"
    subscription = (data.get("subscription_status") or "active").strip().lower() or "active"

    # Blank is valid and means "auto-generate at commit time" (Scope B import policy above) --
    # only a *provided* code is checked for duplicates/collisions.
    if code:
        if code in seen_codes:
            errors.append(f"Student ID مكرر داخل الملف: {code}")
        elif db.scalar(select(User.id).where(User.academy_id == academy_id, func.upper(User.student_code) == code)):
            errors.append(f"Student ID موجود بالفعل: {code}")
        else:
            seen_codes.add(code)

    if not name or len(name) < 2:
        errors.append("اسم الطالب مطلوب (حرفين على الأقل)")

    if email:
        if email in seen_emails:
            errors.append(f"البريد مكرر داخل الملف: {email}")
        elif db.scalar(select(User.id).where(User.academy_id == academy_id, func.lower(User.email) == email)):
            errors.append(f"البريد مستخدم بالفعل: {email}")
        else:
            seen_emails.add(email)

    if grade and grade not in {"G10", "G11", "G12"}:
        errors.append(f"صف غير صحيح: {grade} (المتاح G10/G11/G12)")
        grade = None
    if student_type not in {"academy", "external"}:
        warnings.append(f"نوع غير معروف '{student_type}' — تم استخدام academy")
        student_type = "academy"
    if subscription not in {"active", "pending", "expired", "suspended"}:
        warnings.append(f"حالة اشتراك غير معروفة '{subscription}' — تم استخدام active")
        subscription = "active"

    normalized = {
        "student_code": code,
        "full_name": name,
        "email": email,
        "guardian_phone": (data.get("guardian_phone") or "").strip(),
        "grade_level": grade,
        "student_type": student_type,
        "subscription_status": subscription,
    }
    return ImportRowResult(row_no=row_no, data=normalized, errors=errors, warnings=warnings)


def preview_import(db: Session, academy_id: int, content: bytes, filename: str) -> list[ImportRowResult]:
    raw_rows = _parse_rows(content, filename)
    seen_codes: set[str] = set()
    seen_emails: set[str] = set()
    return [_validate_row(db, academy_id, i, row, seen_codes, seen_emails) for i, row in enumerate(raw_rows, start=1)]


def commit_import(db: Session, academy_id: int, rows: list[dict], actor: User, request: Request | None) -> ImportCommitOut:
    created: list[ImportCreatedRow] = []
    failed: list[ImportFailedRow] = []
    seen_codes: set[str] = set()
    seen_emails: set[str] = set()

    for i, raw in enumerate(rows, start=1):
        validated = _validate_row(db, academy_id, i, raw, seen_codes, seen_emails)
        if validated.errors:
            failed.append(ImportFailedRow(row_no=i, errors=validated.errors))
            continue
        data = validated.data
        password = generate_password()
        code = data["student_code"] or generate_student_code(db)
        student = User(
            academy_id=academy_id, role=UserRole.student, full_name=data["full_name"],
            full_name_search=normalize_search_text(data["full_name"]), email=data["email"],
            student_code=code, password_hash=hash_password(password), must_change_password=True,
        )
        db.add(student)
        db.flush()
        db.add(StudentProfile(
            user_id=student.id, guardian_phone=data["guardian_phone"],
            grade_level=GradeLevel(data["grade_level"]) if data["grade_level"] else None,
            student_type=StudentType(data["student_type"]), subscription_status=SubscriptionStatus(data["subscription_status"]),
        ))
        created.append(ImportCreatedRow(row_no=i, id=student.id, student_code=student.student_code, full_name=student.full_name, generated_password=password))

    record_audit(db, academy_id=academy_id, actor=actor, action="student.import", entity_type="user", entity_id="bulk", summary={"created": len(created), "failed": len(failed)}, request=request)
    db.commit()
    return ImportCommitOut(created=created, failed=failed)


def build_credentials_workbook(rows: list[CredentialsRow], *, academy_name: str = "Talent Academy") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Credentials"
    write_report_sheet(
        ws, report_title="Newly Imported Student Credentials", headers=["Student ID", "Full Name", "Password"],
        rows=[[row.student_code, row.full_name, row.password] for row in rows],
        academy_name=academy_name, column_widths=[16, 28, 16],
    )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_students_export(rows: list[StudentRow], *, academy_name: str = "Talent Academy") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    headers = ["Student ID", "Full Name", "Email", "Grade", "Type", "Subscription", "Active", "Groups", "Courses", "Points", "Last Login"]
    data = [
        [
            r.student_code or "", r.full_name, r.email or "", r.grade_level or "", r.student_type,
            r.effective_subscription, "Yes" if r.is_active else "No", r.groups_count, r.courses_count,
            r.total_points, r.last_login_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") if r.last_login_at else "",
        ]
        for r in rows
    ]
    totals = ["", f"Total: {len(rows)} students", "", "", "", "", "", "", "", sum(r.total_points for r in rows), ""] if rows else None
    write_report_sheet(
        ws, report_title="Students Export", headers=headers, rows=data, academy_name=academy_name, totals_row=totals,
        column_widths=[14, 24, 26, 8, 10, 12, 8, 9, 9, 9, 16],
    )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
