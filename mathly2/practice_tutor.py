"""The AI tutor on a practice question (💬 on the exercise screen; not in quizzes, the simulation or the real-test rounds).

The student asks about the question on screen or the one just answered. Before answering, the tutor guides without saying which choice
is right, and the answer will not count for mastery (as when help is opened). After answering, it may explain the right answer and the
mistake. Which of the two is decided here: the question still on screen (progress.current_key) has not been answered; one of the round's
answered questions has. The conversation comes from the browser with each message (the last HISTORY ones), and is kept in m2_tutor_chats
(a row a student, question and day) for the class's teacher, who reads it in the AI tab (GET /api/teaching/tutor-chats); the daily limit is
counted there. Before that migration is run, the tutor still works: the count is kept in memory and nothing is saved. Nothing personal
goes to the AI: the question, its choices, the right answer, the student's mistake and the conversation."""
from __future__ import annotations

import logging
import threading
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import clock
from .access import learner, need
from .mathtext import tidy
from .photoq import reviewer
from .writtentest import right_text

log = logging.getLogger("mathly2.practice_tutor")
router = APIRouter(prefix="/api")

MESSAGES_A_DAY = 30
HISTORY = 12
LETTERS = "אבגדהוזח"
_counts: dict[tuple[str, str], int] = {}
_helped: set[tuple[str, str, str, str]] = set()                          # (user, skill, question, day): asked before answering
_lock = threading.Lock()


class Said(BaseModel):
    role: Literal["student", "ai"]
    text: str = Field(..., max_length=1500)


class Ask(BaseModel):
    question_key: str = Field(..., max_length=200)
    message: str = Field(..., max_length=500)
    history: list[Said] = Field(default_factory=list, max_length=40)


def used_today(store, user_id: str) -> int:
    try:
        return store.tutor_messages_on(user_id, clock.school_day())
    except Exception:                                                     # the table is not there yet: the count in memory
        with _lock:
            return _counts.get((user_id, clock.school_day().isoformat()), 0)


def _count(user_id: str) -> int:
    day = clock.school_day().isoformat()
    with _lock:
        for key in [k for k in _counts if k[1] != day]:                    # yesterday's counts go
            del _counts[key]
        _counts[(user_id, day)] = _counts.get((user_id, day), 0) + 1
        return _counts[(user_id, day)]


def context_of(bank, skill: dict, key: str, answered: dict | None) -> dict:
    """What the tutor knows: the question with its choices, the right answer (for it only), the skill's explanation, and after an answer
    whether it was right and the mistake's name."""
    served = bank.practice_question(skill["id"], key)
    choices = "\n".join(f"  {LETTERS[i] if i < len(LETTERS) else i + 1}) {c['text']}" for i, c in enumerate(served["choices"]))
    context = {"question": f"{served['question']}\nהתשובות לבחירה (שאלה אמריקאית):\n{choices}\nהנושא: {skill['name']}. {skill.get('description', '')}",
               "answer": right_text(bank, {"skill_id": skill["id"], "key": key}) or "", "steps": [], "shown": 0, "full": answered is not None,
               "note": ("זו שאלת תרגול אמריקאית. התלמיד עוד לא ענה: אל תגלו איזו תשובה נכונה ואל תפסלו תשובות; עזרו לו לחשוב. "
                        "אין כאן כפתורי צעד או פתרון: עודדו אותו לנסות לענות." if answered is None else
                        "זו שאלת תרגול אמריקאית, והתלמיד כבר ענה: מותר להסביר את התשובה הנכונה ולמה הטעות שלו טעות.")}
    if answered is not None:
        mistake = bank.mistake(answered.get("mistake_id")) if answered.get("mistake_id") else None
        context["review"] = {"verdict": "correct" if answered["correct"] else "wrong",
                             "feedback": f"הטעות: {mistake['name']}. {mistake.get('tip') or ''}" if mistake else ("ענה נכון" if answered["correct"] else "ענה לא נכון")}
    return context


def _converse(request: Request, user: dict, skill: dict, key: str, on_screen: bool, answered: dict | None, body: Ask) -> dict:
    """One exchange with the tutor about a practice question (on screen: guide; answered: explain), kept for the teacher."""
    bank, store = request.app.state.bank, request.app.state.store
    tutor = reviewer(request)
    if tutor is None or not hasattr(tutor, "tutor_reply"):
        raise HTTPException(503, "ה־AI לא זמין כרגע")
    message = body.message.strip()
    if not message:
        raise HTTPException(422, "כתבו שאלה")
    used = used_today(store, user["id"])
    if used >= MESSAGES_A_DAY:
        raise HTTPException(429, f"אפשר לשאול את ה־AI עד {MESSAGES_A_DAY} שאלות ביום. נמשיך מחר!")
    history = [{"role": m.role, "text": m.text} for m in body.history[-HISTORY:]]
    try:
        reply = tutor.tutor_reply(context_of(bank, skill, key, answered), history, message, None)
    except Exception as exc:
        log.warning("the practice tutor failed: %s", getattr(exc, "reason", type(exc).__name__))
        raise HTTPException(503, "ה־AI לא ענה כרגע, נסו שוב בעוד רגע")
    reply, day, now = tidy(str(reply))[:1500], clock.school_day(), clock.now()
    _count(user["id"])
    if on_screen:
        with _lock:
            _helped.add((user["id"], skill["id"], key, day.isoformat()))
    try:
        store.add_tutor_messages(user["id"], skill["id"], key, day,
                                 [{"role": "student", "text": message, "at": now.isoformat()}, {"role": "ai", "text": reply, "at": now.isoformat()}], on_screen, now)
    except Exception as exc:                                                  # never lose the reply for the bookkeeping
        log.warning("could not keep the tutor conversation: %s", type(exc).__name__)
    return {"reply": reply, "helped": on_screen, "left": max(0, MESSAGES_A_DAY - used - 1)}


def was_helped(store, user_id: str, skill_id: str, key: str) -> bool:
    """Did the student ask the tutor about this question today before answering it? (then a round's answer does not count for mastery)"""
    day = clock.school_day()
    with _lock:
        if (user_id, skill_id, key, day.isoformat()) in _helped:
            return True
    try:
        row = store.tutor_chat(user_id, skill_id, key, day)
    except Exception:
        return False
    return bool(row and row["helped"])


@router.post("/skills/{skill_id}/tutor")
def ask_tutor(skill_id: str, body: Ask, request: Request, user: dict = Depends(learner)) -> dict:
    """One message to the tutor about a question of the skill's sheet: {reply, helped (this answer will not count), left (messages left today)}."""
    from .skills import _skill
    bank, store = request.app.state.bank, request.app.state.store
    skill = _skill(request, skill_id, user)
    if bank.practice_question(skill_id, body.question_key) is None:
        raise HTTPException(404, "השאלה לא נמצאה")
    progress = store.get_progress(user["id"], skill_id)
    on_screen = bool(progress) and progress.get("current_key") == body.question_key
    answered = None
    if not on_screen:
        answered = next((r for r in reversed(store.answers_of(user["id"], skill_id)) if r["question_key"] == body.question_key), None)
        if answered is None:
            raise HTTPException(409, "השאלה הזו כבר לא על המסך")
    got = _converse(request, user, skill, body.question_key, on_screen, answered, body)
    if on_screen and not progress.get("current_helped"):
        store.save_progress(user["id"], skill_id, current_helped=True)           # as with help: this answer will not count for mastery
    return got


@router.post("/rounds/{round_id}/tutor")
def ask_tutor_in_round(round_id: str, body: Ask, request: Request, user: dict = Depends(learner)) -> dict:
    """The same about a question of a lesson round, a mistakes round or a round on the go: the round's next question (guide; its answer
    will not count for mastery) or one it has answered (explain)."""
    from . import attempts
    from .rounds import _graded, _mine
    bank = request.app.state.bank
    row = _mine(request, user, round_id)
    item = next((q for q in row["questions"] if q["key"] == body.question_key), None)
    if item is None or bank.practice_question(item["skill_id"], item["key"]) is None:
        raise HTTPException(404, "השאלה לא נמצאה")
    done = _graded(bank, row)
    nxt = row["questions"][len(done)] if attempts.is_open(row) and len(done) < len(row["questions"]) else None
    on_screen = nxt is not None and nxt["key"] == body.question_key
    answered = None
    if not on_screen:
        found = next(((right, mistake) for q, right, mistake in done if q["key"] == body.question_key), None)
        if found is None:
            raise HTTPException(409, "השאלה הזו כבר לא על המסך")
        answered = {"correct": found[0], "mistake_id": found[1]["id"] if found[1] else None}
    return _converse(request, user, bank.skill(item["skill_id"]), body.question_key, on_screen, answered, body)


# ---- the teacher reads the conversations ----

@router.get("/teaching/tutor-chats")
def teaching_chats(request: Request, user: dict = Depends(need("class.teach")), days: int = 7) -> dict:
    """The conversations of the taught classes' students with the tutor in the last `days` days, the newest first: the student, the skill,
    the question, whether it was asked before answering, and the messages."""
    from datetime import timedelta
    from .photoq import _taught_ids
    store, bank = request.app.state.store, request.app.state.bank
    days = max(1, min(days, 60))
    emails = {m["user_id"]: m["email"] for i in _taught_ids(request, user) for m in store.members(i) if m.get("user_id")}
    try:
        rows = store.tutor_chats_of(list(emails), clock.school_day() - timedelta(days=days - 1))
    except Exception:
        raise HTTPException(503, "השיחות עוד לא נשמרות: צריך להריץ את המיגרציה 20261127090000_m2_tutor_chats.sql")
    out = []
    for r in rows:
        skill = bank.skill(r["skill_id"]) or {}
        served = bank.practice_question(r["skill_id"], r["question_key"]) or {}
        out.append({"id": r["id"], "student": emails.get(r["user_id"], ""), "skill": skill.get("name", r["skill_id"]), "skill_id": r["skill_id"],
                    "question": served.get("question", ""), "day": r["day"].isoformat(), "helped": r["helped"],
                    "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                    "messages": [{"role": m.get("role"), "text": tidy(m.get("text"))} for m in r["messages"]]})
    return {"days": days, "chats": out}
