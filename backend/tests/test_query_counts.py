"""Query-count regression tests for the hot student paths: autosave must not issue per-answer
queries, and /me/exams + /me/dashboard must not grow with the number of exams or sessions.

Counts every statement sent to the database (SQLAlchemy before_cursor_execute; an executemany
counts once), so the printed numbers are directly comparable before/after a change."""

from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import event

from tests.test_live_sessions import _create_session
from tests.test_student_exams import (
    FAKE_PNG,
    _add_text_question,
    _create_exam_via_api,
    _enroll,
    _login_student,
    _make_course,
    _make_student,
    _publish,
)


@contextmanager
def count_queries(engine):
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def _choice(question, label):
    return {"question_id": question["id"], "choice_id": next(c["id"] for c in question["choices"] if c["label"] == label)}


def test_autosave_query_count_does_not_scale_with_answers(admin_client, client, db_session, engine):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, duration_minutes=120)
    questions = [_add_text_question(admin_client, exam["id"]) for _ in range(100)]
    _publish(admin_client, exam["id"])

    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)
    attempt_id = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()["attempt_id"]
    url = f"/api/v1/me/attempts/{attempt_id}/answers"

    with count_queries(engine) as first:  # 100 new rows
        r1 = student_client.put(url, json={"client_seq": 1, "answers": [_choice(q, "A") for q in questions]})
    with count_queries(engine) as second:  # the same 100 rows, all changed
        r2 = student_client.put(url, json={"client_seq": 2, "answers": [_choice(q, "B") for q in questions]})
    print(f"\n[query-count] autosave, 100-question exam: first save={len(first)} statements, second save={len(second)} statements")

    assert r1.status_code == 200 and r1.json()["saved"] is True
    assert r2.status_code == 200 and r2.json()["saved"] is True
    saved = student_client.get(f"/api/v1/me/attempts/{attempt_id}").json()["saved_answers"]
    assert saved == {str(q["id"]): _choice(q, "B")["choice_id"] for q in questions}
    assert len(first) <= 12, first
    assert len(second) <= 12, second


def _student_with_exams(admin_client, db_session, code, n_exams):
    """One course with n published exams (one of them group-targeted at a group the student is in)
    and n live sessions."""
    course = _make_course(db_session, title=f"Course {code}")
    student = _make_student(db_session, code=code)
    _enroll(db_session, student, course)
    group = admin_client.post("/api/v1/admin/groups", json={"name": f"Group {code}"}).json()
    added = admin_client.post(f"/api/v1/admin/groups/{group['id']}/members", json={"student_ids": [student.id]})
    assert added.status_code in (200, 201), added.text
    exams = []
    for i in range(n_exams):
        exam = _create_exam_via_api(admin_client, course.id, title=f"Exam {i}", group_id=group["id"] if i == 0 else None)
        _add_text_question(admin_client, exam["id"])
        _publish(admin_client, exam["id"])
        exams.append(exam)
        _create_session(admin_client, course.id, starts_delta=timedelta(hours=i + 1), ends_delta=timedelta(hours=i + 2), title=f"S{i}")
    return student, exams


def _measure_student(client, engine, student, exams, n_submitted):
    student_client = _login_student(client, student.student_code)
    for exam in exams[:n_submitted]:  # some finished attempts, so attempt aggregation has rows to work on
        attempt_id = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()["attempt_id"]
        assert student_client.post(f"/api/v1/me/attempts/{attempt_id}/submit", json={"client_seq": 1, "answers": []}).status_code == 200
    student_client.post(f"/api/v1/me/exams/{exams[-1]['id']}/start")  # and one open attempt

    with count_queries(engine) as listing:
        cards = student_client.get("/api/v1/me/exams")
    with count_queries(engine) as dashboard:
        dash = student_client.get("/api/v1/me/dashboard")
    assert cards.status_code == 200 and dash.status_code == 200
    assert len(cards.json()) == len(exams)
    return len(listing), len(dashboard), cards.json()


def test_student_exam_list_and_dashboard_query_count_does_not_grow_with_exams(admin_client, client, db_session, engine):
    small_student, small_exams = _student_with_exams(admin_client, db_session, "TA-070001", 2)
    big_student, big_exams = _student_with_exams(admin_client, db_session, "TA-070002", 8)

    small = _measure_student(client, engine, small_student, small_exams, n_submitted=1)
    big = _measure_student(client, engine, big_student, big_exams, n_submitted=4)
    print(
        f"\n[query-count] GET /me/exams: 2 exams={small[0]}, 8 exams={big[0]}"
        f"\n[query-count] GET /me/dashboard: 2 exams+2 sessions={small[1]}, 8 exams+8 sessions={big[1]}"
    )

    statuses = {c["title"]: c["status"] for c in big[2]}
    assert [statuses[f"Exam {i}"] for i in range(8)] == ["completed"] * 4 + ["available"] * 3 + ["in_progress"]
    assert small[0] == big[0], (small[0], big[0])
    assert small[1] == big[1], (small[1], big[1])


def _image_exam(admin_client, course_id, n_images):
    """A published exam of n image questions plus one passage with an image."""
    exam = _create_exam_via_api(admin_client, course_id, title=f"Images x{n_images}")
    files = [("files", (f"q{i}.png", FAKE_PNG, "image/png")) for i in range(n_images)]
    assert admin_client.post(f"/api/v1/admin/exams/{exam['id']}/question-images", files=files).status_code == 201
    passage = admin_client.post(f"/api/v1/admin/exams/{exam['id']}/passages", json={"title": "P", "body_text": "t"}).json()["passages"][0]
    assert admin_client.post(f"/api/v1/admin/passages/{passage['id']}/image", files={"file": ("p.png", FAKE_PNG, "image/png")}).status_code == 201
    assert admin_client.post(f"/api/v1/admin/exams/{exam['id']}/answer-key", json={"answers": "A" * n_images}).status_code == 200
    return exam


def test_opening_an_attempt_does_not_query_once_per_image(admin_client, client, db_session, engine, fake_s3):
    course = _make_course(db_session)
    small = _image_exam(admin_client, course.id, 2)
    big = _image_exam(admin_client, course.id, 8)
    student = _make_student(db_session)
    _enroll(db_session, student, course)
    student_client = _login_student(client, student.student_code)

    counts = []
    for exam in (small, big):
        attempt_id = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()["attempt_id"]
        # A real request starts with an empty session; drop the File rows the uploads above left
        # in this shared test session, or db.get() would be served from memory and hide the N+1.
        db_session.expunge_all()
        with count_queries(engine) as statements:
            payload = student_client.get(f"/api/v1/me/attempts/{attempt_id}")
        assert payload.status_code == 200
        urls = [q["image_url"] for q in payload.json()["questions"]] + [p["image_url"] for p in payload.json()["passages"]]
        assert all(urls) and len(set(urls)) == len(urls)
        counts.append(len(statements))
    print(f"\n[query-count] GET /me/attempts/{{id}}: 2 images+1 passage image={counts[0]}, 8 images+1 passage image={counts[1]}")
    assert counts[0] == counts[1], counts
