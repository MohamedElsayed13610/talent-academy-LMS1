from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.db.scope import get_default_academy_id
from app.models.courses import Course, CourseAccent
from app.models.groups import Enrollment
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole

# Minimal-but-valid file bytes for magic-byte sniffing (storage_r2.sniff_content_type).
FAKE_PDF = b"%PDF-1.4\n%fake pdf content for tests\n%%EOF"
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _make_course(db_session, *, title="SAT Math — Basics", published=True):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="Math", accent=CourseAccent.blue, is_published=published)
    db_session.add(course)
    db_session.commit()
    return course


def _make_student(db_session, *, code="TA-050001", student_type=StudentType.academy, subscription=SubscriptionStatus.active):
    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name="طالب اختبار", student_code=code, password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, student_type=student_type, subscription_status=subscription))
    db_session.commit()
    return user


def _login_student(client, code, password="Whatever123!"):
    from tests.conftest import AuthedClient

    response = client.post("/api/v1/auth/login", json={"identifier": code, "password": password})
    assert response.status_code == 200, response.text
    return AuthedClient(client)


# --------------------------------------------------------------------- admin course CRUD ----

def test_create_course_and_full_tree(admin_client):
    created = admin_client.post("/api/v1/admin/courses", json={"title": "EST English", "subject": "English"})
    assert created.status_code == 201, created.text
    course_id = created.json()["id"]

    section = admin_client.post(f"/api/v1/admin/courses/{course_id}/sections", json={"title": "Foundations"})
    assert section.status_code == 201
    section_id = section.json()["sections"][0]["id"]

    lesson = admin_client.post(f"/api/v1/admin/sections/{section_id}/lessons", json={"title": "Intro", "duration_minutes": 15})
    assert lesson.status_code == 201
    lesson_id = lesson.json()["sections"][0]["lessons"][0]["id"]

    material = admin_client.post(f"/api/v1/admin/lessons/{lesson_id}/materials", json={"title": "Slides", "material_type": "link", "url": "https://example.com/slides.pdf"})
    assert material.status_code == 201
    tree = material.json()
    assert tree["sections"][0]["lessons"][0]["materials"][0]["title"] == "Slides"
    assert tree["lesson_count"] == 1


def test_course_list_filters_by_published(admin_client, db_session):
    _make_course(db_session, title="Published Course", published=True)
    _make_course(db_session, title="Draft Course", published=False)

    published = admin_client.get("/api/v1/admin/courses?published=true").json()
    assert {c["title"] for c in published} == {"Published Course"}


def test_update_course(admin_client, db_session):
    course = _make_course(db_session)
    response = admin_client.patch(f"/api/v1/admin/courses/{course.id}", json={"title": "Renamed", "is_published": False})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert response.json()["is_published"] is False


def test_reorder_sections_rejects_mismatched_ids(admin_client, db_session):
    course = _make_course(db_session)
    admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "A"})
    admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "B"})
    response = admin_client.put(f"/api/v1/admin/courses/{course.id}/sections/order", json={"ids": [999999]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_MISMATCH"


def test_delete_preview_and_cascade_delete_course(admin_client, db_session):
    course = _make_course(db_session)
    student = _make_student(db_session)
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()
    section = admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "S1"}).json()["sections"][0]
    admin_client.post(f"/api/v1/admin/sections/{section['id']}/lessons", json={"title": "L1"})

    preview = admin_client.get(f"/api/v1/admin/courses/{course.id}/delete-preview")
    assert preview.status_code == 200
    body = preview.json()
    assert body["sections"] == 1
    assert body["lessons"] == 1
    assert body["enrollments"] == 1

    delete = admin_client.delete(f"/api/v1/admin/courses/{course.id}")
    assert delete.status_code == 204
    assert db_session.get(Course, course.id) is None
    assert db_session.query(Enrollment).filter(Enrollment.course_id == course.id).count() == 0


# ----------------------------------------------------------------------------- file upload ----

def test_upload_material_pdf_and_reject_bad_type(admin_client, fake_s3):
    good = admin_client.post(
        "/api/v1/admin/files",
        files={"file": ("worksheet.pdf", FAKE_PDF, "application/pdf")},
        data={"purpose": "material_pdf"},
    )
    assert good.status_code == 201, good.text
    assert good.json()["content_type"] == "application/pdf"

    # A .pdf filename with PNG magic bytes — the declared filename/content-type must never be
    # trusted; only what's actually sniffed from the bytes.
    bad = admin_client.post(
        "/api/v1/admin/files",
        files={"file": ("worksheet.pdf", FAKE_PNG, "application/pdf")},
        data={"purpose": "material_pdf"},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"


def test_upload_oversized_file_rejected(admin_client, fake_s3):
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (3 * 1024 * 1024)  # 3MB > 2MB course_cover limit
    response = admin_client.post(
        "/api/v1/admin/files",
        files={"file": ("cover.png", oversized, "image/png")},
        data={"purpose": "course_cover"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_material_with_uploaded_file_and_signed_download(admin_client, client, db_session, fake_s3):
    upload = admin_client.post("/api/v1/admin/files", files={"file": ("notes.pdf", FAKE_PDF, "application/pdf")}, data={"purpose": "material_pdf"})
    file_id = upload.json()["id"]

    course = _make_course(db_session)
    section = admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "S1"}).json()["sections"][0]
    lesson = admin_client.post(f"/api/v1/admin/sections/{section['id']}/lessons", json={"title": "L1"}).json()["sections"][0]["lessons"][0]
    material = admin_client.post(f"/api/v1/admin/lessons/{lesson['id']}/materials", json={"title": "Notes", "material_type": "file", "file_id": file_id})
    assert material.status_code == 201
    material_id = material.json()["sections"][0]["lessons"][0]["materials"][0]["id"]

    student = _make_student(db_session, code="TA-050080")
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()

    # The student-facing course/lesson payload must carry an already-signed URL, never a bare file_id.
    authed = _login_student(client, "TA-050080")
    lesson_detail = authed.get(f"/api/v1/me/lessons/{lesson['id']}")
    assert lesson_detail.status_code == 200
    signed_material_url = lesson_detail.json()["materials"][0]["url"]
    assert signed_material_url.startswith("https://fake-r2.test/")

    # And the dedicated download endpoint redirects to a signed URL too, with access enforced.
    download = authed.get(f"/api/v1/me/materials/{material_id}/download", follow_redirects=False)
    assert download.status_code == 302
    assert download.headers["location"].startswith("https://fake-r2.test/")

    other_student = _make_student(db_session, code="TA-050081")
    other_authed = _login_student(client, "TA-050081")
    forbidden = other_authed.get(f"/api/v1/me/materials/{material_id}/download", follow_redirects=False)
    assert forbidden.status_code == 403


def test_material_rejects_both_url_and_file_id(admin_client, db_session):
    course = _make_course(db_session)
    section = admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "S1"}).json()["sections"][0]
    lesson = admin_client.post(f"/api/v1/admin/sections/{section['id']}/lessons", json={"title": "L1"}).json()["sections"][0]["lessons"][0]
    response = admin_client.post(f"/api/v1/admin/lessons/{lesson['id']}/materials", json={"title": "Bad", "url": "https://x.com", "file_id": "not-real"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MATERIAL_SOURCE_INVALID"


# ------------------------------------------------------------------------- student access ----

def test_student_only_sees_accessible_published_courses(client, db_session):
    accessible = _make_course(db_session, title="My Course", published=True)
    _make_course(db_session, title="Not Enrolled", published=True)
    _make_course(db_session, title="Unpublished But Enrolled", published=False)
    student = _make_student(db_session, code="TA-050010")
    db_session.add(Enrollment(user_id=student.id, course_id=accessible.id))
    db_session.commit()

    authed = _login_student(client, "TA-050010")
    response = authed.get("/api/v1/me/courses")
    assert response.status_code == 200
    titles = {c["title"] for c in response.json()}
    assert titles == {"My Course"}  # unpublished excluded even though enrolled; not-enrolled excluded


def test_external_expired_student_sees_no_courses(client, db_session):
    course = _make_course(db_session)
    student = _make_student(db_session, code="TA-050020", student_type=StudentType.external, subscription=SubscriptionStatus.expired)
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()

    authed = _login_student(client, "TA-050020")
    response = authed.get("/api/v1/me/courses")
    assert response.status_code == 200
    assert response.json() == []


def test_student_cannot_access_course_detail_without_enrollment(client, db_session):
    course = _make_course(db_session)
    _make_student(db_session, code="TA-050030")
    authed = _login_student(client, "TA-050030")
    response = authed.get(f"/api/v1/me/courses/{course.id}")
    assert response.status_code == 404


def test_lesson_progress_awards_points_idempotently(admin_client, client, db_session):
    course = _make_course(db_session)
    section = admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "S1"}).json()["sections"][0]
    lesson = admin_client.post(f"/api/v1/admin/sections/{section['id']}/lessons", json={"title": "L1"}).json()["sections"][0]["lessons"][0]

    student = _make_student(db_session, code="TA-050040")
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()

    authed = _login_student(client, "TA-050040")
    first = authed.put(f"/api/v1/me/lessons/{lesson['id']}/progress", json={"completed": True})
    assert first.status_code == 200
    assert first.json() == {"completed": True, "points_awarded": 3}

    db_session.refresh(student)
    profile = db_session.get(StudentProfile, student.id)
    assert profile.total_points == 3

    # Marking complete again must not stack points (idempotent ledger, spec §8).
    second = authed.put(f"/api/v1/me/lessons/{lesson['id']}/progress", json={"completed": True})
    assert second.json()["points_awarded"] == 0
    db_session.refresh(profile)
    assert profile.total_points == 3

    # Un-completing removes the points again.
    third = authed.put(f"/api/v1/me/lessons/{lesson['id']}/progress", json={"completed": False})
    assert third.json() == {"completed": False, "points_awarded": 0}
    db_session.refresh(profile)
    assert profile.total_points == 0


def test_student_cannot_mark_progress_without_access(client, db_session):
    course = _make_course(db_session)
    from app.models.courses import Lesson, Section

    section_row = Section(course_id=course.id, title="S1", position=1)
    db_session.add(section_row)
    db_session.flush()
    lesson_row = Lesson(section_id=section_row.id, title="L1")
    db_session.add(lesson_row)
    db_session.commit()

    _make_student(db_session, code="TA-050050")
    authed = _login_student(client, "TA-050050")
    response = authed.put(f"/api/v1/me/lessons/{lesson_row.id}/progress", json={"completed": True})
    assert response.status_code == 403


def test_recorded_lessons_grouped_by_course(admin_client, client, db_session):
    course = _make_course(db_session)
    section = admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "S1"}).json()["sections"][0]
    admin_client.post(f"/api/v1/admin/sections/{section['id']}/lessons", json={"title": "L1"})
    admin_client.post(f"/api/v1/admin/sections/{section['id']}/lessons", json={"title": "L2"})

    student = _make_student(db_session, code="TA-050060")
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()

    authed = _login_student(client, "TA-050060")
    response = authed.get("/api/v1/me/lessons")
    assert response.status_code == 200
    groups = response.json()
    assert len(groups) == 1
    assert groups[0]["course_title"] == course.title
    assert len(groups[0]["lessons"]) == 2


def test_youtube_recording_produces_embed_url(admin_client, client, db_session):
    course = _make_course(db_session)
    section = admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "S1"}).json()["sections"][0]
    lesson = admin_client.post(
        f"/api/v1/admin/sections/{section['id']}/lessons",
        json={"title": "L1", "recording_url": "https://www.youtube.com/watch?v=abc123XYZ"},
    ).json()["sections"][0]["lessons"][0]

    student = _make_student(db_session, code="TA-050070")
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()

    authed = _login_student(client, "TA-050070")
    response = authed.get(f"/api/v1/me/lessons/{lesson['id']}")
    assert response.status_code == 200
    recording = response.json()["recording"]
    assert recording["kind"] == "youtube"
    assert recording["embed_url"] == "https://www.youtube-nocookie.com/embed/abc123XYZ"


def test_deleting_a_material_with_an_uploaded_file_queues_cleanup(admin_client, db_session, fake_s3):
    # Regression: pending_file_deletions.attempts/last_error/reason lacked a DB-level default, so
    # the file-deletion trigger's raw-SQL INSERT (which only sets file_id/bucket/storage_key/reason)
    # violated NOT NULL -- and in Postgres, a failing trigger rolls back the entire statement that
    # fired it, not just the insert. Every delete of a row with a file reference (lesson_materials,
    # exam_questions, courses, academy_settings) was silently failing outright since Phase 1; this
    # was never caught because no earlier test attached a real file to what it deleted.
    upload = admin_client.post("/api/v1/admin/files", files={"file": ("notes.pdf", FAKE_PDF, "application/pdf")}, data={"purpose": "material_pdf"})
    file_id = upload.json()["id"]

    course = _make_course(db_session)
    section = admin_client.post(f"/api/v1/admin/courses/{course.id}/sections", json={"title": "S1"}).json()["sections"][0]
    lesson = admin_client.post(f"/api/v1/admin/sections/{section['id']}/lessons", json={"title": "L1"}).json()["sections"][0]["lessons"][0]
    material = admin_client.post(f"/api/v1/admin/lessons/{lesson['id']}/materials", json={"title": "Notes", "material_type": "file", "file_id": file_id})
    material_id = material.json()["sections"][0]["lessons"][0]["materials"][0]["id"]

    from app.models.files import PendingFileDeletion

    response = admin_client.delete(f"/api/v1/admin/materials/{material_id}")
    assert response.status_code == 200, response.text
    assert response.json()["sections"][0]["lessons"][0]["materials"] == []
    assert db_session.query(PendingFileDeletion).filter(PendingFileDeletion.file_id == file_id).count() == 1
