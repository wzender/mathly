"""An AI review of the way (הדרך) in a practice test (מבחן תרגול) or the simulation, sent back to the student after handing in.

After a test is handed in, the boards of its questions go to Gemini in ONE request (the free tier allows few requests a minute), with each
question, its choices, the right choice (for the model only) and the student's choice. The model judges the way per question (correct, partial,
wrong, unclear) and writes a short feedback line and a tip in Hebrew, without ever saying the right answer: results never show it. The review is
stored on the attempt (`review`): {"state": "pending" | "done" | "failed", ...} and shown on the result; the teacher sees it as a suggestion.

Nothing here knows a student: a request carries pictures and questions, never a name or an email. Without GEMINI_API_KEY there is no review.
The review runs in a background thread; a review left pending by a restart is started again when the result is next read."""
from __future__ import annotations

import base64
import io
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from . import clock

log = logging.getLogger("mathly2.boardreview")

REVIEWED = ("exercise_test", "simulation")
DEFAULT_MODEL = "gemini-2.5-flash"                 # a model with a free tier; GEMINI_MODEL overrides it
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
STALE = timedelta(minutes=10)                     # a pending review older than this was lost (a restart) and is started again
RETRIES = 3                                       # tries after "too many requests", waiting as the API asks (or 20, 40 s)
SIDE = 1280                                       # a board is shrunk to this longest side before it is sent
VERDICTS = ("correct", "partial", "wrong", "unclear")

INSTRUCTIONS = """אתם מורים למתמטיקה בכיתה ט בישראל. תלמיד פתר מבחן אמריקאי, ולכל שאלה כתב את הדרך על לוח. קיבלתם את השאלות, התשובות האפשריות, \
התשובה הנכונה (רק בשבילכם), התשובה שהתלמיד בחר, ותמונה של הלוח שלו לכל שאלה.
לכל שאלה עם לוח, הַעריכו את הדרך (לא רק את התשובה הסופית):
- verdict: "correct" אם הדרך נכונה ומובילה לתשובה; "partial" אם יש התחלה נכונה או רעיון נכון אבל טעות או חוסר; "wrong" אם השיטה שגויה; "unclear" אם אי אפשר לקרוא או שאין בלוח דרך של ממש.
- feedback: משפט או שניים לתלמיד, בעברית, בפנייה ברבים (אתם), חם וענייני: מה טוב בדרך, ואם יש טעות, איפה היא הטעות הראשונה ומה סוגה.
- tip: טיפ אחד קצר ומעשי לפעם הבאה.
אסור לכתוב את התשובה הסופית הנכונה, את המספר שלה או איזו אפשרות נכונה. אם התלמיד טעה, כוונו אותו לשלב, אל תפתרו בשבילו.
summary: משפט או שניים על הדרך במבחן כולו: חוזקה אחת ודבר אחד לשפר.
נוסחאות כתבו בתוך $...$."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "questions": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "n": {"type": "INTEGER"}, "verdict": {"type": "STRING", "enum": list(VERDICTS)},
            "feedback": {"type": "STRING"}, "tip": {"type": "STRING"}}, "required": ["n", "verdict", "feedback", "tip"]}},
    },
    "required": ["summary", "questions"],
}


class ReviewFailure(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


def _small(jpeg: bytes) -> bytes:
    from PIL import Image
    image = Image.open(io.BytesIO(jpeg)).convert("RGB")
    image.thumbnail((SIDE, SIDE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85)
    return out.getvalue()


def _letter(i: int) -> str:
    return "אבגדהוזחטי"[i] if i < 10 else str(i + 1)


class GeminiReviewer:
    """Gemini over its REST API (no SDK). `review(items)` -> {"summary", "questions": [{n, verdict, feedback, tip}]}."""

    def __init__(self, key: str, model: str = "", sleep=time.sleep) -> None:
        self.key, self.model, self.sleep = key, model or DEFAULT_MODEL, sleep
        self._lock = threading.Lock()                   # one request at a time: the free tier counts requests a minute

    def _parts(self, items: list[dict]) -> list[dict]:
        parts = [{"text": INSTRUCTIONS}]
        for it in items:
            choices = "\n".join(f"  {_letter(i)}. {c}" for i, c in enumerate(it["choices"]))
            picked = _letter(it["picked"]) if it["picked"] is not None else "לא ענה"
            parts.append({"text": f"\n\nשאלה {it['n']}:\n{it['question']}\nאפשרויות:\n{choices}\nהתשובה הנכונה (לא לגלות): {_letter(it['correct'])}\n"
                                  f"התלמיד בחר: {picked}\nהלוח של התלמיד לשאלה {it['n']}:"})
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(_small(it["image"])).decode()}})
        return parts

    def _call(self, body: bytes) -> dict:
        request = urllib.request.Request(ENDPOINT.format(model=self.model), data=body, method="POST",
                                         headers={"Content-Type": "application/json", "x-goog-api-key": self.key})
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read())

    def review(self, items: list[dict]) -> dict:
        body = json.dumps({"contents": [{"role": "user", "parts": self._parts(items)}],
                           "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "responseSchema": SCHEMA}}).encode()
        with self._lock:
            for attempt in range(RETRIES + 1):
                try:
                    data = self._call(body)
                    break
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", "replace")[:500]
                    if exc.code == 429 and attempt < RETRIES:
                        self.sleep(_retry_after(detail, 20 * (attempt + 1)))
                        continue
                    raise ReviewFailure({400: "bad_request", 401: "api_key_invalid", 403: "permission", 404: "model_not_found",
                                         429: "rate_limited"}.get(exc.code, "provider_error"), f"HTTP {exc.code}: {detail}") from None
                except (urllib.error.URLError, TimeoutError) as exc:
                    raise ReviewFailure("no_connection", str(exc)[:300]) from None
        try:
            candidate = data["candidates"][0]
            if candidate.get("finishReason") not in (None, "STOP"):
                raise ReviewFailure("incomplete", str(candidate.get("finishReason")))
            text = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
            out = json.loads(text)
        except ReviewFailure:
            raise
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ReviewFailure("bad_output", f"{type(exc).__name__}: {str(data)[:300]}") from None
        return out


def _retry_after(detail: str, default: float) -> float:
    """The wait the API asks for in a 429 ("retryDelay": "17s"), else `default` seconds."""
    try:
        for d in json.loads(detail).get("error", {}).get("details", []):
            if str(d.get("retryDelay", "")).endswith("s"):
                return min(90.0, float(d["retryDelay"][:-1]) + 1)
    except (ValueError, AttributeError, TypeError):
        pass
    return default


def make_reviewer(settings):
    return GeminiReviewer(settings.gemini_key, settings.gemini_model) if settings.gemini_key else None


# ---- running a review for an attempt ----

_running: set[str] = set()
_running_lock = threading.Lock()


def _items(app, row: dict) -> tuple[list[dict], dict]:
    """The questions that have a board, as the reviewer takes them, and n -> question key."""
    bank, store = app.state.bank, app.state.store
    work = store.work_of(row["user_id"], row["id"])
    items, keys = [], {}
    for n, q in enumerate(row["questions"], start=1):
        pid = work.get(q["key"])
        served = bank.practice_question(q["skill_id"], q["key"])
        picture = store.get_picture(pid) if pid else None
        if not served or not picture or picture["deleted_at"]:
            continue
        correct = next((c["index"] for c in served["choices"] if (bank.grade(q["skill_id"], q["key"], c["index"]) or {}).get("correct")), 0)
        picked = row["answers"].get(q["key"])
        items.append({"n": n, "question": served["question"], "choices": [c["text"] for c in served["choices"]], "correct": correct,
                      "picked": picked if isinstance(picked, int) else None, "image": app.state.pictures.get(picture["path"])})
        keys[n] = q["key"]
    return items, keys


def run(app, attempt_id: str) -> None:
    """Review one handed-in attempt and store the result on it. Never raises: a failure is stored as {"state": "failed"}."""
    store = app.state.store
    try:
        row = store.get_attempt(attempt_id)
        items, keys = _items(app, row)
        if not items:
            result = {"state": "done", "summary": None, "questions": {}}
        else:
            got = app.state.reviewer.review(items)
            questions = {}
            for q in got.get("questions", []):
                key = keys.get(q.get("n"))
                if key and q.get("verdict") in VERDICTS:
                    questions[key] = {"verdict": q["verdict"], "feedback": str(q.get("feedback", ""))[:600], "tip": str(q.get("tip", ""))[:300]}
            result = {"state": "done", "summary": str(got.get("summary") or "")[:800] or None, "questions": questions}
        result["at"] = clock.now().isoformat()
    except ReviewFailure as exc:
        log.warning("board review failed: %s %s", exc.reason, exc.detail)
        result = {"state": "failed", "reason": exc.reason, "at": clock.now().isoformat()}
    except Exception:
        log.exception("board review failed")
        result = {"state": "failed", "reason": "provider_error", "at": clock.now().isoformat()}
    try:
        store.save_attempt(attempt_id, review=result)
    finally:
        with _running_lock:
            _running.discard(attempt_id)


def start_in_thread(app, attempt_id: str) -> None:
    threading.Thread(target=run, args=(app, attempt_id), name="board-review", daemon=True).start()


def ensure(app, row: dict) -> dict:
    """For a handed-in practice test or simulation: start its review if it has none yet (or a lost one). Returns the row as it is now."""
    if row["kind"] not in REVIEWED or row["submitted_at"] is None or getattr(app.state, "reviewer", None) is None:
        return row
    review = row.get("review")
    if review and not (review.get("state") == "pending" and clock.now() - datetime.fromisoformat(review["at"]) > STALE):
        return row
    with _running_lock:
        if row["id"] in _running:
            return row
        _running.add(row["id"])
    row = app.state.store.save_attempt(row["id"], review={"state": "pending", "at": clock.now().isoformat()})
    app.state.run_review(app, row["id"])
    return app.state.store.get_attempt(row["id"]) or row


def student_view(row: dict) -> dict | None:
    """What the student sees: pending, failed, or per question its verdict, feedback and tip (by question key), and the summary."""
    review = row.get("review")
    if not review:
        return None
    if review["state"] != "done":
        return {"state": review["state"]}
    return {"state": "done", "summary": review.get("summary"), "questions": review.get("questions", {})}
