from datetime import timedelta

from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.models.academy import Academy, AcademySettings
from app.models.audit import AuditLog
from app.models.courses import Course, CourseAccent
from app.models.exams import ChoiceLabel, Exam, ExamAttempt, ExamChoice, ExamMode, ExamQuestion, QuestionType
from app.models.files import PendingFileDeletion
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.models.points import PointLedger, PointSource

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
FAKE_JPEG = b"\xff\xd8\xff" + b"\x00" * 32


def _make_course(db_session, title="ACT Math"):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="Math", accent=CourseAccent.blue, is_published=True)
    db_session.add(course)
    db_session.commit()
    return course


def _create_exam_via_api(admin_client, course_id, **overrides):
    payload = {
        "title": "Unit 1 Test", "course_id": course_id, "exam_mode": "answer_sheet",
        "duration_minutes": 30, "passing_score": 50, "max_attempts": 1,
    }
    payload.update(overrides)
    response = admin_client.post("/api/v1/admin/exams", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _add_text_question(admin_client, exam_id, correct="A", points=1):
    payload = {
        "question_type": "text_mcq", "prompt_text": "2 + 2 = ?",
        "choices": [{"label": "A", "text": "4"}, {"label": "B", "text": "3"}, {"label": "C", "text": "5"}, {"label": "D", "text": "6"}],
        "correct_label": correct, "topic": "Arithmetic", "difficulty": "easy", "points": points,
    }
    response = admin_client.post(f"/api/v1/admin/exams/{exam_id}/questions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------------------------------- exam CRUD ----

def test_create_exam_as_draft(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    assert exam["is_published"] is False
    assert exam["state"] == "draft"
    assert exam["question_count"] == 0
    assert exam["has_attempts"] is False


def test_create_exam_rejects_unknown_course(admin_client):
    response = admin_client.post("/api/v1/admin/exams", json={"title": "Unknown Course Exam", "course_id": 999999, "duration_minutes": 30})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "COURSE_NOT_FOUND"


def test_create_exam_rejects_invalid_time_range(admin_client, db_session):
    course = _make_course(db_session)
    now = utcnow()
    response = admin_client.post("/api/v1/admin/exams", json={
        "title": "Invalid Time Range Exam", "course_id": course.id, "duration_minutes": 30,
        "starts_at": now.isoformat(), "ends_at": (now - timedelta(hours=1)).isoformat(),
    })
    assert response.status_code == 422


def test_update_exam(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    response = admin_client.patch(f"/api/v1/admin/exams/{exam['id']}", json={"title": "Renamed", "passing_score": 70})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert response.json()["passing_score"] == 70


def test_anonymous_and_student_cannot_access_admin_exams(client, db_session):
    course = _make_course(db_session)
    academy_id = get_default_academy_id(db_session)
    student = User(academy_id=academy_id, role=UserRole.student, full_name="S", student_code="TA-070001", password_hash=hash_password("Whatever123!"))
    db_session.add(student)
    db_session.flush()
    db_session.add(StudentProfile(user_id=student.id, student_type=StudentType.academy, subscription_status=SubscriptionStatus.active))
    db_session.commit()

    anon = client.get("/api/v1/admin/exams")
    assert anon.status_code == 401

    client.post("/api/v1/auth/login", json={"identifier": "TA-070001", "password": "Whatever123!"})
    as_student = client.get("/api/v1/admin/exams")
    assert as_student.status_code == 403


def test_cross_academy_exam_returns_404(admin_client, db_session):
    other_academy = Academy(name="Other Academy", slug="other-academy")
    db_session.add(other_academy)
    db_session.flush()
    db_session.add(AcademySettings(academy_id=other_academy.id))
    other_course = Course(academy_id=other_academy.id, title="Other Course", title_search="other course", subject="X", accent=CourseAccent.gold)
    db_session.add(other_course)
    db_session.flush()
    other_exam = Exam(academy_id=other_academy.id, course_id=other_course.id, title="Other Exam", exam_mode=ExamMode.answer_sheet)
    db_session.add(other_exam)
    db_session.commit()

    response = admin_client.get(f"/api/v1/admin/exams/{other_exam.id}")
    assert response.status_code == 404


def test_exam_state_filter(admin_client, db_session):
    course = _make_course(db_session)
    now = utcnow()
    draft = _create_exam_via_api(admin_client, course.id, title="Draft Exam")

    upcoming = _create_exam_via_api(admin_client, course.id, title="Upcoming Exam", starts_at=(now + timedelta(days=1)).isoformat(), ends_at=(now + timedelta(days=2)).isoformat())
    _add_text_question(admin_client, upcoming["id"])
    admin_client.post(f"/api/v1/admin/exams/{upcoming['id']}/publish")

    available = _create_exam_via_api(admin_client, course.id, title="Available Exam")
    _add_text_question(admin_client, available["id"])
    admin_client.post(f"/api/v1/admin/exams/{available['id']}/publish")

    draft_list = admin_client.get("/api/v1/admin/exams?state=draft").json()["items"]
    assert {e["title"] for e in draft_list} == {"Draft Exam"}

    upcoming_list = admin_client.get("/api/v1/admin/exams?state=upcoming").json()["items"]
    assert {e["title"] for e in upcoming_list} == {"Upcoming Exam"}

    available_list = admin_client.get("/api/v1/admin/exams?state=available").json()["items"]
    assert {e["title"] for e in available_list} == {"Available Exam"}


# ------------------------------------------------------------------------------ publishing ----

def test_publish_blocked_without_questions(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    response = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/publish")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXAM_NOT_READY"
    assert response.json()["error"]["details"]["question_numbers"] == []


def test_publish_blocked_when_question_missing_correct_answer(admin_client, db_session):
    # Every real creation path (manual question, image upload, answer-key apply) enforces
    # exactly-one-correct-choice by construction, so the only way to reach this state is a direct
    # DB anomaly -- exactly what this test simulates, to prove publish still catches it.
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    detail = _add_text_question(admin_client, exam["id"])
    question_id = detail["questions"][0]["id"]

    question = db_session.get(ExamQuestion, question_id)
    for choice in question.choices:
        choice.is_correct = False
    db_session.commit()

    response = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/publish")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXAM_NOT_READY"
    assert response.json()["error"]["details"]["question_numbers"] == [1]


def test_publish_succeeds_with_valid_question_and_unpublish_works(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])

    published = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/publish")
    assert published.status_code == 200
    assert published.json()["is_published"] is True
    assert published.json()["published_at"] is not None

    unpublished = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/unpublish")
    assert unpublished.status_code == 200
    assert unpublished.json()["is_published"] is False


# -------------------------------------------------------------------------------- questions ----

def test_add_text_question_and_reorder(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    q1 = _add_text_question(admin_client, exam["id"])
    q2 = _add_text_question(admin_client, exam["id"])
    ids = [q["id"] for q in q2["questions"]]
    assert len(ids) == 2

    reordered = admin_client.put(f"/api/v1/admin/exams/{exam['id']}/questions/order", json={"ids": list(reversed(ids))})
    assert reordered.status_code == 200
    positions = {q["id"]: q["position"] for q in reordered.json()["questions"]}
    assert positions[ids[0]] == 2
    assert positions[ids[1]] == 1


def test_reorder_rejects_mismatched_ids(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    response = admin_client.put(f"/api/v1/admin/exams/{exam['id']}/questions/order", json={"ids": [999999]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_MISMATCH"


def test_delete_question_closes_position_gap(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _add_text_question(admin_client, exam["id"])
    detail = _add_text_question(admin_client, exam["id"])
    questions = sorted(detail["questions"], key=lambda q: q["position"])
    assert [q["position"] for q in questions] == [1, 2, 3]

    delete_response = admin_client.delete(f"/api/v1/admin/questions/{questions[0]['id']}")
    assert delete_response.status_code == 200
    remaining = sorted(delete_response.json()["questions"], key=lambda q: q["position"])
    assert [q["position"] for q in remaining] == [1, 2]


def test_text_question_choices_must_cover_a_to_d(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    response = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/questions", json={
        "question_type": "text_mcq", "prompt_text": "Bad", "correct_label": "A",
        "choices": [{"label": "A", "text": "x"}, {"label": "B", "text": "y"}, {"label": "A", "text": "z"}, {"label": "D", "text": "w"}],
    })
    assert response.status_code == 422


# --------------------------------------------------------------------------- image upload ----

def test_upload_question_images_natural_sort_and_validation(admin_client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)

    files = [
        ("q10.png", FAKE_PNG, "image/png"),
        ("q1.png", FAKE_PNG, "image/png"),
        ("q2.jpg", FAKE_JPEG, "image/jpeg"),
    ]
    response = admin_client.post(
        f"/api/v1/admin/exams/{exam['id']}/question-images",
        files=[("files", f) for f in files],
        data={"topic": "Geometry", "difficulty": "hard", "points": "2"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["exam_mode"] == "full"
    questions = sorted(body["questions"], key=lambda q: q["position"])
    assert len(questions) == 3
    # Natural sort: q1, q2, q10 -- not lexical q1, q10, q2.
    assert [q["topic"] for q in questions] == ["Geometry", "Geometry", "Geometry"]
    assert all(q["points"] == 2 for q in questions)
    assert all(q["question_type"] == "image_mcq" for q in questions)
    assert all(len(q["choices"]) == 4 for q in questions)


def test_upload_rejects_more_than_10_files(admin_client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    files = [(f"q{i}.png", FAKE_PNG, "image/png") for i in range(11)]
    response = admin_client.post(
        f"/api/v1/admin/exams/{exam['id']}/question-images",
        files=[("files", f) for f in files],
        data={"topic": "General", "difficulty": "medium", "points": "1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TOO_MANY_FILES"


def test_upload_rejects_bad_magic_bytes(admin_client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    fake_pdf_as_png = b"%PDF-1.4 not really a png"
    response = admin_client.post(
        f"/api/v1/admin/exams/{exam['id']}/question-images",
        files=[("files", ("q1.png", fake_pdf_as_png, "image/png"))],
        data={"topic": "General", "difficulty": "medium", "points": "1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"


def test_upload_rejects_oversized_image(admin_client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * 900_000
    response = admin_client.post(
        f"/api/v1/admin/exams/{exam['id']}/question-images",
        files=[("files", ("big.png", oversized, "image/png"))],
        data={"topic": "General", "difficulty": "medium", "points": "1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


# ------------------------------------------------------------------------------ answer key ----

def test_answer_key_preview_does_not_modify_database(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    preview = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/answer-key/preview", json={"answers": "BCAD"})
    assert preview.status_code == 200
    body = preview.json()
    assert body["parsed"] == ["B", "C", "A", "D"]
    assert body["count"] == 4
    assert body["question_count"] == 0
    assert body["errors"] == []

    detail = admin_client.get(f"/api/v1/admin/exams/{exam['id']}").json()
    assert detail["question_count"] == 0  # preview never writes


def test_answer_key_preview_reports_count_mismatch(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _add_text_question(admin_client, exam["id"])
    preview = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/answer-key/preview", json={"answers": "BCAD"})
    assert preview.status_code == 200
    assert preview.json()["errors"]  # 4 answers but only 2 questions


def test_apply_answer_key_creates_bubble_questions_when_none_exist(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    response = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/answer-key", json={"answers": "BCAD", "points_per_question": 5})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_published"] is True  # publish defaults to true
    questions = sorted(body["questions"], key=lambda q: q["position"])
    assert len(questions) == 4
    assert all(q["question_type"] == "bubble" for q in questions)
    assert all(q["points"] == 5 for q in questions)
    correct_letters = []
    for q in questions:
        correct = [c["label"] for c in q["choices"] if c["is_correct"]]
        assert len(correct) == 1
        correct_letters.append(correct[0])
    assert correct_letters == ["B", "C", "A", "D"]


def test_apply_answer_key_updates_existing_questions_without_recreating(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    q1 = _add_text_question(admin_client, exam["id"], correct="A")
    detail = _add_text_question(admin_client, exam["id"], correct="A")
    original_ids = sorted(q["id"] for q in detail["questions"])

    response = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/answer-key", json={"answers": "BD", "publish": False})
    assert response.status_code == 200, response.text
    body = response.json()
    new_ids = sorted(q["id"] for q in body["questions"])
    assert new_ids == original_ids  # same rows updated, not deleted/recreated
    questions = sorted(body["questions"], key=lambda q: q["position"])
    assert [c["label"] for q in questions for c in q["choices"] if c["is_correct"]] == ["B", "D"]


def test_apply_answer_key_rejects_invalid_format(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    response = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/answer-key", json={"answers": "not valid at all 123xyz"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ANSWER_KEY_INVALID"


def test_apply_answer_key_publish_false_does_not_publish(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    response = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/answer-key", json={"answers": "AB", "publish": False})
    assert response.status_code == 200
    assert response.json()["is_published"] is False


# ------------------------------------------------------------------------------ locking ----

def _seed_attempt(db_session, exam_id):
    academy_id = get_default_academy_id(db_session)
    student = User(academy_id=academy_id, role=UserRole.student, full_name="Attempted Student", student_code="TA-070099", password_hash=hash_password("Whatever123!"))
    db_session.add(student)
    db_session.flush()
    db_session.add(StudentProfile(user_id=student.id, student_type=StudentType.academy, subscription_status=SubscriptionStatus.active))
    db_session.flush()
    attempt = ExamAttempt(exam_id=exam_id, user_id=student.id, expires_at=utcnow() + timedelta(hours=1))
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_question_mutations_blocked_once_attempt_exists(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    detail = _add_text_question(admin_client, exam["id"])
    question_id = detail["questions"][0]["id"]
    _seed_attempt(db_session, exam["id"])

    add_more = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/questions", json={
        "question_type": "text_mcq", "prompt_text": "New", "correct_label": "A",
        "choices": [{"label": "A", "text": "1"}, {"label": "B", "text": "2"}, {"label": "C", "text": "3"}, {"label": "D", "text": "4"}],
    })
    assert add_more.status_code == 409
    assert add_more.json()["error"]["code"] == "EXAM_LOCKED"

    delete_response = admin_client.delete(f"/api/v1/admin/questions/{question_id}")
    assert delete_response.status_code == 409

    reorder_response = admin_client.put(f"/api/v1/admin/exams/{exam['id']}/questions/order", json={"ids": [question_id]})
    assert reorder_response.status_code == 409

    scoring_edit = admin_client.patch(f"/api/v1/admin/questions/{question_id}", json={"points": 99})
    assert scoring_edit.status_code == 409
    assert scoring_edit.json()["error"]["code"] == "EXAM_LOCKED"

    answer_key = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/answer-key", json={"answers": "B"})
    assert answer_key.status_code == 409


def test_non_scoring_metadata_still_editable_once_attempt_exists(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    detail = _add_text_question(admin_client, exam["id"])
    question_id = detail["questions"][0]["id"]
    _seed_attempt(db_session, exam["id"])

    response = admin_client.patch(f"/api/v1/admin/questions/{question_id}", json={"topic": "Updated Topic", "difficulty": "hard", "prompt_text": "Updated prompt"})
    assert response.status_code == 200, response.text
    updated = next(q for q in response.json()["questions"] if q["id"] == question_id)
    assert updated["topic"] == "Updated Topic"
    assert updated["difficulty"] == "hard"
    assert updated["prompt_text"] == "Updated prompt"


def test_image_upload_blocked_once_attempt_exists(admin_client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _seed_attempt(db_session, exam["id"])

    response = admin_client.post(
        f"/api/v1/admin/exams/{exam['id']}/question-images",
        files=[("files", ("q1.png", FAKE_PNG, "image/png"))],
        data={"topic": "General", "difficulty": "medium", "points": "1"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXAM_LOCKED"


# -------------------------------------------------------------------------------- delete ----

def test_delete_preview_counts(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _seed_attempt(db_session, exam["id"])

    preview = admin_client.get(f"/api/v1/admin/exams/{exam['id']}/delete-preview")
    assert preview.status_code == 200
    body = preview.json()
    assert body["questions"] == 1
    assert body["attempts"] == 1


def test_delete_exam_cascades_and_queues_image_cleanup(admin_client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    admin_client.post(
        f"/api/v1/admin/exams/{exam['id']}/question-images",
        files=[("files", ("q1.png", FAKE_PNG, "image/png"))],
        data={"topic": "General", "difficulty": "medium", "points": "1"},
    )
    attempt = _seed_attempt(db_session, exam["id"])
    db_session.add(PointLedger(user_id=attempt.user_id, event_key=f"exam:{attempt.id}", source_type=PointSource.exam, source_id=attempt.id, points=10, description="test", course_id=course.id))
    db_session.commit()
    profile = db_session.get(StudentProfile, attempt.user_id)
    profile.total_points = 10
    db_session.commit()

    delete_response = admin_client.delete(f"/api/v1/admin/exams/{exam['id']}")
    assert delete_response.status_code == 204

    assert db_session.get(Exam, exam["id"]) is None
    assert db_session.query(ExamQuestion).filter(ExamQuestion.exam_id == exam["id"]).count() == 0
    assert db_session.query(PointLedger).filter(PointLedger.source_type == PointSource.exam, PointLedger.source_id == attempt.id).count() == 0
    db_session.refresh(profile)
    assert profile.total_points == 0
    # The Phase-1 DB trigger on exam_questions.image_file_id queues the file for cleanup.
    assert db_session.query(PendingFileDeletion).count() >= 1


# ------------------------------------------------------------------------------- audit log ----

def test_audit_log_serializes_datetime_and_enum_summary(admin_client, db_session):
    course = _make_course(db_session)
    now = utcnow()
    exam = _create_exam_via_api(admin_client, course.id)
    response = admin_client.patch(f"/api/v1/admin/exams/{exam['id']}", json={
        "starts_at": now.isoformat(), "ends_at": (now + timedelta(hours=2)).isoformat(), "exam_mode": "full",
    })
    assert response.status_code == 200, response.text

    rows = db_session.query(AuditLog).filter(AuditLog.action == "exam.update").all()
    assert len(rows) == 1
    assert "starts_at" in rows[0].summary
    assert "exam_mode" in rows[0].summary
