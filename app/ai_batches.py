"""AI checks of student work for a whole class: a daily budget per class, and batches the teacher sends in one action.

Each class has a daily number of AI checks of its students' work (`classes.ai_daily_checks`, default 150; set by a
manager), counted in `math_class_ai_budget` by Jerusalem date and taken atomically in the database, so two batches at
once never pass it. Checks of student work (quiz answers in the AI queue, worksheet submissions) take from it; the
teacher's personal 3 requests a day (app/teacher_ai.py) stay for the teacher's own use. A check that fails, or whose
photo the AI could not read, is given back.

A batch is every pending check of one scope, oldest first: one final-quiz window ("window:<id>"), one unit's practice
sittings ("unit:<id>"), single answers ("answers"), or one worksheet's submissions ("worksheet:<id>"). When the budget
is short the batch sends what is left and the rest stays pending for the next day. With `auto_send_practice` on for a
class, a handed-in practice sitting's answers are sent at once, within the budget; final quizzes and worksheets always
wait for the teacher.

Without the migration, a single check falls back to the teacher's own allowance, and batches answer
"budget_unavailable".
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from .access import has_permission
from .answer_scans import ScanError
from .auth import AuthUnavailable

log = logging.getLogger("mathly.ai_batches")
MIGRATION = "supabase/migrations/20261106120000_math_ai_batches.sql"
DEFAULT_DAILY = 150
LIMIT_CODE = "class_budget_limit"
WORKERS = 2   # checks sent at once in a batch: the provider's rate limits
JERUSALEM = ZoneInfo("Asia/Jerusalem")
OPEN = ("pending", "failed")


class BudgetUnavailable(RuntimeError):
    pass


def today() -> date:
    return datetime.now(JERUSALEM).date()


def class_limit(row: dict) -> int:
    value = (row or {}).get("ai_daily_checks")
    return value if type(value) is int and value >= 0 else DEFAULT_DAILY


def class_of_student(classes: list[dict], email: str) -> dict | None:
    """The class whose budget a student's check takes from: the first class that has them as a student."""
    email = str(email or "").lower()
    return next((r for r in classes if email in (r.get("emails") or ()) and email not in (r.get("teachers") or ())), None)


class ClassBudget:
    """The budget table and its two functions, through the service key."""

    def __init__(self, auth):
        self.auth = auth
        self._warned = False

    @property
    def configured(self) -> bool:
        return bool(self.auth is not None and getattr(self.auth, "secret", None))

    def _call(self, path: str, method: str = "GET", body=None):
        if not self.configured:
            raise BudgetUnavailable("budget_unavailable")
        try:
            return self.auth._admin(path, method, body)
        except AuthUnavailable as exc:
            if ("answered 404" in str(exc) or "PGRST202" in str(exc)) and not self._warned:
                log.warning("the class AI budget is missing; apply %s", MIGRATION)
                self._warned = True
            raise BudgetUnavailable("budget_unavailable") from exc

    def take(self, class_id: int, n: int, limit: int, day: date | None = None) -> int:
        """Up to n checks for the day, never past the limit; the number granted."""
        got = self._call("/rest/v1/rpc/math_take_class_checks", "POST",
                         {"p_class": int(class_id), "p_day": (day or today()).isoformat(), "p_n": int(n), "p_limit": int(limit)})
        if type(got) is not int:   # not the function's answer: there is no budget to count on
            raise BudgetUnavailable("budget_unavailable")
        return got

    def give(self, class_id: int, n: int = 1, day: date | None = None) -> None:
        try:
            self._call("/rest/v1/rpc/math_give_class_checks", "POST",
                       {"p_class": int(class_id), "p_day": (day or today()).isoformat(), "p_n": int(n)})
        except BudgetUnavailable:
            log.warning("a check was not given back to class %s", class_id)

    def usage(self, class_ids, since: date) -> list[dict]:
        ids = sorted({int(c) for c in class_ids})
        if not ids:
            return []
        return self._call(f"/rest/v1/math_class_ai_budget?select=class_id,day,used&class_id=in.({','.join(map(str, ids))})"
                          f"&day=gte.{since.isoformat()}") or []

    def add_batch(self, row: dict) -> dict | None:
        try:
            rows = self._call("/rest/v1/math_ai_batches?select=id", "POST", row)
            return rows[0] if rows else None
        except BudgetUnavailable:
            return None


def install_ai_batch_routes(app, signed_in):
    if not hasattr(app.state, "class_budget"):
        app.state.class_budget = ClassBudget(app.state.auth)
    lock = threading.Lock()

    def budget() -> ClassBudget:
        return app.state.class_budget

    def reply(value, status=200):
        return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})

    def classes() -> list[dict]:
        try:
            return app.state.auth.classes() if app.state.auth is not None else []
        except AuthUnavailable as exc:
            raise ScanError(503, "queue_unavailable") from exc

    def account(user=Depends(signed_in)) -> dict:
        if not user or not user.get("id"):
            raise ScanError(401, "sign_in_required")
        return user

    def taught(user) -> list[dict]:
        """The classes this account reviews checks for: the ones it teaches, or every class for a manager."""
        if has_permission(user, "management.access"):
            return classes()
        email = str(user.get("email", "")).lower()
        return [r for r in classes() if email in (r.get("teachers") or ())]

    def class_row(user, class_id) -> dict:
        row = next((r for r in taught(user) if r.get("id") == class_id), None)
        if row is None:
            raise ScanError(403, "teacher_required")
        return row

    # ---- one check of student work: the class's budget (the AI queue's send, a worksheet's check)
    def take_one(email: str):
        """Takes one check from the student's class. Returns the class row to give back to, or None when there is no
        class budget (then the caller uses the teacher's own allowance). ScanError 429 when the budget is used up."""
        row = class_of_student(classes(), email)
        if row is None:
            return None
        try:
            got = budget().take(row["id"], 1, class_limit(row))
        except BudgetUnavailable:
            return None
        if not got:
            raise ScanError(429, LIMIT_CODE)
        return row

    def give_one(row) -> None:
        if row is not None:
            budget().give(row["id"], 1)

    app.state.class_take_one, app.state.class_give_one = take_one, give_one

    # ---- what can be sent in one action
    def pending(row: dict) -> dict[str, list[dict]]:
        """The class's open checks of answers, by scope, oldest first."""
        emails = set(row.get("emails") or ()) - set(row.get("teachers") or ())
        open_rows = [r for r in app.state.ai_queue.listing(emails, limit=1000)
                     if r.get("kind") == "grading" and r.get("state") in OPEN]
        users = sorted({r["user_id"] for r in open_rows})
        by_attempt = {}
        if users:
            try:
                for s in app.state.answers.quiz(None, "report", users=users):
                    for a in s.get("attempts") or []:
                        by_attempt[a.get("attempt_id")] = s
            except ScanError:
                pass
        out: dict[str, list[dict]] = {}
        for r in sorted(open_rows, key=lambda r: str(r.get("created_at") or "")):
            s = by_attempt.get(r.get("attempt_id"))
            key = "answers" if s is None else (f"window:{s['window_id']}" if s.get("mode") == "final" and s.get("window_id")
                                               else f"unit:{s['unit_id']}")
            out.setdefault(key, []).append(r)
        return out

    def pending_sheets(row: dict) -> dict[str, list[dict]]:
        """The class's worksheet submissions waiting for a check that have no AI suggestion yet, by worksheet."""
        store = getattr(app.state, "worksheets", None)
        if store is None:
            return {}
        from .worksheets import WorksheetsUnavailable, current
        try:
            sheets = store.of_class(row["id"])
            subs = current(store.submissions([w["id"] for w in sheets]))
        except WorksheetsUnavailable:
            return {}
        out: dict[str, list[dict]] = {}
        for sub in sorted(subs, key=lambda s: str(s.get("submitted_at") or "")):
            state = sub.get("state") or ("checked" if sub.get("checked_at") else "submitted")
            if state == "submitted" and not sub.get("ai_checked_at"):
                out.setdefault(f"worksheet:{sub['worksheet_id']}", []).append(sub)
        return out

    def scope_label(key: str) -> str:
        from .math_skills import algebra9
        kind, _, rest = key.partition(":")
        unit = lambda uid: next((u["name"] for u in algebra9()["units"] if u["id"] == uid), uid)
        if kind == "window":
            try:
                w = app.state.quiz_modes.window(rest)
            except Exception:
                w = None
            return f"בוחן מסכם: {unit(w['unit_id'])}" if w else "בוחן מסכם"
        if kind == "unit":
            return f"בחני חיזוק: {unit(rest)}"
        if kind == "worksheet":
            store = getattr(app.state, "worksheets", None)
            try:
                w = store.get(rest) if store else None
            except Exception:
                w = None
            return f"שיעורי בית: {w['title']}" if w else "שיעורי בית"
        return "תשובות בודדות"

    @app.get("/api/ai-queue/budget")
    def budget_view(user=Depends(account)):
        """Per class the teacher reviews: today's checks used and left, the last 7 days, the class's settings, and
        what can be sent in one action."""
        rows = taught(user)
        if not rows:
            raise ScanError(403, "teacher_required")
        try:
            usage = budget().usage([r["id"] for r in rows], today() - timedelta(days=6))
            known = True
        except BudgetUnavailable:
            usage, known = [], False
        out = []
        for r in rows:
            mine = [u for u in usage if u["class_id"] == r["id"]]
            used = next((u["used"] for u in mine if str(u["day"]) == today().isoformat()), 0)
            scopes = {**{k: len(v) for k, v in pending(r).items()}, **{k: len(v) for k, v in pending_sheets(r).items()}}
            out.append({"class_id": r["id"], "name": r.get("name", ""), "limit": class_limit(r), "used_today": used,
                        "left_today": max(class_limit(r) - used, 0), "used_7d": sum(u["used"] for u in mine),
                        "auto_send_practice": bool(r.get("auto_send_practice")),
                        "scopes": [{"key": k, "label": scope_label(k), "pending": n} for k, n in sorted(scopes.items())]})
        return reply({"classes": out, "available": known, "manager": has_permission(user, "management.access")})

    # ---- sending
    def send_answers(rows: list[dict], class_id: int, reviewer: str, batch_id: str | None) -> None:
        """Sends these queued answers to the AI, a few at a time; a check that fails or cannot read the photo is
        given back to the class."""
        def one(r):
            try:
                claimed = app.state.ai_queue.claim(r["id"], reviewer)
            except ScanError:
                budget().give(class_id, 1)   # taken by someone else meanwhile
                return
            try:
                done = app.state.queue_send_answer(claimed)
            except Exception as exc:   # never leave a request "sending" because of one answer
                log.error("batch check failed: %s", type(exc).__name__)
                done = {}
            if done.get("state") != "done" or (done.get("result") or {}).get("verdict") == "unreadable":
                budget().give(class_id, 1)
        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(one, rows))
        log.info("batch %s: %d checks sent", batch_id or "-", len(rows))

    def send_sheets(subs: list[dict], class_id: int) -> None:
        def one(sub):
            try:
                result = app.state.worksheet_ai_suggest(sub)
            except Exception as exc:
                log.warning("batch worksheet check failed: %s", type(exc).__name__)
                result = None
            if not result or not result.get("readable"):
                budget().give(class_id, 1)
        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(one, subs))

    @app.post("/api/ai-queue/batches")
    def batch(body: dict, background: BackgroundTasks, user=Depends(account)):
        """One scope's pending checks: without `confirm`, how many there are and how many the class has left today;
        with it, sends as many as the budget allows, oldest first. The rest stay pending."""
        row = class_row(user, body.get("class_id"))
        key = str(body.get("scope") or "")
        if key.startswith("worksheet:"):
            items = pending_sheets(row).get(key, [])
        else:
            items = pending(row).get(key, [])
        try:
            used = next((u["used"] for u in budget().usage([row["id"]], today()) if str(u["day"]) == today().isoformat()), 0)
        except BudgetUnavailable as exc:
            raise ScanError(503, "budget_unavailable") from exc
        left = max(class_limit(row) - used, 0)
        if body.get("confirm") is not True:
            return reply({"scope": key, "label": scope_label(key), "total": len(items), "left": left})
        with lock:   # the database keeps the count right; this keeps one teacher's double click from two batches
            got = budget().take(row["id"], len(items), class_limit(row)) if items else 0
        chosen = items[:got]
        reviewer = str(user.get("email", "")).lower()
        saved = budget().add_batch({"class_id": row["id"], "scope": key[:80], "created_by_email": reviewer,
                                    "total": len(items), "sent": len(chosen)}) if items else None
        if chosen and key.startswith("worksheet:"):
            background.add_task(send_sheets, chosen, row["id"])
        elif chosen:
            background.add_task(send_answers, chosen, row["id"], reviewer, (saved or {}).get("id"))
        actions = getattr(app.state, "actions", None)
        if actions is not None and chosen:
            actions.record(user, "ai_batch", f"{row.get('name', '')}: {scope_label(key)} · {len(chosen)}")
        return reply({"scope": key, "total": len(items), "sent": len(chosen), "later": len(items) - len(chosen),
                      "left": max(left - len(chosen), 0)})

    def auto_send(email: str, attempt_ids: list[str], background: BackgroundTasks | None = None) -> int:
        """A practice sitting just handed in: its queued answers go to the AI now when the class turned this on."""
        row = class_of_student(classes(), email)
        if row is None or not row.get("auto_send_practice"):
            return 0
        wanted = set(attempt_ids)
        rows = [r for r in app.state.ai_queue.listing({str(email).lower()}, limit=200)
                if r.get("kind") == "grading" and r.get("state") in OPEN and r.get("attempt_id") in wanted]
        try:
            got = budget().take(row["id"], len(rows), class_limit(row)) if rows else 0
        except BudgetUnavailable:
            return 0
        chosen = rows[:got]
        if chosen:
            if background is not None:
                background.add_task(send_answers, chosen, row["id"], "auto", None)
            else:
                send_answers(chosen, row["id"], "auto", None)
        return len(chosen)

    app.state.ai_auto_send = auto_send

    @app.put("/api/classes/{class_id}/ai-settings")
    def settings(class_id: int, body: dict, user=Depends(account)):
        """The class teacher turns automatic practice checks on or off; a manager sets the class's daily budget."""
        row = class_row(user, class_id)
        fields = {}
        if "auto_send_practice" in body:
            if type(body["auto_send_practice"]) is not bool:
                raise ScanError(400, "invalid_setting")
            fields["auto_send_practice"] = body["auto_send_practice"]
        if "ai_daily_checks" in body:
            if not has_permission(user, "management.access"):
                raise ScanError(403, "manager_required")
            value = body["ai_daily_checks"]
            if value is not None and (type(value) is not int or not 0 <= value <= 5000):
                raise ScanError(400, "invalid_setting")
            fields["ai_daily_checks"] = value
        if not fields:
            raise ScanError(400, "invalid_setting")
        try:
            app.state.auth.save_class_settings(class_id, fields)
        except AuthUnavailable as exc:
            raise ScanError(503, "settings_unavailable") from exc
        return reply({"class_id": class_id, **{k: row.get(k) for k in ("auto_send_practice", "ai_daily_checks")}, **fields})
