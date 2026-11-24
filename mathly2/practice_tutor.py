"""The AI tutor on a practice question (💬 on the exercise screen; not in quizzes, the simulation or the real-test rounds).

The student asks about the question on screen or the one just answered. Before answering, the tutor guides without saying which choice
is right, and the answer will not count for mastery (as when help is opened). After answering, it may explain the right answer and the
mistake. Which of the two is decided here: the question still on screen (progress.current_key) has not been answered; one of the round's
answered questions has. The conversation lives in the browser and comes with each message (the last HISTORY ones); only a count of the
day's messages is kept, in memory (it starts again when the server restarts). Nothing personal goes to the AI: the question, its
choices, the right answer, the student's mistake and the conversation."""
from __future__ import annotations

import logging
import threading
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import clock
from .access import learner
from .mathtext import tidy
from .photoq import reviewer
from .writtentest import right_text

log = logging.getLogger("mathly2.practice_tutor")
router = APIRouter(prefix="/api")

MESSAGES_A_DAY = 30
HISTORY = 12
LETTERS = "אבגדהוזח"
_counts: dict[tuple[str, str], int] = {}
_lock = threading.Lock()


class Said(BaseModel):
    role: Literal["student", "ai"]
    text: str = Field(..., max_length=1500)


class Ask(BaseModel):
    question_key: str = Field(..., max_length=200)
    message: str = Field(..., max_length=500)
    history: list[Said] = Field(default_factory=list, max_length=40)


def used_today(user_id: str) -> int:
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


@router.post("/skills/{skill_id}/tutor")
def ask_tutor(skill_id: str, body: Ask, request: Request, user: dict = Depends(learner)) -> dict:
    """One message to the tutor about a practice question: {reply, helped (this answer will not count), left (messages left today)}."""
    from .skills import _skill
    bank, store = request.app.state.bank, request.app.state.store
    skill = _skill(request, skill_id, user)
    tutor = reviewer(request)
    if tutor is None or not hasattr(tutor, "tutor_reply"):
        raise HTTPException(503, "ה־AI לא זמין כרגע")
    message = body.message.strip()
    if not message:
        raise HTTPException(422, "כתבו שאלה")
    if bank.practice_question(skill_id, body.question_key) is None:
        raise HTTPException(404, "השאלה לא נמצאה")
    progress = store.get_progress(user["id"], skill_id)
    on_screen = bool(progress) and progress.get("current_key") == body.question_key
    answered = None
    if not on_screen:
        answered = next((r for r in reversed(store.answers_of(user["id"], skill_id)) if r["question_key"] == body.question_key), None)
        if answered is None:
            raise HTTPException(409, "השאלה הזו כבר לא על המסך")
    if used_today(user["id"]) >= MESSAGES_A_DAY:
        raise HTTPException(429, f"אפשר לשאול את ה־AI עד {MESSAGES_A_DAY} שאלות ביום. נמשיך מחר!")
    history = [{"role": m.role, "text": m.text} for m in body.history[-HISTORY:]]
    try:
        reply = tutor.tutor_reply(context_of(bank, skill, body.question_key, answered), history, message, None)
    except Exception as exc:
        log.warning("the practice tutor failed: %s", getattr(exc, "reason", type(exc).__name__))
        raise HTTPException(503, "ה־AI לא ענה כרגע, נסו שוב בעוד רגע")
    helped = on_screen
    if on_screen and not progress.get("current_helped"):
        store.save_progress(user["id"], skill_id, current_helped=True)           # as with help: this answer will not count for mastery
    left = MESSAGES_A_DAY - _count(user["id"])
    return {"reply": tidy(str(reply))[:1500], "helped": helped, "left": max(0, left)}
