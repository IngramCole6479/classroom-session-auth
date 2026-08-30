from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    salt_hex, expected = encoded.split(":", 1)
    actual = _password_hash(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
    return hmac.compare_digest(actual, expected)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class DeliveryDecision:
    assignment_id: int
    title: str
    due_at: str
    submitted_at: str | None
    status: str


class CourseService:
    def __init__(self, database: str):
        self.database = database
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL, password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('learner', 'educator'))
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                    expires_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL, educator_id INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS enrollments (
                    course_id INTEGER NOT NULL, learner_id INTEGER NOT NULL,
                    PRIMARY KEY(course_id, learner_id)
                );
                CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL,
                    title TEXT NOT NULL, due_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS submissions (
                    assignment_id INTEGER NOT NULL, learner_id INTEGER NOT NULL,
                    submitted_at TEXT NOT NULL,
                    PRIMARY KEY(assignment_id, learner_id)
                );
                """
            )

    def create_user(self, email: str, name: str, password: str, role: str = "learner") -> int:
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO users(email, name, password_hash, role) VALUES (?, ?, ?, ?)",
                (email.lower(), name, _password_hash(password), role),
            )
            return int(cursor.lastrowid)

    def login(self, email: str, password: str, expires_at: datetime) -> str | None:
        with self._connect() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
            if not user or not _password_matches(password, user["password_hash"]):
                return None
            token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (_token_hash(token), user["id"], expires_at.isoformat()),
            )
            return token

    def user_for_session(self, token: str, now: datetime) -> sqlite3.Row | None:
        with self._connect() as db:
            return db.execute(
                """SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id
                   WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
                (_token_hash(token), now.isoformat()),
            ).fetchone()

    def learner_schedule(
        self, learner_id: int, now: datetime, course_id: int | None = None
    ) -> list[DeliveryDecision]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT assignments.id, assignments.title, assignments.due_at,
                          submissions.submitted_at
                   FROM assignments
                   JOIN enrollments ON enrollments.course_id = assignments.course_id
                   LEFT JOIN submissions ON submissions.assignment_id = assignments.id
                     AND submissions.learner_id = enrollments.learner_id
                   WHERE enrollments.learner_id = ?
                     AND (? IS NULL OR assignments.course_id = ?)
                   ORDER BY assignments.due_at""",
                (learner_id, course_id, course_id),
            ).fetchall()
        return [self._delivery(row, now) for row in rows]

    @staticmethod
    def _delivery(row: sqlite3.Row, now: datetime) -> DeliveryDecision:
        submitted = row["submitted_at"]
        due_at = datetime.fromisoformat(row["due_at"])
        if submitted:
            status = "submitted"
        elif due_at < now:
            status = "overdue"
        else:
            status = "due"
        return DeliveryDecision(row["id"], row["title"], row["due_at"], submitted, status)

    def educator_report(self, educator_id: int, course_id: int, now: datetime) -> dict[str, int]:
        with self._connect() as db:
            owner = db.execute(
                "SELECT 1 FROM courses WHERE id = ? AND educator_id = ?", (course_id, educator_id)
            ).fetchone()
            if not owner:
                raise PermissionError("course is not assigned to this educator")
            learner_ids = [
                row[0]
                for row in db.execute(
                    "SELECT learner_id FROM enrollments WHERE course_id = ?", (course_id,)
                ).fetchall()
            ]
        decisions = [
            item
            for learner in learner_ids
            for item in self.learner_schedule(learner, now, course_id)
        ]
        return {
            "learners": len(learner_ids),
            "submitted": sum(item.status == "submitted" for item in decisions),
            "overdue": sum(item.status == "overdue" for item in decisions),
            "due": sum(item.status == "due" for item in decisions),
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
