"""Phase 7: admin exam-attempt management (ARCHITECTURE.md §4.4) -- listing/filtering, attempt
detail, and the unlock / extra-time / new-attempt actions, including cross-student isolation,
invalid state transitions, repeated-action safety, and that grading/points never duplicate across
a superseded -> granted -> completed attempt chain.
"""

import time
from datetime import timedelta

from starlette.testclient import TestClient

from app.core.security import hash_password
from app.core.time import utcnow
from app.db.scope import get_default_academy_id
from app.main import app as fastapi_app
from app.models.academy import Academy, AcademySettings
from app.models.courses import Course, CourseAccent
from app.models.exams import AttemptStatus, Exam, ExamAttempt, ExamMode
from app.models.groups import Enrollment
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole
from app.models.points import PointLedger, PointSource

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _make_course(db_session, title="Attempts Course"):
    academy_id = get_default_academy_id(db_session)
    from app.core.search import normalize_search_text

    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="Math", accent=CourseAccent.blue, is_published=True)
    db_session.add(course)
    db_session.commit()
    return course


def _create_exam_via_api(admin_client, course_id, **overrides):
    payload = {"title": "Attempt Mgmt Exam", "course_id": course_id, "exam_mode": "answer_sheet", "duration_minutes": 30, "passing_score": 50, "max_attempts": 1, "ends_at": None}
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


def _make_student(db_session, code="TA-091001"):
    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name="طالب اختبار", student_code=code, password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, student_type=StudentType.academy, subscription_status=SubscriptionStatus.active))
    db_session.commit()
    return user


def _login_student(code, password="Whatever123!"):
    """Uses its own fresh TestClient/cookie jar, independent from admin_client's -- these tests
    interleave admin actions (unlock/extra-time/new-attempt) with student actions on the same
    attempt, and logging in on a *shared* client would silently overwrite the admin's session
    cookies with the student's (both `client` and `admin_client` wrap the same TestClient)."""
    from tests.conftest import AuthedClient

    student_test_client = TestClient(fastapi_app)
    response = student_test_client.post("/api/v1/auth/login", json={"identifier": code, "password": password})
    assert response.status_code == 200, response.text
    return AuthedClient(student_test_client)


def _enroll(db_session, student, course):
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()


def _setup_exam_with_attempt(admin_client, db_session, code="TA-091001", max_attempts=1, duration_minutes=30):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, max_attempts=max_attempts, duration_minutes=duration_minutes)
    question = _add_text_question(admin_client, exam["id"])
    _publish(admin_client, exam["id"])
    student = _make_student(db_session, code=code)
    _enroll(db_session, student, course)
    student_client = _login_student(student.student_code)
    started = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert started.status_code == 200, started.text
    return exam, question, student, student_client, started.json()


# --------------------------------------------------------------------------------- listing ----

def test_list_attempts_and_filter_by_status(admin_client, db_session):
    exam, _question, _student, _student_client, payload = _setup_exam_with_attempt(admin_client, db_session)

    all_attempts = admin_client.get(f"/api/v1/admin/exams/{exam['id']}/attempts")
    assert all_attempts.status_code == 200
    body = all_attempts.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["attempt_id"] == payload["attempt_id"]
    assert row["status"] == "in_progress"
    assert row["student"]["student_code"] == "TA-091001"
    assert row["question_count"] == 1
    assert row["percentage"] is None  # not graded yet

    filtered = admin_client.get(f"/api/v1/admin/exams/{exam['id']}/attempts?status=submitted")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 0


def test_cross_academy_attempt_returns_404(admin_client, db_session):
    other_academy = Academy(name="Other Academy", slug="other-academy-attempts")
    db_session.add(other_academy)
    db_session.flush()
    db_session.add(AcademySettings(academy_id=other_academy.id))
    from app.core.search import normalize_search_text

    other_course = Course(academy_id=other_academy.id, title="Other Course", title_search=normalize_search_text("Other Course"), subject="X", accent=CourseAccent.gold)
    db_session.add(other_course)
    db_session.flush()
    other_exam = Exam(academy_id=other_academy.id, course_id=other_course.id, title="Other Exam", exam_mode=ExamMode.answer_sheet)
    db_session.add(other_exam)
    db_session.flush()
    other_student = User(academy_id=other_academy.id, role=UserRole.student, full_name="Other", student_code="OA-000001", password_hash=hash_password("Whatever123!"))
    db_session.add(other_student)
    db_session.flush()
    other_attempt = ExamAttempt(exam_id=other_exam.id, user_id=other_student.id, expires_at=utcnow() + timedelta(hours=1))
    db_session.add(other_attempt)
    db_session.commit()

    response = admin_client.get(f"/api/v1/admin/attempts/{other_attempt.id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"


# ---------------------------------------------------------------------------------- detail ----

def test_attempt_detail_shows_events_and_answers(admin_client, db_session):
    exam, question, _student, student_client, payload = _setup_exam_with_attempt(admin_client, db_session)
    attempt_id = payload["attempt_id"]
    choice_a = next(c for c in question["choices"] if c["label"] == "A")
    student_client.put(f"/api/v1/me/attempts/{attempt_id}/answers", json={"client_seq": 1, "answers": [{"question_id": question["id"], "choice_id": choice_a["id"]}]})

    detail = admin_client.get(f"/api/v1/admin/attempts/{attempt_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["exam_id"] == exam["id"]
    assert body["student"]["student_code"] == "TA-091001"
    assert len(body["answers"]) == 1
    ans = body["answers"][0]
    assert ans["choice_id"] == choice_a["id"]
    assert ans["correct_label"] == "A"  # admin view is allowed to see the answer key
    assert any(e["event_type"] == "started" for e in body["events"])


# ---------------------------------------------------------------------------------- unlock ----

def test_unlock_requires_locked_status(admin_client, db_session):
    exam, _question, _student, _student_client, payload = _setup_exam_with_attempt(admin_client, db_session)
    response = admin_client.post(f"/api/v1/admin/attempts/{payload['attempt_id']}/unlock", json={"reason": "test", "extra_minutes": 0})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ATTEMPT_NOT_LOCKED"


def test_violation_lock_then_admin_unlock_restores_writability(admin_client, db_session):
    exam, question, _student, student_client, payload = _setup_exam_with_attempt(admin_client, db_session)
    attempt_id = payload["attempt_id"]

    student_client.post(f"/api/v1/me/attempts/{attempt_id}/events", json={"type": "window_blur"})
    time.sleep(3.1)
    second = student_client.post(f"/api/v1/me/attempts/{attempt_id}/events", json={"type": "window_blur"})
    assert second.json()["locked"] is True

    blocked = student_client.put(f"/api/v1/me/attempts/{attempt_id}/answers", json={"client_seq": 1, "answers": []})
    assert blocked.status_code == 423

    unlocked = admin_client.post(f"/api/v1/admin/attempts/{attempt_id}/unlock", json={"reason": "طالب اتصل بالإدارة", "extra_minutes": 5})
    assert unlocked.status_code == 200, unlocked.text
    body = unlocked.json()
    assert body["status"] == "in_progress"
    assert body["violation_count"] == 0
    assert body["extra_minutes"] == 5
    assert any(e["event_type"] == "unlocked" for e in body["events"])

    choice_a = next(c for c in question["choices"] if c["label"] == "A")
    resumed_write = student_client.put(f"/api/v1/me/attempts/{attempt_id}/answers", json={"client_seq": 2, "answers": [{"question_id": question["id"], "choice_id": choice_a["id"]}]})
    assert resumed_write.status_code == 200
    assert resumed_write.json()["saved"] is True


def test_unlock_after_expiry_grants_remaining_time_when_no_extra_given(admin_client, db_session):
    exam, _question, _student, student_client, payload = _setup_exam_with_attempt(admin_client, db_session, duration_minutes=10)
    attempt_id = payload["attempt_id"]

    attempt = db_session.get(ExamAttempt, attempt_id)
    now = utcnow()
    # Locked 7 minutes ago with 6 minutes still left on the clock at that moment (expires_at was
    # locked_at + 6min = 1 minute ago) -- simulates a student who got locked, then never came back
    # before the clock ran out while still locked.
    attempt.locked_at = now - timedelta(minutes=7)
    attempt.expires_at = now - timedelta(minutes=1)
    attempt.status = AttemptStatus.locked
    attempt.violation_count = 2
    db_session.commit()

    unlocked = admin_client.post(f"/api/v1/admin/attempts/{attempt_id}/unlock", json={"reason": "manual review", "extra_minutes": 0})
    assert unlocked.status_code == 200, unlocked.text
    body = unlocked.json()
    assert body["status"] == "in_progress"
    new_expires = body["expires_at"]
    # New deadline should be roughly "now + max(remaining, 0)" -- just assert it's now comfortably
    # in the future rather than pin an exact second (test runtime jitter).
    from datetime import datetime, timezone

    delta_minutes = (datetime.fromisoformat(new_expires.replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() / 60
    assert delta_minutes > 0
    assert delta_minutes < 10  # never more than the original duration


# ------------------------------------------------------------------------------- extra time ----

def test_extra_time_extends_deadline_and_rejects_on_terminal_attempt(admin_client, db_session):
    exam, question, _student, student_client, payload = _setup_exam_with_attempt(admin_client, db_session)
    attempt_id = payload["attempt_id"]
    before = payload["expires_at"]

    granted = admin_client.post(f"/api/v1/admin/attempts/{attempt_id}/extra-time", json={"reason": "تأخر بسبب مشكلة إنترنت", "minutes": 15})
    assert granted.status_code == 200, granted.text
    body = granted.json()
    assert body["expires_at"] > before
    assert body["extra_minutes"] == 15
    assert any(e["event_type"] == "extra_time" for e in body["events"])

    student_client.post(f"/api/v1/me/attempts/{attempt_id}/submit", json={"client_seq": 1, "answers": []})
    rejected = admin_client.post(f"/api/v1/admin/attempts/{attempt_id}/extra-time", json={"reason": "too late", "minutes": 10})
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "ATTEMPT_NOT_ACTIVE"


def test_extra_time_minutes_out_of_range_rejected(admin_client, db_session):
    exam, _question, _student, _student_client, payload = _setup_exam_with_attempt(admin_client, db_session)
    too_many = admin_client.post(f"/api/v1/admin/attempts/{payload['attempt_id']}/extra-time", json={"reason": "x", "minutes": 500})
    assert too_many.status_code == 422
    zero = admin_client.post(f"/api/v1/admin/attempts/{payload['attempt_id']}/extra-time", json={"reason": "x", "minutes": 0})
    assert zero.status_code == 422


# ------------------------------------------------------------------------------ new attempt ----

def test_new_attempt_supersedes_open_attempt_and_bypasses_window(admin_client, db_session):
    exam, question, student, student_client, payload = _setup_exam_with_attempt(admin_client, db_session, max_attempts=1)
    old_attempt_id = payload["attempt_id"]

    # Close the exam window entirely -- a granted replacement attempt must still be startable.
    admin_client.patch(f"/api/v1/admin/exams/{exam['id']}", json={"ends_at": (utcnow() - timedelta(minutes=1)).isoformat()})

    granted = admin_client.post(f"/api/v1/admin/attempts/{old_attempt_id}/new-attempt", json={"reason": "انقطع الإنترنت", "extra_minutes": 10})
    assert granted.status_code == 200, granted.text
    new_body = granted.json()
    assert new_body["status"] == "granted"
    assert new_body["attempt_id"] != old_attempt_id
    assert new_body["extra_minutes"] == 10

    old_row = db_session.get(ExamAttempt, old_attempt_id)
    assert old_row.status == AttemptStatus.superseded
    assert old_row.superseded_by_id == new_body["attempt_id"]

    # The student can start the granted attempt even though the window closed and max_attempts=1
    # was already exhausted by the (now superseded) first attempt.
    resumed = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["attempt_id"] == new_body["attempt_id"]
    assert resumed.json()["status"] == "in_progress"

    # duration_minutes=30 (default) + extra_minutes=10 granted at creation time.
    from datetime import datetime, timezone

    started_at = datetime.fromisoformat(resumed.json()["server_now"].replace("Z", "+00:00"))
    expires_at = datetime.fromisoformat(resumed.json()["expires_at"].replace("Z", "+00:00"))
    total_minutes = (expires_at - started_at).total_seconds() / 60
    assert 38 <= total_minutes <= 40  # ~30 + 10, generous bound for test runtime


def test_new_attempt_rejected_when_no_open_attempt_to_supersede_and_not_terminal(admin_client, db_session):
    exam, _question, _student, student_client, payload = _setup_exam_with_attempt(admin_client, db_session)
    old_attempt_id = payload["attempt_id"]
    first = admin_client.post(f"/api/v1/admin/attempts/{old_attempt_id}/new-attempt", json={"reason": "r1", "extra_minutes": 0})
    assert first.status_code == 200

    # old_attempt_id is now superseded -- calling new-attempt on it again must be rejected, not
    # silently create yet another replacement (idempotent-safe: repeat clicks fail loudly).
    second = admin_client.post(f"/api/v1/admin/attempts/{old_attempt_id}/new-attempt", json={"reason": "r2", "extra_minutes": 0})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ATTEMPT_NOT_ELIGIBLE"


def test_new_attempt_from_submitted_attempt_grants_extra_eligibility(admin_client, db_session):
    exam, question, _student, student_client, payload = _setup_exam_with_attempt(admin_client, db_session, max_attempts=1)
    attempt_id = payload["attempt_id"]
    submit = student_client.post(f"/api/v1/me/attempts/{attempt_id}/submit", json={"client_seq": 1, "answers": []})
    assert submit.status_code == 200

    # max_attempts=1 already exhausted -- a normal start would be rejected.
    exhausted = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert exhausted.status_code == 409
    assert exhausted.json()["error"]["code"] == "ATTEMPTS_EXHAUSTED"

    granted = admin_client.post(f"/api/v1/admin/attempts/{attempt_id}/new-attempt", json={"reason": "طلب إعادة", "extra_minutes": 0})
    assert granted.status_code == 200, granted.text
    assert granted.json()["status"] == "granted"

    old_row = db_session.get(ExamAttempt, attempt_id)
    assert old_row.status == AttemptStatus.submitted  # a terminal attempt is left alone, not superseded
    assert old_row.superseded_by_id is None

    resumed = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "in_progress"


def test_grading_and_points_not_duplicated_across_superseded_chain(admin_client, db_session):
    exam, question, student, student_client, payload = _setup_exam_with_attempt(admin_client, db_session, max_attempts=1)
    old_attempt_id = payload["attempt_id"]
    choice_a = next(c for c in question["choices"] if c["label"] == "A")

    # First attempt: submitted with a wrong answer on purpose, low score.
    wrong = next(c for c in question["choices"] if c["label"] == "B")
    student_client.post(f"/api/v1/me/attempts/{old_attempt_id}/submit", json={"client_seq": 1, "answers": [{"question_id": question["id"], "choice_id": wrong["id"]}]})

    granted = admin_client.post(f"/api/v1/admin/attempts/{old_attempt_id}/new-attempt", json={"reason": "إعادة فرصة", "extra_minutes": 0})
    assert granted.status_code == 200

    started = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    new_attempt_id = started.json()["attempt_id"]
    result = student_client.post(f"/api/v1/me/attempts/{new_attempt_id}/submit", json={"client_seq": 1, "answers": [{"question_id": question["id"], "choice_id": choice_a["id"]}]})
    assert result.status_code == 200
    assert result.json()["percentage"] == 100

    # Exactly one ledger row for (student, exam), holding the best percentage across both attempts.
    ledger_rows = db_session.query(PointLedger).filter(PointLedger.source_type == PointSource.exam, PointLedger.source_id == exam["id"], PointLedger.user_id == student.id).all()
    assert len(ledger_rows) == 1
    assert ledger_rows[0].points > 0

    card = student_client.get("/api/v1/me/exams").json()
    row = next(c for c in card if c["id"] == exam["id"])
    assert row["best_score"] == 100
    assert row["attempts_used"] == 2  # both submitted attempts count, neither is superseded
