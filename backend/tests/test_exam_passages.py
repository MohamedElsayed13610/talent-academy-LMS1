"""Passage support (integrated into Phase 6, not a separate phase): a reading passage belongs to
one exam and zero or more of that exam's questions may link to it. Covers admin CRUD, cross-exam
link rejection, exam-deletion cascade + image cleanup queueing, and student-runner access control
(passage content/images only reachable through an owned, active attempt — same discipline as
question images)."""

from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.db.scope import get_default_academy_id
from app.models.courses import Course, CourseAccent
from app.models.exams import Exam, ExamPassage, ExamQuestion
from app.models.files import PendingFileDeletion
from app.models.groups import Enrollment
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _make_course(db_session, title="Reading Comprehension"):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="English", accent=CourseAccent.blue, is_published=True)
    db_session.add(course)
    db_session.commit()
    return course


def _create_exam_via_api(admin_client, course_id, **overrides):
    payload = {"title": "Passage Exam", "course_id": course_id, "exam_mode": "answer_sheet", "duration_minutes": 30, "passing_score": 50, "max_attempts": 1}
    payload.update(overrides)
    response = admin_client.post("/api/v1/admin/exams", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _add_text_question(admin_client, exam_id, correct="A"):
    payload = {
        "question_type": "text_mcq", "prompt_text": "According to the passage, what is true?",
        "choices": [{"label": "A", "text": "X"}, {"label": "B", "text": "Y"}, {"label": "C", "text": "Z"}, {"label": "D", "text": "W"}],
        "correct_label": correct, "topic": "Reading", "difficulty": "medium", "points": 1,
    }
    response = admin_client.post(f"/api/v1/admin/exams/{exam_id}/questions", json=payload)
    assert response.status_code == 201, response.text
    return sorted(response.json()["questions"], key=lambda q: q["position"])[-1]


def _make_student(db_session, code="TA-080001"):
    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name="طالب اختبار", student_code=code, password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, student_type=StudentType.academy, subscription_status=SubscriptionStatus.active))
    db_session.commit()
    return user


def _login_student(client, code, password="Whatever123!"):
    from tests.conftest import AuthedClient

    response = client.post("/api/v1/auth/login", json={"identifier": code, "password": password})
    assert response.status_code == 200, response.text
    return AuthedClient(client)


# ------------------------------------------------------------------------------ admin CRUD ----

def test_create_and_update_passage(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    response = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "Passage 1", "body_text": "Once upon a time..."})
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["passages"]) == 1
    passage = body["passages"][0]
    assert passage["title"] == "Passage 1"
    assert passage["question_ids"] == []
    assert passage["position"] == 1

    update = admin_client.patch(f"/api/v1/admin/passages/{passage['id']}", json={"title": "Renamed Passage", "body_text": "Updated text"})
    assert update.status_code == 200
    updated = update.json()["passages"][0]
    assert updated["title"] == "Renamed Passage"
    assert updated["body_text"] == "Updated text"


def test_reorder_passages(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    p1 = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "P1", "body_text": "a"}).json()["passages"][0]
    p2 = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "P2", "body_text": "b"}).json()["passages"][-1]
    assert p1["position"] == 1 and p2["position"] == 2

    reordered = admin_client.put(f"/api/v1/admin/exams/{exam['id']}/passages/order", json={"ids": [p2["id"], p1["id"]]})
    assert reordered.status_code == 200, reordered.text
    by_id = {p["id"]: p for p in reordered.json()["passages"]}
    assert by_id[p2["id"]]["position"] == 1
    assert by_id[p1["id"]]["position"] == 2

    mismatched = admin_client.put(f"/api/v1/admin/exams/{exam['id']}/passages/order", json={"ids": [p1["id"]]})
    assert mismatched.status_code == 409
    assert mismatched.json()["error"]["code"] == "ORDER_MISMATCH"


def test_set_passage_questions_links_multiple(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    q1 = _add_text_question(admin_client, exam["id"])
    q2 = _add_text_question(admin_client, exam["id"])
    passage = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "P", "body_text": "text"}).json()["passages"][0]

    linked = admin_client.put(f"/api/v1/admin/passages/{passage['id']}/questions", json={"question_ids": [q1["id"], q2["id"]]})
    assert linked.status_code == 200, linked.text
    body = linked.json()
    updated_passage = next(p for p in body["passages"] if p["id"] == passage["id"])
    assert sorted(updated_passage["question_ids"]) == sorted([q1["id"], q2["id"]])
    for q in body["questions"]:
        if q["id"] in (q1["id"], q2["id"]):
            assert q["passage_id"] == passage["id"]

    # Re-setting to a smaller set unlinks the removed question.
    relinked = admin_client.put(f"/api/v1/admin/passages/{passage['id']}/questions", json={"question_ids": [q1["id"]]})
    assert relinked.status_code == 200
    body2 = relinked.json()
    q2_after = next(q for q in body2["questions"] if q["id"] == q2["id"])
    assert q2_after["passage_id"] is None


def test_set_passage_questions_rejects_cross_exam_question(admin_client, db_session):
    course = _make_course(db_session)
    exam_a = _create_exam_via_api(admin_client, course.id, title="Exam A")
    exam_b = _create_exam_via_api(admin_client, course.id, title="Exam B")
    other_question = _add_text_question(admin_client, exam_b["id"])
    passage = admin_client.post(f"/api/v1/admin/exams/{exam_a['id']}/passages", json={"title": "P", "body_text": "t"}).json()["passages"][0]

    response = admin_client.put(f"/api/v1/admin/passages/{passage['id']}/questions", json={"question_ids": [other_question["id"]]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUESTION_NOT_IN_EXAM"


def test_delete_passage_keeps_linked_questions_but_clears_link(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    question = _add_text_question(admin_client, exam["id"])
    passage = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "P", "body_text": "t"}).json()["passages"][0]
    admin_client.put(f"/api/v1/admin/passages/{passage['id']}/questions", json={"question_ids": [question["id"]]})

    delete_response = admin_client.delete(f"/api/v1/admin/passages/{passage['id']}")
    assert delete_response.status_code == 200
    body = delete_response.json()
    assert body["passages"] == []
    assert len(body["questions"]) == 1
    assert body["questions"][0]["id"] == question["id"]
    assert body["questions"][0]["passage_id"] is None
    assert db_session.get(ExamQuestion, question["id"]) is not None


def test_passage_image_upload_and_validation(admin_client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    passage = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "P", "body_text": "t"}).json()["passages"][0]

    good = admin_client.post(f"/api/v1/admin/passages/{passage['id']}/image", files={"file": ("p.png", FAKE_PNG, "image/png")})
    assert good.status_code == 201, good.text
    updated_passage = next(p for p in good.json()["passages"] if p["id"] == passage["id"])
    assert updated_passage["image_url"] is not None

    bad = admin_client.post(f"/api/v1/admin/passages/{passage['id']}/image", files={"file": ("p.png", b"not an image", "image/png")})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"


def test_exam_delete_cascades_passages_and_queues_image_cleanup(admin_client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id)
    passage = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "P", "body_text": "t"}).json()["passages"][0]
    admin_client.post(f"/api/v1/admin/passages/{passage['id']}/image", files={"file": ("p.png", FAKE_PNG, "image/png")})

    delete_response = admin_client.delete(f"/api/v1/admin/exams/{exam['id']}")
    assert delete_response.status_code == 204
    assert db_session.get(Exam, exam["id"]) is None
    assert db_session.get(ExamPassage, passage["id"]) is None
    assert db_session.query(PendingFileDeletion).count() >= 1


# --------------------------------------------------------------------------- student runner ----

def test_pre_start_exam_view_never_exposes_passages(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, ends_at=None)
    question = _add_text_question(admin_client, exam["id"])
    passage = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "Secret Passage", "body_text": "hidden until start"}).json()["passages"][0]
    admin_client.put(f"/api/v1/admin/passages/{passage['id']}/questions", json={"question_ids": [question["id"]]})
    admin_client.post(f"/api/v1/admin/exams/{exam['id']}/publish")

    student = _make_student(db_session)
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()
    student_client = _login_student(client, student.student_code)

    pre_start = student_client.get(f"/api/v1/me/exams/{exam['id']}")
    assert pre_start.status_code == 200
    assert "passages" not in pre_start.json()


def test_student_sees_passage_after_starting_attempt(admin_client, client, db_session, fake_s3):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, ends_at=None)
    question = _add_text_question(admin_client, exam["id"])
    passage_body = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "Rain", "body_text": "It rains a lot."}).json()
    passage = passage_body["passages"][0]
    admin_client.post(f"/api/v1/admin/passages/{passage['id']}/image", files={"file": ("p.png", FAKE_PNG, "image/png")})
    admin_client.put(f"/api/v1/admin/passages/{passage['id']}/questions", json={"question_ids": [question["id"]]})
    admin_client.post(f"/api/v1/admin/exams/{exam['id']}/publish")

    student = _make_student(db_session)
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()
    student_client = _login_student(client, student.student_code)

    started = student_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert started.status_code == 200, started.text
    payload = started.json()
    assert len(payload["passages"]) == 1
    passage_out = payload["passages"][0]
    assert passage_out["title"] == "Rain"
    assert passage_out["body_text"] == "It rains a lot."
    assert passage_out["image_url"] is not None
    linked_question = next(q for q in payload["questions"] if q["id"] == question["id"])
    assert linked_question["passage_id"] == passage["id"]
    # No answer-key leakage anywhere in the payload.
    assert "is_correct" not in str(payload)


def test_student_cannot_access_another_students_attempt_or_its_passage(admin_client, client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, ends_at=None)
    question = _add_text_question(admin_client, exam["id"])
    passage = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "P", "body_text": "t"}).json()["passages"][0]
    admin_client.put(f"/api/v1/admin/passages/{passage['id']}/questions", json={"question_ids": [question["id"]]})
    admin_client.post(f"/api/v1/admin/exams/{exam['id']}/publish")

    owner = _make_student(db_session, code="TA-080002")
    intruder = _make_student(db_session, code="TA-080003")
    db_session.add(Enrollment(user_id=owner.id, course_id=course.id))
    db_session.add(Enrollment(user_id=intruder.id, course_id=course.id))
    db_session.commit()

    owner_client = _login_student(client, owner.student_code)
    started = owner_client.post(f"/api/v1/me/exams/{exam['id']}/start")
    assert started.status_code == 200
    attempt_id = started.json()["attempt_id"]

    intruder_client = _login_student(client, intruder.student_code)
    hijack = intruder_client.get(f"/api/v1/me/attempts/{attempt_id}")
    assert hijack.status_code == 404
    assert hijack.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"
