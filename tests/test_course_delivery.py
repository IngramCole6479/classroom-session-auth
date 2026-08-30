from datetime import datetime, timezone

from classroom_auth.course_service import CourseService


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def test_schedule_and_report_separate_overdue_from_submitted(tmp_path):
    courses = CourseService(str(tmp_path / "classroom.db"))
    educator = courses.create_user("ada@example.edu", "Ada", "educator-passphrase", "educator")
    learner = courses.create_user("lin@example.edu", "Lin", "learner-passphrase")

    with courses._connect() as db:
        course = db.execute(
            "INSERT INTO courses(title, educator_id) VALUES (?, ?)", ("Data Ethics", educator)
        ).lastrowid
        db.execute("INSERT INTO enrollments(course_id, learner_id) VALUES (?, ?)", (course, learner))
        late = db.execute(
            "INSERT INTO assignments(course_id, title, due_at) VALUES (?, ?, ?)",
            (course, "Consent review", "2026-08-28T12:00:00+00:00"),
        ).lastrowid
        done = db.execute(
            "INSERT INTO assignments(course_id, title, due_at) VALUES (?, ?, ?)",
            (course, "Dataset memo", "2026-08-30T12:00:00+00:00"),
        ).lastrowid
        db.execute(
            "INSERT INTO submissions(assignment_id, learner_id, submitted_at) VALUES (?, ?, ?)",
            (done, learner, "2026-08-29T09:00:00+00:00"),
        )

    schedule = courses.learner_schedule(learner, NOW)

    assert [(item.assignment_id, item.status) for item in schedule] == [
        (late, "overdue"),
        (done, "submitted"),
    ]
    assert courses.educator_report(educator, course, NOW) == {
        "learners": 1,
        "submitted": 1,
        "overdue": 1,
        "due": 0,
    }
