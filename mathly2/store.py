"""Where classes, students, roles and learning progress are kept. Two stores with the same methods:
InMemoryStore (tests and local development, lost on restart) and SupabaseStore (PostgREST with the secret key)."""
from __future__ import annotations

import itertools
import json
import threading
import urllib.error
import urllib.parse
import uuid
from datetime import date, datetime, timezone

from . import pooled

TIMEOUT = 10


class StoreUnavailable(RuntimeError):
    """The database could not be reached or refused the request."""


class ClassExists(ValueError):
    """The teacher already has a class with this name."""


class MemberExists(ValueError):
    """The email already belongs to this class."""


class TeacherIsStudent(ValueError):
    """A class's teacher cannot also be one of its students."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# What the server keeps about one student and one skill (table m2_skill_progress). `mastered_at` is set once.
PROGRESS_FIELDS = ("current_key", "current_helped", "started_at", "mastered_at", "round_start")
PROGRESS_DEFAULTS = {"current_key": None, "current_helped": False, "started_at": None, "mastered_at": None, "round_start": None}


ATTEMPT_FIELDS = {"answers", "submitted_at", "timed_out", "grade"}


def _copy_attempt(row: dict) -> dict:
    return {**row, "questions": [dict(q) for q in row["questions"]], "answers": dict(row["answers"])}


def _when(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _attempt_row(row: dict) -> dict:
    """A database row as the in-memory store gives it: real datetimes, plain lists and dicts."""
    return {**row, "started_at": _when(row["started_at"]), "due_at": _when(row["due_at"]), "submitted_at": _when(row.get("submitted_at")),
            "questions": list(row.get("questions") or []), "answers": dict(row.get("answers") or {})}


TEST_FIELDS = {"date", "lessons", "note", "questions", "minutes"}


def _check_test(fields: dict) -> None:
    """The limits the database enforces too: 1-40 questions, 5-180 minutes, at least one lesson."""
    if "questions" in fields and not 1 <= fields["questions"] <= 40:
        raise ValueError("questions must be 1-40")
    if "minutes" in fields and not 5 <= fields["minutes"] <= 180:
        raise ValueError("minutes must be 5-180")
    if "lessons" in fields and not fields["lessons"]:
        raise ValueError("a test covers at least one lesson")


def _test_row(row: dict) -> dict:
    """A database row as the in-memory store gives it: a real date and datetimes, a plain list."""
    day = row["date"] if isinstance(row["date"], date) else date.fromisoformat(str(row["date"])[:10])
    return {**row, "date": day, "lessons": list(row.get("lessons") or []), "created_at": _when(row["created_at"]), "removed_at": _when(row.get("removed_at"))}


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._classes: dict[int, dict] = {}
        self._members: dict[tuple[int, str], dict] = {}   # (class_id, email) -> row
        self._roles: dict[tuple[str, str], dict] = {}     # (email, role) -> row
        self._progress: dict[tuple[str, str], dict] = {}   # (user_id, skill_id) -> row
        self._answers: list[dict] = []
        self._comets: dict[str, dict[str, str]] = {}       # user_id -> {comet_id: caught_at}
        self._attempts: dict[str, dict] = {}                # attempt id -> row
        self._reward: dict[str, dict] = {}                 # user_id -> {last_comet_day, last_catch_day}
        self._tests: dict[int, dict] = {}                   # test id -> row

    # --- classes ---

    def _students(self, class_id: int) -> int:
        return sum(1 for (c, _) in self._members if c == class_id)

    def _row(self, row: dict) -> dict:
        return {**row, "lessons": list(row["lessons"]), "students": self._students(row["id"])}

    def _taken(self, name: str, except_id: int | None = None) -> bool:
        return any(c["name"].lower() == name.lower() and c["id"] != except_id for c in self._classes.values())

    def create_class(self, created_by: str, name: str, *, lessons=(), teacher_email: str | None = None,
                     ai_enabled: bool = False, ai_daily_checks: int = 150) -> dict:
        with self._lock:
            if self._taken(name):
                raise ClassExists(name)
            row = {"id": next(self._ids), "name": name, "created_by": created_by, "teacher_email": teacher_email,
                   "lessons": list(lessons), "ai_enabled": ai_enabled, "ai_daily_checks": ai_daily_checks,
                   "created_at": _now()}
            self._classes[row["id"]] = row
            return self._row(row)

    def update_class(self, class_id: int, **fields) -> dict:
        unknown = set(fields) - {"name", "lessons", "teacher_email", "ai_enabled", "ai_daily_checks"}
        if unknown:
            raise ValueError(f"unknown class fields {sorted(unknown)}")
        with self._lock:
            row = self._classes.get(class_id)
            if row is None:
                raise KeyError(class_id)
            if "name" in fields and self._taken(fields["name"], class_id):
                raise ClassExists(fields["name"])
            teacher = fields.get("teacher_email", row["teacher_email"])
            if teacher and (class_id, teacher) in self._members:
                raise TeacherIsStudent(teacher)
            row.update({k: (list(v) if k == "lessons" else v) for k, v in fields.items()})
            return self._row(row)

    def delete_class(self, class_id: int) -> bool:
        with self._lock:
            if self._classes.pop(class_id, None) is None:
                return False
            for key in [k for k in self._members if k[0] == class_id]:
                del self._members[key]
            return True

    def get_class(self, class_id: int) -> dict | None:
        with self._lock:
            row = self._classes.get(class_id)
            return self._row(row) if row else None

    def classes(self) -> list[dict]:
        with self._lock:
            return [self._row(c) for c in self._classes.values()]

    def classes_taught(self, email: str) -> list[dict]:
        with self._lock:
            return [self._row(c) for c in self._classes.values() if c["teacher_email"] == email]

    # --- students ---

    def members(self, class_id: int) -> list[dict]:
        with self._lock:
            rows = [m for (c, _), m in self._members.items() if c == class_id]
            return [{"email": m["email"], "user_id": m["user_id"], "added_at": m["added_at"]}
                    for m in sorted(rows, key=lambda m: (m["added_at"], m["email"]))]

    def classes_of_student(self, email: str) -> list[dict]:
        with self._lock:
            return [{"id": c["id"], "name": c["name"], "lessons": list(c["lessons"])}
                    for (cid, e), _ in self._members.items() if e == email for c in [self._classes[cid]]]

    def add_member(self, class_id: int, email: str) -> None:
        with self._lock:
            if self._classes[class_id]["teacher_email"] == email:
                raise TeacherIsStudent(email)
            if (class_id, email) in self._members:
                raise MemberExists(email)
            user_id = next((m["user_id"] for (_, e), m in self._members.items() if e == email and m["user_id"]), None)
            self._members[(class_id, email)] = {"class_id": class_id, "email": email, "user_id": user_id, "added_at": _now()}

    def remove_member(self, class_id: int, email: str) -> bool:
        with self._lock:
            return self._members.pop((class_id, email), None) is not None

    def link_user(self, email: str, user_id: str) -> None:
        with self._lock:
            for (_, e), row in self._members.items():
                if e == email and not row["user_id"]:
                    row["user_id"] = user_id

    def all_students(self) -> list[dict]:
        with self._lock:
            found: dict[str, list[str]] = {}
            for (cid, email) in self._members:
                found.setdefault(email, []).append(self._classes[cid]["name"])
            return [{"email": e, "classes": sorted(names)} for e, names in sorted(found.items())]

    # --- roles (given by an admin; the settings add developers and the first admins) ---

    def roles_of(self, email: str) -> set[str]:
        with self._lock:
            return {role for (e, role) in self._roles if e == email}

    def give_role(self, email: str, role: str, granted_by: str) -> None:
        with self._lock:
            self._roles.setdefault((email, role), {"email": email, "role": role, "granted_by": granted_by, "granted_at": _now()})

    def take_role(self, email: str, role: str, settings_admins: int = 0) -> str:
        """"removed", "absent", or "last_admin" (nothing was removed): the last admin keeps the role.
        `settings_admins` counts the admins named in the app's settings, who stay admins whatever the table says."""
        with self._lock:
            if (email, role) not in self._roles:
                return "absent"
            if role == "admin":
                others = sum(1 for (e, r) in self._roles if r == "admin" and e != email)
                if others + settings_admins == 0:
                    return "last_admin"
            del self._roles[(email, role)]
            return "removed"

    def accounts(self) -> list[dict]:
        """Every email the app knows (a role, a class entry or a class's teacher) with the roles given in the table."""
        with self._lock:
            known = {e for (e, _) in self._roles} | {e for (_, e) in self._members}
            known |= {c["teacher_email"] for c in self._classes.values() if c["teacher_email"]}
            return [{"email": e, "roles": sorted(r for (x, r) in self._roles if x == e)} for e in sorted(known)]

    # --- skill learning ---

    def get_progress(self, user_id: str, skill_id: str) -> dict | None:
        with self._lock:
            row = self._progress.get((user_id, skill_id))
            return dict(row) if row else None

    def save_progress(self, user_id: str, skill_id: str, **fields) -> dict:
        """Create the row if needed, then set the given fields; the others stay as they are."""
        unknown = set(fields) - set(PROGRESS_FIELDS)
        if unknown:
            raise ValueError(f"unknown progress fields {sorted(unknown)}")
        with self._lock:
            row = self._progress.setdefault((user_id, skill_id), {"user_id": user_id, "skill_id": skill_id,
                                                                   **PROGRESS_DEFAULTS})
            row.update(fields)
            return dict(row)

    def progress_of(self, user_id: str) -> list[dict]:
        with self._lock:
            return [dict(r) for (u, _), r in self._progress.items() if u == user_id]

    def add_answer(self, user_id: str, skill_id: str, question_key: str, correct: bool, counted: bool,
                   mistake_id: str | None, day: date) -> None:
        with self._lock:
            self._answers.append({"id": len(self._answers) + 1, "user_id": user_id, "skill_id": skill_id,
                                  "question_key": question_key, "correct": correct, "counted": counted,
                                  "mistake_id": mistake_id, "day": day})

    def last_counted_answers(self, user_id: str, skill_id: str, n: int) -> list[dict]:
        """The last `n` answers that were not given with help, oldest first."""
        with self._lock:
            rows = [a for a in self._answers if a["user_id"] == user_id and a["skill_id"] == skill_id and a["counted"]]
            return [{"question_key": a["question_key"], "correct": a["correct"], "day": a["day"]} for a in rows[-n:]]

    def answer_counts(self, user_id: str, skill_id: str) -> dict[str, int]:
        with self._lock:
            counts: dict[str, int] = {}
            for a in self._answers:
                if a["user_id"] == user_id and a["skill_id"] == skill_id:
                    counts[a["question_key"]] = counts.get(a["question_key"], 0) + 1
            return counts

    def answers_of(self, user_id: str, skill_id: str) -> list[dict]:
        """All the student's answers on a skill, oldest first: question_key, correct, counted, day. One read gives what mastery,
        the next question and the progress need."""
        with self._lock:
            return [{k: a[k] for k in ("question_key", "correct", "counted", "day", "mistake_id")} for a in self._answers
                    if a["user_id"] == user_id and a["skill_id"] == skill_id]

    def recent_skills(self, user_id: str, n: int = 20) -> list[str]:
        """The skills the student answered most recently, newest first, each once (helped and wrong answers count)."""
        with self._lock:
            found: list[str] = []
            for a in reversed(self._answers):
                if a["user_id"] == user_id and a["skill_id"] not in found:
                    found.append(a["skill_id"])
                    if len(found) == n:
                        break
            return found

    def solved_keys(self, user_id: str, skill_id: str) -> set[str]:
        """The questions of a skill the student has answered correctly at least once (with or without help)."""
        with self._lock:
            return {a["question_key"] for a in self._answers
                    if a["user_id"] == user_id and a["skill_id"] == skill_id and a["correct"]}

    # --- real tests (a teacher sets them for a class) ---

    def create_test(self, class_id: int, test_day: date, lessons: list[str], created_by: str, *, note: str = "", questions: int = 12,
                    minutes: int = 45, created_at: datetime | None = None) -> dict:
        fields = {"lessons": list(lessons), "questions": questions, "minutes": minutes}
        _check_test(fields)
        with self._lock:
            row = {"id": next(self._ids), "class_id": class_id, "date": test_day, **fields, "note": note, "created_by": created_by,
                   "created_at": created_at or datetime.now(timezone.utc), "removed_at": None}
            self._tests[row["id"]] = row
            return dict(row, lessons=list(row["lessons"]))

    def get_test(self, test_id: int) -> dict | None:
        with self._lock:
            row = self._tests.get(test_id)
            return dict(row, lessons=list(row["lessons"])) if row else None

    def update_test(self, test_id: int, **fields) -> dict:
        unknown = set(fields) - TEST_FIELDS
        if unknown:
            raise ValueError(f"unknown test fields {sorted(unknown)}")
        _check_test(fields)
        with self._lock:
            row = self._tests.get(test_id)
            if row is None or row["removed_at"]:
                raise KeyError(test_id)
            row.update({k: (list(v) if k == "lessons" else v) for k, v in fields.items()})
            return dict(row, lessons=list(row["lessons"]))

    def remove_test(self, test_id: int, at: datetime | None = None) -> bool:
        """Soft delete: the test disappears from lists, grades already earned keep its name."""
        with self._lock:
            row = self._tests.get(test_id)
            if row is None or row["removed_at"]:
                return False
            row["removed_at"] = at or datetime.now(timezone.utc)
            return True

    def tests_of_classes(self, class_ids, include_removed: bool = False) -> list[dict]:
        """The tests of these classes, the nearest date first."""
        wanted = set(class_ids)
        with self._lock:
            rows = [r for r in self._tests.values() if r["class_id"] in wanted and (include_removed or not r["removed_at"])]
            return [dict(r, lessons=list(r["lessons"])) for r in sorted(rows, key=lambda r: (r["date"], r["id"]))]

    # --- timed attempts (quizzes; later exercise tests and the simulation) ---

    def create_attempt(self, user_id: str, kind: str, scope: str, started_at: datetime, due_at: datetime, questions: list[dict]) -> dict:
        row = {"id": str(uuid.uuid4()), "user_id": user_id, "kind": kind, "scope": scope, "started_at": started_at, "due_at": due_at,
               "submitted_at": None, "timed_out": False, "grade": None, "questions": [dict(q) for q in questions], "answers": {}}
        with self._lock:
            self._attempts[row["id"]] = row
            return _copy_attempt(row)

    def get_attempt(self, attempt_id: str) -> dict | None:
        with self._lock:
            row = self._attempts.get(str(attempt_id))
            return _copy_attempt(row) if row else None

    def save_attempt(self, attempt_id: str, **fields) -> dict:
        """Update `answers`, `submitted_at`, `timed_out` and/or `grade`."""
        unknown = set(fields) - ATTEMPT_FIELDS
        if unknown:
            raise ValueError(f"unknown attempt fields {sorted(unknown)}")
        with self._lock:
            row = self._attempts.get(str(attempt_id))
            if row is None:
                raise KeyError(attempt_id)
            row.update({k: (dict(v) if k == "answers" else v) for k, v in fields.items()})
            return _copy_attempt(row)

    def attempts_of(self, user_id: str, kind: str, scope: str | None = None) -> list[dict]:
        """A student's attempts of one kind (of one scope, when given), oldest first."""
        with self._lock:
            rows = [r for r in self._attempts.values() if r["user_id"] == user_id and r["kind"] == kind and (scope is None or r["scope"] == scope)]
            return [_copy_attempt(r) for r in sorted(rows, key=lambda r: r["started_at"])]

    def comets_of(self, user_id: str) -> set[str]:
        with self._lock:
            return set(self._comets.get(user_id, {}))

    def add_comet(self, user_id: str, comet_id: str) -> None:
        with self._lock:
            self._comets.setdefault(user_id, {}).setdefault(comet_id, datetime.now(timezone.utc).isoformat())

    def reward_state(self, user_id: str) -> dict | None:
        with self._lock:
            row = self._reward.get(user_id)
            return dict(row) if row else None

    def save_reward_state(self, user_id: str, **fields) -> dict:
        """Set `last_comet_day` and/or `last_catch_day`; the other field stays as it was."""
        with self._lock:
            row = self._reward.setdefault(user_id, {"user_id": user_id, "last_comet_day": None, "last_catch_day": None})
            row.update(fields)
            return dict(row)

    def last_answered(self, user_id: str) -> dict[str, date]:
        """The day of the student's newest answer on each skill (helped and wrong answers count): what fading reads."""
        with self._lock:
            days: dict[str, date] = {}
            for a in self._answers:
                if a["user_id"] == user_id and (a["skill_id"] not in days or a["day"] > days[a["skill_id"]]):
                    days[a["skill_id"]] = a["day"]
            return days

    def daily_correct(self, user_id: str) -> dict[date, int]:
        """Correct practice answers per day (helped answers included): the daily goal and the streak."""
        with self._lock:
            counts: dict[date, int] = {}
            for a in self._answers:
                if a["user_id"] == user_id and a["correct"]:
                    counts[a["day"]] = counts.get(a["day"], 0) + 1
            return counts


class SupabaseStore:
    def __init__(self, url: str, secret: str) -> None:
        self.url, self.secret = url.rstrip("/"), secret

    def _request(self, method: str, table: str, params: dict[str, str] | None = None, body: dict | None = None,
                 returning: bool = False, upsert: bool = False):
        query = "&".join(f"{k}={urllib.parse.quote(v, safe='(),.*:')}" for k, v in (params or {}).items())
        headers = {"apikey": self.secret, "Authorization": f"Bearer {self.secret}", "User-Agent": "mathly2/1.0",
                   "Content-Type": "application/json"}
        prefer = []
        if upsert:
            prefer.append("resolution=merge-duplicates")
        if returning:
            prefer.append("return=representation")
        if prefer:
            headers["Prefer"] = ",".join(prefer)
        data = json.dumps(body).encode() if body is not None else None
        try:
            _, raw = pooled.request(method, f"{self.url}/rest/v1/{table}" + (f"?{query}" if query else ""), headers, data, TIMEOUT)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 409):   # a conflict, or one of the database's own refusals (see _why)
                raise
            raise StoreUnavailable(f"supabase answered {exc.code} for {method} {table}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise StoreUnavailable(str(exc)) from exc
        return json.loads(raw) if raw else None

    @staticmethod
    def _eq(value) -> str:
        return f"eq.{value}"

    @staticmethod
    def _why(exc: urllib.error.HTTPError) -> str:
        """The database's own message for a refusal, or empty if it sent none. The body can be read only once, so it is kept."""
        if not hasattr(exc, "_mathly_why"):
            try:
                exc._mathly_why = str(json.loads(exc.read() or b"{}").get("message", ""))
            except (ValueError, AttributeError, OSError):
                exc._mathly_why = ""
        return exc._mathly_why

    def _refused(self, exc: urllib.error.HTTPError, conflict: Exception) -> Exception:
        """A 409 is the conflict the caller expects (a name or an entry that already exists). Anything else the database refused
        (a missing column because a migration was not applied, bad data) is a failure to report, not a name clash."""
        if exc.code == 409:
            return conflict
        return StoreUnavailable(f"supabase refused ({exc.code}): {self._why(exc) or exc.reason}")

    _CLASS = "id,name,created_by,teacher_email,lessons,ai_enabled,ai_daily_checks,created_at"

    def _class_row(self, row: dict) -> dict:
        count = (row.get("m2_class_members") or [{"count": 0}])[0]["count"]
        return {**{k: row[k] for k in self._CLASS.split(",")}, "students": count}

    # --- classes ---

    def create_class(self, created_by: str, name: str, *, lessons=(), teacher_email: str | None = None,
                     ai_enabled: bool = False, ai_daily_checks: int = 150) -> dict:
        body = {"created_by": created_by, "name": name, "lessons": list(lessons), "teacher_email": teacher_email,
                "ai_enabled": ai_enabled, "ai_daily_checks": ai_daily_checks}
        try:
            rows = self._request("POST", "m2_classes", body=body, returning=True)
        except urllib.error.HTTPError as exc:
            raise self._refused(exc, ClassExists(name)) from exc
        return {**rows[0], "students": 0}

    def update_class(self, class_id: int, **fields) -> dict:
        unknown = set(fields) - {"name", "lessons", "teacher_email", "ai_enabled", "ai_daily_checks"}
        if unknown:
            raise ValueError(f"unknown class fields {sorted(unknown)}")
        try:
            rows = self._request("PATCH", "m2_classes", {"id": self._eq(class_id)}, fields, returning=True)
        except urllib.error.HTTPError as exc:
            if "teacher_is_student" in self._why(exc):
                raise TeacherIsStudent(str(fields.get("teacher_email"))) from exc
            raise self._refused(exc, ClassExists(str(fields.get("name")))) from exc
        if not rows:
            raise KeyError(class_id)
        return self.get_class(class_id)

    def delete_class(self, class_id: int) -> bool:
        return bool(self._request("DELETE", "m2_classes", {"id": self._eq(class_id)}, returning=True))

    def get_class(self, class_id: int) -> dict | None:
        rows = self._request("GET", "m2_classes", {"id": self._eq(class_id), "select": f"{self._CLASS},m2_class_members(count)"})
        return self._class_row(rows[0]) if rows else None

    def classes(self) -> list[dict]:
        rows = self._request("GET", "m2_classes", {"select": f"{self._CLASS},m2_class_members(count)", "order": "id"})
        return [self._class_row(r) for r in rows]

    def classes_taught(self, email: str) -> list[dict]:
        rows = self._request("GET", "m2_classes", {"teacher_email": self._eq(email),
                             "select": f"{self._CLASS},m2_class_members(count)", "order": "id"})
        return [self._class_row(r) for r in rows]

    # --- students ---

    def members(self, class_id: int) -> list[dict]:
        return self._request("GET", "m2_class_members", {"class_id": self._eq(class_id),
                             "select": "email,user_id,added_at", "order": "added_at,email"})

    def classes_of_student(self, email: str) -> list[dict]:
        rows = self._request("GET", "m2_class_members", {"email": self._eq(email), "select": "m2_classes(id,name,lessons)"})
        return [r["m2_classes"] for r in rows]

    def add_member(self, class_id: int, email: str) -> None:
        try:
            self._request("POST", "m2_class_members", body={"class_id": class_id, "email": email})
        except urllib.error.HTTPError as exc:
            if "teacher_is_student" in self._why(exc):
                raise TeacherIsStudent(email) from exc
            raise self._refused(exc, MemberExists(email)) from exc

    def remove_member(self, class_id: int, email: str) -> bool:
        rows = self._request("DELETE", "m2_class_members", {"class_id": self._eq(class_id), "email": self._eq(email)},
                             returning=True)
        return bool(rows)

    def link_user(self, email: str, user_id: str) -> None:
        self._request("PATCH", "m2_class_members", {"email": self._eq(email), "user_id": "is.null"}, {"user_id": user_id})

    def all_students(self) -> list[dict]:
        rows = self._request("GET", "m2_class_members", {"select": "email,m2_classes(name)", "order": "email"})
        found: dict[str, list[str]] = {}
        for r in rows:
            found.setdefault(r["email"], []).append(r["m2_classes"]["name"])
        return [{"email": e, "classes": sorted(names)} for e, names in found.items()]

    # --- roles ---

    def roles_of(self, email: str) -> set[str]:
        return {r["role"] for r in self._request("GET", "m2_roles", {"email": self._eq(email), "select": "role"})}

    def give_role(self, email: str, role: str, granted_by: str) -> None:
        self._request("POST", "m2_roles", {"on_conflict": "email,role"},
                      {"email": email, "role": role, "granted_by": granted_by}, upsert=True)

    def take_role(self, email: str, role: str, settings_admins: int = 0) -> str:
        """One call in the database counts the admins and deletes together (function m2_take_role), so two admins
        removing each other at once cannot leave none."""
        return self._request("POST", "rpc/m2_take_role", body={"p_email": email, "p_role": role, "p_settings_admins": settings_admins})

    def accounts(self) -> list[dict]:
        roles: dict[str, list[str]] = {}
        for r in self._request("GET", "m2_roles", {"select": "email,role", "order": "email"}):
            roles.setdefault(r["email"], []).append(r["role"])
        known = set(roles)
        known |= {r["email"] for r in self._request("GET", "m2_class_members", {"select": "email"})}
        known |= {r["teacher_email"] for r in self._request("GET", "m2_classes", {"select": "teacher_email", "teacher_email": "not.is.null"})}
        return [{"email": e, "roles": sorted(roles.get(e, []))} for e in sorted(known)]

    # --- skill learning ---

    def get_progress(self, user_id: str, skill_id: str) -> dict | None:
        rows = self._request("GET", "m2_skill_progress", {"user_id": self._eq(user_id), "skill_id": self._eq(skill_id),
                                                          "select": "*"})
        return rows[0] if rows else None

    def save_progress(self, user_id: str, skill_id: str, **fields) -> dict:
        unknown = set(fields) - set(PROGRESS_FIELDS)
        if unknown:
            raise ValueError(f"unknown progress fields {sorted(unknown)}")
        # merge-duplicates updates only the columns sent, so the other fields stay as they are
        rows = self._request("POST", "m2_skill_progress", {"on_conflict": "user_id,skill_id"},
                             {"user_id": user_id, "skill_id": skill_id, **fields}, returning=True, upsert=True)
        return rows[0]

    def progress_of(self, user_id: str) -> list[dict]:
        return self._request("GET", "m2_skill_progress", {"user_id": self._eq(user_id), "select": "*"})

    def add_answer(self, user_id: str, skill_id: str, question_key: str, correct: bool, counted: bool,
                   mistake_id: str | None, day: date) -> None:
        self._request("POST", "m2_answers", body={"user_id": user_id, "skill_id": skill_id, "question_key": question_key,
                                                   "correct": correct, "counted": counted, "mistake_id": mistake_id,
                                                   "day": day.isoformat()})

    def last_counted_answers(self, user_id: str, skill_id: str, n: int) -> list[dict]:
        rows = self._request("GET", "m2_answers", {"user_id": self._eq(user_id), "skill_id": self._eq(skill_id),
                             "counted": "eq.true", "select": "question_key,correct,day", "order": "id.desc",
                             "limit": str(n)})
        return [{**r, "day": date.fromisoformat(r["day"])} for r in reversed(rows)]

    def answer_counts(self, user_id: str, skill_id: str) -> dict[str, int]:
        rows = self._request("GET", "m2_answers", {"user_id": self._eq(user_id), "skill_id": self._eq(skill_id),
                                                   "select": "question_key"})
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["question_key"]] = counts.get(r["question_key"], 0) + 1
        return counts

    # --- real tests ---

    def create_test(self, class_id: int, test_day: date, lessons: list[str], created_by: str, *, note: str = "", questions: int = 12,
                    minutes: int = 45, created_at: datetime | None = None) -> dict:
        fields = {"lessons": list(lessons), "questions": questions, "minutes": minutes}
        _check_test(fields)
        body = {"class_id": class_id, "date": test_day.isoformat(), **fields, "note": note, "created_by": created_by}
        if created_at:
            body["created_at"] = created_at.isoformat()
        return _test_row(self._request("POST", "m2_tests", body=body, returning=True)[0])

    def get_test(self, test_id: int) -> dict | None:
        rows = self._request("GET", "m2_tests", {"id": self._eq(test_id), "select": "*"})
        return _test_row(rows[0]) if rows else None

    def update_test(self, test_id: int, **fields) -> dict:
        unknown = set(fields) - TEST_FIELDS
        if unknown:
            raise ValueError(f"unknown test fields {sorted(unknown)}")
        _check_test(fields)
        body = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in fields.items()}
        rows = self._request("PATCH", "m2_tests", {"id": self._eq(test_id), "removed_at": "is.null"}, body, returning=True)
        if not rows:
            raise KeyError(test_id)
        return _test_row(rows[0])

    def remove_test(self, test_id: int, at: datetime | None = None) -> bool:
        stamp = (at or datetime.now(timezone.utc)).isoformat()
        return bool(self._request("PATCH", "m2_tests", {"id": self._eq(test_id), "removed_at": "is.null"}, {"removed_at": stamp}, returning=True))

    def tests_of_classes(self, class_ids, include_removed: bool = False) -> list[dict]:
        ids = sorted(set(class_ids))
        if not ids:
            return []
        params = {"class_id": f"in.({','.join(str(i) for i in ids)})", "select": "*", "order": "date,id"}
        if not include_removed:
            params["removed_at"] = "is.null"
        return [_test_row(r) for r in self._request("GET", "m2_tests", params)]

    # --- timed attempts ---

    def create_attempt(self, user_id: str, kind: str, scope: str, started_at: datetime, due_at: datetime, questions: list[dict]) -> dict:
        rows = self._request("POST", "m2_attempts", body={"user_id": user_id, "kind": kind, "scope": scope, "started_at": started_at.isoformat(),
                                                           "due_at": due_at.isoformat(), "questions": questions}, returning=True)
        return _attempt_row(rows[0])

    def get_attempt(self, attempt_id: str) -> dict | None:
        try:
            rows = self._request("GET", "m2_attempts", {"id": self._eq(attempt_id), "select": "*"})
        except urllib.error.HTTPError as exc:
            if exc.code == 400:                                  # not a valid id
                return None
            raise
        return _attempt_row(rows[0]) if rows else None

    def save_attempt(self, attempt_id: str, **fields) -> dict:
        unknown = set(fields) - ATTEMPT_FIELDS
        if unknown:
            raise ValueError(f"unknown attempt fields {sorted(unknown)}")
        body = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in fields.items()}
        rows = self._request("PATCH", "m2_attempts", {"id": self._eq(attempt_id)}, body, returning=True)
        if not rows:
            raise KeyError(attempt_id)
        return _attempt_row(rows[0])

    def attempts_of(self, user_id: str, kind: str, scope: str | None = None) -> list[dict]:
        params = {"user_id": self._eq(user_id), "kind": self._eq(kind), "select": "*", "order": "started_at"}
        if scope is not None:
            params["scope"] = self._eq(scope)
        return [_attempt_row(r) for r in self._request("GET", "m2_attempts", params)]

    def comets_of(self, user_id: str) -> set[str]:
        rows = self._request("GET", "m2_comets", {"user_id": self._eq(user_id), "select": "comet_id"})
        return {r["comet_id"] for r in rows}

    def add_comet(self, user_id: str, comet_id: str) -> None:
        self._request("POST", "m2_comets", {"on_conflict": "user_id,comet_id"}, {"user_id": user_id, "comet_id": comet_id}, upsert=True)

    def reward_state(self, user_id: str) -> dict | None:
        rows = self._request("GET", "m2_reward_state", {"user_id": self._eq(user_id), "select": "*"})
        if not rows:
            return None
        return self.reward_state_row(rows[0])

    def save_reward_state(self, user_id: str, **fields) -> dict:
        body = {k: v.isoformat() if isinstance(v, date) else v for k, v in fields.items()}
        rows = self._request("POST", "m2_reward_state", {"on_conflict": "user_id"}, {"user_id": user_id, **body}, returning=True, upsert=True)
        return self.reward_state_row(rows[0])

    @staticmethod
    def reward_state_row(row: dict) -> dict:
        return {**row, **{k: date.fromisoformat(row[k]) if row.get(k) else None for k in ("last_comet_day", "last_catch_day")}}

    def last_answered(self, user_id: str) -> dict[str, date]:
        rows = self._request("GET", "m2_last_answered", {"user_id": self._eq(user_id), "select": "skill_id,day"})
        return {r["skill_id"]: date.fromisoformat(r["day"]) for r in rows}

    def daily_correct(self, user_id: str) -> dict[date, int]:
        rows = self._request("GET", "m2_daily_correct", {"user_id": self._eq(user_id), "select": "day,correct"})
        return {date.fromisoformat(r["day"]): r["correct"] for r in rows}

    def answers_of(self, user_id: str, skill_id: str) -> list[dict]:
        rows = self._request("GET", "m2_answers", {"user_id": self._eq(user_id), "skill_id": self._eq(skill_id),
                                                   "select": "question_key,correct,counted,day,mistake_id", "order": "id"})
        return [{**r, "day": date.fromisoformat(r["day"])} for r in rows]

    def recent_skills(self, user_id: str, n: int = 20) -> list[str]:
        rows = self._request("GET", "m2_answers", {"user_id": self._eq(user_id), "select": "skill_id", "order": "id.desc",
                                                   "limit": str(max(200, n * 20))})
        found: list[str] = []
        for r in rows:
            if r["skill_id"] not in found:
                found.append(r["skill_id"])
                if len(found) == n:
                    break
        return found

    def solved_keys(self, user_id: str, skill_id: str) -> set[str]:
        rows = self._request("GET", "m2_answers", {"user_id": self._eq(user_id), "skill_id": self._eq(skill_id),
                                                   "correct": "eq.true", "select": "question_key"})
        return {r["question_key"] for r in rows}
