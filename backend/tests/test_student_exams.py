"""Phase 6 student exam runner (ARCHITECTURE.md §4.4, §5.2): eligibility/access, attempt
start/resume idempotency, autosave staleness/rejection rules, manual + auto-submit grading and
point-award idempotency, violation locking, and student isolation."""

from datetime import timedelta

from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.jobs.auto_submit import _run as run_auto_submit
from app.models.courses import Course, CourseAccent
from app.models.exams import AttemptStatus, ExamAttempt
from app.models.groups import Enrollment
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.models.points import PointLedger, PointSource

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _make_course(db_session, title="ACT Reading"):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="English", accent=CourseAccent.blue, is_published=True)
    db_session.add(course)
    db_session.commit()
    return course


def _create_exam_via_api(admin_client, course_id, **overrides):
    payload = {"title": "Runner Exam", "course_id": course_id, "exam_mode": "answer_sheet", "duration_minutes": 30, "passing_score": 50, "max_attempts": 1, "ends_at": None}
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
    return sorted(response.json()["questions"], key=lambda q: q["position"])[-1]


def _publish(admin_client, exam_id):
    response = admin_client.post(f"/api/v1/admin/exams/{exam_id}/publish")
    assert response.status_code == 200, response.text
    return response.json()


def _make_student(db_session, code="TA-090001", student_type=StudentType.academy, subscription=SubscriptionStatus.active):
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


def _enroll(db_session, student, course):
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()


# ------------------------------------------------------------------------------- eligibility ----

def test_exam_not_listed_without_enrollment(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    student_client = _login_student(client, student.student_code)
    listing = student_client.get("/api/v1/me/exams")
    assert listing.status_code == 200
    assert listing.json() == []

    pre_start = student_client.get(f"/api/v1/me/exams/{exam['id']}")
    assert pre_start.status_code == 404


def test_external_student_with_inactive_subscription_is_blocked(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _publish(admin_client, exam["id"])

    student = _make_student(db_session, student_type=StudentType.external, subscription=SubscriptionStatus.expired)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)

    assert student_client.get("/api/v1/me/exams").json() == []
    assert student_client.get(f"/api/v1/me/exams/{exam['id']}").status_code == 404


def test_upcoming_and_expired_window_states(admin_client, client, db_session):
    now = utcnow()
    course = _make_course(db_session)
    upcoming_exam = _create_exam_via_api(admin_client, course.id, title="Upcoming", starts_at=(now + timedelta(days=1)).isoformat())
    _add_text_question(admin_client, upcoming_exam["id"])
    _publish(admin_client, upcoming_exam["id"])

    expired_exam = _create_exam_via_api(admin_client, course.id, title="Expired", ends_at=(now - timedelta(hours=1)).isoformat())
    _add_text_question(admin_client, expired_exam["id"])
    _publish(admin_client, expired_exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)

    cards = {c["id"]: c for c in student_client.get("/api/v1/me/exams").json()}
    assert cards[upcoming_exam["id"]]["status"] == "upcoming"
    assert cards[expired_exam["id"]]["status"] == "expired"

    assert student_client.post(f"/api/v1/me/exams/{upcoming_exam['id']}/start").status_code == 409
    assert student_client.post(f"/api/v1/me/exams/{expired_exam['id']}/start").status_code == 409


# ------------------------------------------------------------------------ start/resume/secrecy ----

def test_start_then_resume_is_idempotent_and_hides_answer_key(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)

    first = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert first.status_code == 200
    payload = first.json()
    assert payload["status"] == "in_progress"
    assert "is_correct" not in str(payload)
    for q in payload["questions"]:
        for choice in q["choices"]:
            assert "is_correct" not in choice

    second = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert second.status_code == 200
    assert second.json()["attempt_id"] == payload["attempt_id"]

    attempt_ids = db_session.query(ExamAttempt).filter(ExamAttempt.exam_id == exam["id"], ExamAttempt.user_id == student.id).count()
    assert attempt_ids == 1


def test_get_exam_pre_start_never_reveals_questions(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)

    pre_start = student_client.get(f"/api/v1/me/exams/{exam['id']}")
    assert pre_start.status_code == 200
    assert "questions" not in pre_start.json()


# ------------------------------------------------------------------------------------ autosave ----

def test_autosave_replaces_answer_and_rejects_stale_client_seq(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    question = _add_text_question(admin_client, exam["id"])
    choice_a = next(c for c in question["choices"] if c["label"] == "A")
    choice_b = next(c for c in question["choices"] if c["label"] == "B")
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)
    attempt_id = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()["attempt_id"]

    save1 = student_client.put(f"/api/v1/me/attempts/{attempt_id}/answers", json={"client_seq": 1, "answers": [{"question_id": question["id"], "choice_id": choice_a["id"]}]})
    assert save1.status_code == 200 and save1.json()["saved"] is True

    save2 = student_client.put(f"/api/v1/me/attempts/{attempt_id}/answers", json={"client_seq": 2, "answers": [{"question_id": question["id"], "choice_id": choice_b["id"]}]})
    assert save2.status_code == 200 and save2.json()["saved"] is True

    stale = student_client.put(f"/api/v1/me/attempts/{attempt_id}/answers", json={"client_seq": 1, "answers": [{"question_id": question["id"], "choice_id": choice_a["id"]}]})
    assert stale.status_code == 200 and stale.json()["saved"] is False

    resumed = student_client.get(f"/api/v1/me/attempts/{attempt_id}")
    assert resumed.json()["saved_answers"][str(question["id"])] == choice_b["id"]


def test_autosave_rejected_after_submit(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    question = _add_text_question(admin_client, exam["id"])
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)
    attempt_id = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()["attempt_id"]

    submit = student_client.post(f"/api/v1/me/attempts/{attempt_id}/submit", json={"client_seq": 1, "answers": []})
    assert submit.status_code == 200

    after = student_client.put(f"/api/v1/me/attempts/{attempt_id}/answers", json={"client_seq": 2, "answers": [{"question_id": question["id"], "choice_id": None}]})
    assert after.status_code == 409
    assert after.json()["error"]["code"] == "ATTEMPT_NOT_ACTIVE"


# ----------------------------------------------------------------------------- grading/points ----

def test_manual_submit_grades_objectively_and_awards_points_once(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, passing_score=50)
    q1 = _add_text_question(admin_client, exam["id"], correct="A", points=1)
    q2 = _add_text_question(admin_client, exam["id"], correct="B", points=1)
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)
    attempt_id = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()["attempt_id"]

    a1 = next(c for c in q1["choices"] if c["label"] == "A")
    a2_wrong = next(c for c in q2["choices"] if c["label"] == "A")  # wrong on purpose
    submit = student_client.post(
        f"/api/v1/me/attempts/{attempt_id}/submit",
        json={"client_seq": 1, "answers": [{"question_id": q1["id"], "choice_id": a1["id"]}, {"question_id": q2["id"], "choice_id": a2_wrong["id"]}]},
    )
    assert submit.status_code == 200, submit.text
    result = submit.json()
    assert result["score_points"] == 1
    assert result["total_points"] == 2
    assert result["percentage"] == 50
    assert result["passed"] is True
    assert result["points_awarded"] > 0

    ledger_count = db_session.query(PointLedger).filter(PointLedger.source_type == PointSource.exam, PointLedger.source_id == exam["id"], PointLedger.user_id == student.id).count()
    assert ledger_count == 1

    # Idempotent replay: same result, no re-award, no duplicate ledger row.
    replay = student_client.post(f"/api/v1/me/attempts/{attempt_id}/submit", json={"client_seq": 1, "answers": []})
    assert replay.status_code == 200
    assert replay.json()["points_awarded"] == 0
    ledger_count_after = db_session.query(PointLedger).filter(PointLedger.source_type == PointSource.exam, PointLedger.source_id == exam["id"], PointLedger.user_id == student.id).count()
    assert ledger_count_after == 1


def test_auto_submit_job_expires_and_grades_overdue_attempt(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, duration_minutes=1)
    question = _add_text_question(admin_client, exam["id"], correct="A")
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)
    attempt_id = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()["attempt_id"]

    attempt = db_session.get(ExamAttempt, attempt_id)
    attempt.expires_at = utcnow() - timedelta(minutes=5)
    db_session.commit()

    summary = run_auto_submit(db_session)
    assert "expired=1" in summary

    db_session.refresh(attempt)
    assert attempt.status == AttemptStatus.expired
    assert attempt.submit_source.value == "auto"
    ledger_count = db_session.query(PointLedger).filter(PointLedger.source_type == PointSource.exam, PointLedger.source_id == exam["id"], PointLedger.user_id == student.id).count()
    assert ledger_count == 1


# ------------------------------------------------------------------------------ violation lock ----

def test_violations_lock_attempt_and_block_further_writes(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    _add_text_question(admin_client, exam["id"])
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)
    attempt_id = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()["attempt_id"]

    # AcademySettings.violation_limit defaults to 2 (Phase 1 migration seed) -- two violations lock.
    student_client.post(f"/api/v1/me/attempts/{attempt_id}/events", json={"type": "window_blur"})
    import time

    time.sleep(3.1)  # clear the 3s violation debounce window
    second = student_client.post(f"/api/v1/me/attempts/{attempt_id}/events", json={"type": "window_blur"})
    assert second.status_code == 200
    assert second.json()["locked"] is True

    blocked = student_client.put(f"/api/v1/me/attempts/{attempt_id}/answers", json={"client_seq": 1, "answers": []})
    assert blocked.status_code == 423


# ------------------------------------------------------------------------------ isolation ----

def test_student_cannot_start_second_open_attempt_via_double_click(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, max_attempts=1)
    _add_text_question(admin_client, exam["id"])
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)

    r1 = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    r2 = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert r1.json()["attempt_id"] == r2.json()["attempt_id"]
    assert db_session.query(ExamAttempt).filter(ExamAttempt.exam_id == exam["id"]).count() == 1
