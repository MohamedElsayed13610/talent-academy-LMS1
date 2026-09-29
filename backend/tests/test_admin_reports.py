"""Phase 8: /admin/reports/students[.xlsx], /admin/students/{id}/points,
/admin/exams/{id}/results[.xlsx] (ARCHITECTURE.md §5.2, §5.3)."""

from starlette.testclient import TestClient

from app.core.search import normalize_search_text
from app.core.security import hash_password
from app.db.scope import get_default_academy_id
from app.main import app as fastapi_app
from app.models.courses import Course, CourseAccent, Lesson, Section
from app.models.groups import Enrollment
from app.models.identity import StudentProfile, StudentType, SubscriptionStatus, User, UserRole


def _make_course(db_session, title="Course A"):
    academy_id = get_default_academy_id(db_session)
    course = Course(academy_id=academy_id, title=title, title_search=normalize_search_text(title), subject="Math", accent=CourseAccent.blue, is_published=True)
    db_session.add(course)
    db_session.commit()
    return course


def _make_student(db_session, code):
    academy_id = get_default_academy_id(db_session)
    user = User(academy_id=academy_id, role=UserRole.student, full_name=f"طالب {code}", full_name_search=normalize_search_text(f"طالب {code}"), student_code=code, password_hash=hash_password("Whatever123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(StudentProfile(user_id=user.id, student_type=StudentType.academy, subscription_status=SubscriptionStatus.active))
    db_session.commit()
    return user


def _login_student(code):
    from tests.conftest import AuthedClient

    student_client = TestClient(fastapi_app)
    response = student_client.post("/api/v1/auth/login", json={"identifier": code, "password": "Whatever123!"})
    assert response.status_code == 200, response.text
    return AuthedClient(student_client)


def _create_exam_via_api(admin_client, course_id, **overrides):
    payload = {"title": "Report Exam", "course_id": course_id, "exam_mode": "answer_sheet", "duration_minutes": 30, "passing_score": 50, "max_attempts": 2}
    payload.update(overrides)
    response = admin_client.post("/api/v1/admin/exams", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _add_text_question(admin_client, exam_id, correct="A"):
    payload = {
        "question_type": "text_mcq", "prompt_text": "2 + 2 = ?",
        "choices": [{"label": "A", "text": "4"}, {"label": "B", "text": "3"}, {"label": "C", "text": "5"}, {"label": "D", "text": "6"}],
        "correct_label": correct, "topic": "Arithmetic", "difficulty": "easy", "points": 1,
    }
    response = admin_client.post(f"/api/v1/admin/exams/{exam_id}/questions", json=payload)
    assert response.status_code == 201, response.text
    return sorted(response.json()["questions"], key=lambda q: q["position"])[-1]


def test_student_reports_list_computes_progress_and_exam_average(admin_client, db_session):
    course = _make_course(db_session)
    section = Section(course_id=course.id, title="Sec", position=1)
    db_session.add(section)
    db_session.flush()
    lesson1 = Lesson(section_id=section.id, title="L1", duration_minutes=10, position=1)
    lesson2 = Lesson(section_id=section.id, title="L2", duration_minutes=10, position=2)
    db_session.add_all([lesson1, lesson2])
    db_session.commit()

    student = _make_student(db_session, "TA-082001")
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()
    student_client = _login_student(student.student_code)
    assert student_client.put(f"/api/v1/me/lessons/{lesson1.id}/progress", json={"completed": True}).status_code == 200

    exam = _create_exam_via_api(admin_client, course.id)
    question = _add_text_question(admin_client, exam["id"])
    admin_client.post(f"/api/v1/admin/exams/{exam['id']}/publish")
    attempt = student_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()
    choice_a = next(c for c in question["choices"] if c["label"] == "A")
    submit = student_client.post(f"/api/v1/me/attempts/{attempt['attempt_id']}/submit", json={"client_seq": 1, "answers": [{"question_id": question["id"], "choice_id": choice_a["id"]}]})
    assert submit.status_code == 200

    report = admin_client.get(f"/api/v1/admin/reports/students?course_id={course.id}")
    assert report.status_code == 200, report.text
    row = next(r for r in report.json()["items"] if r["student"]["id"] == student.id)
    assert row["overall_progress"] == 50  # 1 of 2 lessons
    assert row["completed_lessons"] == 1 and row["total_lessons"] == 2
    assert row["exams_taken"] == 1
    assert row["exam_average"] == 100.0
    assert row["total_points"] > 0


def test_student_report_detail_shape(admin_client, db_session):
    course = _make_course(db_session)
    student = _make_student(db_session, "TA-082002")
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()

    detail = admin_client.get(f"/api/v1/admin/reports/students/{student.id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["student"]["id"] == student.id
    assert any(c["course_id"] == course.id for c in body["courses"])
    assert body["attendance"]["rate"] == 0
    assert body["whatsapp_summary_text"]


def test_reports_xlsx_exports_smoke(admin_client, db_session):
    student = _make_student(db_session, "TA-082003")

    list_xlsx = admin_client.get("/api/v1/admin/reports/students.xlsx")
    assert list_xlsx.status_code == 200
    assert "spreadsheetml" in list_xlsx.headers["content-type"]

    detail_xlsx = admin_client.get(f"/api/v1/admin/reports/students/{student.id}.xlsx")
    assert detail_xlsx.status_code == 200
    assert "spreadsheetml" in detail_xlsx.headers["content-type"]


def test_student_period_report_filters_by_date_range(admin_client, db_session):
    from datetime import timedelta

    from app.core.time import utcnow

    course = _make_course(db_session)
    section = Section(course_id=course.id, title="Sec", position=1)
    db_session.add(section)
    db_session.flush()
    lesson = Lesson(section_id=section.id, title="L1", duration_minutes=10, position=1)
    db_session.add(lesson)
    db_session.commit()

    student = _make_student(db_session, "TA-082020")
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()
    student_client = _login_student(student.student_code)
    assert student_client.put(f"/api/v1/me/lessons/{lesson.id}/progress", json={"completed": True}).status_code == 200

    now = utcnow()
    all_time = admin_client.get(f"/api/v1/admin/reports/students/{student.id}/period")
    assert all_time.status_code == 200, all_time.text
    assert len(all_time.json()["completed_lessons"]) == 1

    future_only = admin_client.get(
        f"/api/v1/admin/reports/students/{student.id}/period",
        params={"date_from": (now + timedelta(days=1)).isoformat()},
    )
    assert future_only.status_code == 200
    assert future_only.json()["completed_lessons"] == []
    assert future_only.json()["points_total"] == 0

    invalid_range = admin_client.get(
        f"/api/v1/admin/reports/students/{student.id}/period",
        params={"date_from": now.isoformat(), "date_to": (now - timedelta(days=1)).isoformat()},
    )
    assert invalid_range.status_code == 422


def test_student_period_pdf_export_smoke(admin_client, db_session):
    student = _make_student(db_session, "TA-082021")
    response = admin_client.get(f"/api/v1/admin/reports/students/{student.id}.pdf")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_admin_student_points_history(admin_client, db_session):
    course = _make_course(db_session)
    section = Section(course_id=course.id, title="Sec", position=1)
    db_session.add(section)
    db_session.flush()
    lesson = Lesson(section_id=section.id, title="L1", duration_minutes=10, position=1)
    db_session.add(lesson)
    db_session.commit()

    student = _make_student(db_session, "TA-082004")
    db_session.add(Enrollment(user_id=student.id, course_id=course.id))
    db_session.commit()
    student_client = _login_student(student.student_code)
    student_client.put(f"/api/v1/me/lessons/{lesson.id}/progress", json={"completed": True})

    history = admin_client.get(f"/api/v1/admin/students/{student.id}/points")
    assert history.status_code == 200, history.text
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["course_title"] == course.title


def test_exam_results_lists_every_eligible_student_with_status(admin_client, db_session):
    course = _make_course(db_session)
    exam = _create_exam_via_api(admin_client, course.id, max_attempts=1)
    question = _add_text_question(admin_client, exam["id"])
    admin_client.post(f"/api/v1/admin/exams/{exam['id']}/publish")

    not_taken = _make_student(db_session, "TA-082010")
    submitter = _make_student(db_session, "TA-082011")
    db_session.add(Enrollment(user_id=not_taken.id, course_id=course.id))
    db_session.add(Enrollment(user_id=submitter.id, course_id=course.id))
    db_session.commit()

    submitter_client = _login_student(submitter.student_code)
    attempt = submitter_client.post(f"/api/v1/me/exams/{exam['id']}/start").json()
    choice_a = next(c for c in question["choices"] if c["label"] == "A")
    submitter_client.post(f"/api/v1/me/attempts/{attempt['attempt_id']}/submit", json={"client_seq": 1, "answers": [{"question_id": question["id"], "choice_id": choice_a["id"]}]})

    results = admin_client.get(f"/api/v1/admin/exams/{exam['id']}/results")
    assert results.status_code == 200, results.text
    by_student = {r["student_id"]: r for r in results.json()}
    assert by_student[not_taken.id]["status"] == "not_taken"
    assert by_student[not_taken.id]["attempts_used"] == 0
    assert by_student[submitter.id]["status"] == "submitted"
    assert by_student[submitter.id]["best"] == 100

    filtered = admin_client.get(f"/api/v1/admin/exams/{exam['id']}/results?status=not_taken")
    assert filtered.status_code == 200
    assert {r["student_id"] for r in filtered.json()} == {not_taken.id}

    xlsx = admin_client.get(f"/api/v1/admin/exams/{exam['id']}/results.xlsx")
    assert xlsx.status_code == 200
    assert "spreadsheetml" in xlsx.headers["content-type"]
