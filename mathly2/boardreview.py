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

from . import clock, writtentest

log = logging.getLogger("mathly2.boardreview")

REVIEWED = ("exercise_test", "simulation")
DEFAULT_MODEL = "gemini-2.5-flash"                 # a model with a free tier; GEMINI_MODEL overrides it
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"   # the models this key can use, when the named one is gone
STALE = timedelta(minutes=10)                     # a pending review older than this was lost (a restart) and is started again
RETRIES = 3                                       # tries after "too many requests", waiting as the API asks (or 20, 40 s)
SIDE = 1280                                       # a board is shrunk to this longest side before it is sent
VERDICTS = ("correct", "partial", "wrong", "unclear")

INSTRUCTIONS = """אתם מורים למתמטיקה בכיתה ט בישראל. תלמיד פתר שאלה אמריקאית במבחן, וכתב את הדרך על לוח. קיבלתם את השאלה, התשובות האפשריות, \
התשובה הנכונה (רק בשבילכם), התשובה שהתלמיד בחר, ותמונה של הלוח שלו.
הַעריכו את הדרך (לא רק את התשובה הסופית):
- verdict: "correct" אם הדרך נכונה ומובילה לתשובה; "partial" אם יש התחלה נכונה או רעיון נכון אבל טעות או חוסר; "wrong" אם השיטה שגויה; "unclear" אם אי אפשר לקרוא או שאין בלוח דרך של ממש.
- feedback: משפט או שניים לתלמיד, בעברית, בפנייה ברבים (אתם), חם וענייני: מה טוב בדרך, ואם יש טעות, איפה היא הטעות הראשונה ומה סוגה.
- tip: טיפ אחד קצר ומעשי לפעם הבאה.
אסור לכתוב את התשובה הסופית הנכונה, את המספר שלה או איזו אפשרות נכונה. אם התלמיד טעה, כוונו אותו לשלב, אל תפתרו בשבילו.
נוסחאות כתבו בתוך $...$."""

WRITTEN_INSTRUCTIONS = """אתם מורים למתמטיקה בכיתה ט בישראל ובודקים מבחן אמיתי. תלמיד פתר שאלה פתוחה (בלי תשובות לבחירה) וכתב את הפתרון על לוח. \
קיבלתם את השאלה, התשובה הנכונה (רק בשבילכם), התשובה הסופית שהתלמיד הקליד (אם יש תיבה כזו לשאלה) ותמונה של הלוח שלו.
בדקו את הפתרון כמו בבדיקת מבחן:
- verdict: "correct" אם הדרך נכונה ומגיעה לתשובה הנכונה; "partial" אם הדרך ברובה נכונה אבל יש טעות חישוב, שלב חסר או תשובה סופית שגויה; \
"wrong" אם השיטה שגויה או שאין התקדמות של ממש; "unclear" אם אי אפשר לקרוא את הלוח או שאין בו פתרון.
תשובה סופית נכונה בלי דרך בלוח אינה "correct".
- feedback: משפט או שניים לתלמיד, בעברית, בפנייה ברבים (אתם), חם וענייני: מה טוב בפתרון, ואם יש טעות, איפה הטעות הראשונה ומה סוגה.
- tip: טיפ אחד קצר ומעשי לפעם הבאה.
אסור לכתוב את התשובה הסופית הנכונה או את המספר שלה. אם התלמיד טעה, כוונו אותו לשלב, אל תפתרו בשבילו.
נוסחאות כתבו בתוך $...$."""

READ_INSTRUCTIONS = """אתם מורים למתמטיקה בכיתה ט בישראל. קיבלתם תמונה של שאלה שתלמיד צילם (מדף עבודה, ספר או מבחן).
- readable: האם רואים בתמונה שאלה במתמטיקה אחת שאפשר לקרוא ולפתור.
- question: נוסח השאלה בעברית, מלא ומדויק כפי שהוא בתמונה, נוסחאות בתוך $...$: הנתונים, ואחריהם כל הסעיפים, כל סעיף בשורה משלו שמתחילה באות שלו (למשל "א. מצאו את גודלה של ∠B."). אם יש שרטוט, תארו במילים מה שנחוץ לפתרון. אם בתמונה יש כמה שאלות, קראו רק את השאלה השלמה שבמרכז התמונה.
- העתיקו את כל הנתונים במלואם, גם מה שכתוב בתוך סוגריים (למשל "משולש שווה־שוקיים ($AB = AC$)"). אל תשאירו סוגריים ריקים.
- answer: התשובה הסופית הנכונה, קצרה (למשל $x = 5$). בשאלה עם סעיפים: שורה לכל סעיף שמתחילה באות שלו (למשל "א. $∠B = 30°$"), ובסעיף הוכחה "הוכחה".
- steps: שלבי הפתרון, 2 עד 6 שלבים קצרים. בשאלה עם סעיפים: עד 10 שלבים, וכל שלב מתחיל באות הסעיף שלו (למשל "ב. ..."). כש־proof הוא true: כל שלב הוא שורה בטבלה, "טענה | נימוק" (למשל "א. ∠B = ∠C | במשולש שווה־שוקיים זוויות הבסיס שוות").
- proof: true אם זו שאלה בגיאומטריה שפותרים בטבלת טענה ונימוק (הוכחה, או מציאת זווית או אורך בעזרת משפטים), אחרת false.
- skill: המזהה של המיומנות מהרשימה שהשאלה הכי מתאימה לה, או מחרוזת ריקה אם אף אחת לא מתאימה (שאלה "חיצונית").
- כתבו סימנים מתמטיים כתווים רגילים: △ ∠ ⊥ ∥ ° √ ≤ ≥ ≠ ± π ² ³ ₁ ₂, ושבר כ־a/b. אסור לכתוב פקודות LaTeX כמו \\triangle, \\angle, \\frac, \\text או ^\\circ.
אל תמציאו: אם משהו בתמונה לא ברור, readable = false."""

GRADE_INSTRUCTIONS = """אתם מורים למתמטיקה בכיתה ט בישראל ובודקים פתרון של תלמיד לשאלה פתוחה. קיבלתם את השאלה, התשובה הנכונה (רק בשבילכם), \
התשובה הסופית שהתלמיד הקליד (אם יש) ותמונה של הלוח שלו.
- score: ציון מ־0 עד 100 לפתרון כולו (בשאלה עם סעיפים: לכל סעיף משקל שווה), כמו בבדיקת מבחן: דרך נכונה ותשובה נכונה 100; דרך נכונה עם טעות חישוב 60 עד 85; התחלה נכונה בלבד 20 עד 50; \
שיטה שגויה או לוח בלי פתרון 0 עד 15. תשובה סופית נכונה בלי דרך בלוח לא מקבלת יותר מ־30.
- verdict: "correct", "partial", "wrong" או "unclear" (אי אפשר לקרוא את הלוח).
- feedback: משפט או שניים לתלמיד, בעברית, בפנייה ברבים (אתם), חם וענייני: מה טוב בדרך, ואיפה הטעות הראשונה אם יש.
- tip: טיפ אחד קצר לפעם הבאה.
- טבלת טענה/נימוק: אם התלמיד מילא טבלה, היא הפתרון, והלוח (אם יש) הוא שרטוט וחישובי עזר. בדקו כל שורה: הטענה נכונה ונובעת מהקודמות, והנימוק נכון ומדויק (נתון, הגדרה או משפט). נימוק חסר או לא מדויק מוריד נקודות, גם כשהטענה נכונה. במשוב הפנו לשורה לפי המספר שלה.
- parts: רק בשאלה עם סעיפים: לכל סעיף label (האות שלו), verdict ו־feedback של משפט אחד. בשאלה בלי סעיפים: רשימה ריקה.
אסור לכתוב את התשובה הסופית הנכונה או את המספר שלה. נוסחאות בתוך $...$."""

TUTOR_INSTRUCTIONS = """אתם מורים למתמטיקה סבלניים וחמים לתלמידי כיתה ט בישראל, ועוזרים לתלמיד בשאלה אחת בשיחה קצרה.
- ענו בעברית, בפנייה ברבים (אתם), קצר: עד 4 משפטים. נוסחאות בתוך $...$, עם סימנים כתווים רגילים (△ ∠ ⊥ ° √ ²) ובלי פקודות LaTeX.
- עזרו לתלמיד לחשוב בעצמו: הסבירו מושג, שאלו שאלה מכוונת, הצביעו על הצעד הבא. אל תפתרו במקומו.
- אם הפתרון המלא עוד לא נחשף לתלמיד: אסור לכתוב את התשובה הסופית או צעדים שהוא עוד לא קיבל. אם הוא מבקש את התשובה, הציעו לו את הכפתורים "הצעד הבא" או "הפתרון המלא".
- אם הפתרון כבר נחשף או שהשאלה נבדקה: מותר להסביר את הפתרון, את המשוב ואת הטעויות בלוח.
- אם התלמיד כותב משהו שלא קשור לשאלה או למתמטיקה, החזירו אותו בעדינות לשאלה. אל תבקשו ואל תשמרו פרטים אישיים."""

TUTOR_SCHEMA = {"type": "OBJECT", "properties": {"reply": {"type": "STRING"}}, "required": ["reply"]}

READ_SCHEMA = {"type": "OBJECT", "properties": {"readable": {"type": "BOOLEAN"}, "question": {"type": "STRING"}, "answer": {"type": "STRING"},
                                              "steps": {"type": "ARRAY", "items": {"type": "STRING"}}, "skill": {"type": "STRING"},
                                              "proof": {"type": "BOOLEAN"}},
               "required": ["readable", "question", "answer", "steps", "skill"]}
GRADE_SCHEMA = {"type": "OBJECT", "properties": {"score": {"type": "INTEGER"}, "verdict": {"type": "STRING", "enum": list(VERDICTS)},
                                               "feedback": {"type": "STRING"}, "tip": {"type": "STRING"},
                                               "parts": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                                                   "label": {"type": "STRING"}, "verdict": {"type": "STRING", "enum": list(VERDICTS)},
                                                   "feedback": {"type": "STRING"}}, "required": ["label", "verdict", "feedback"]}}},
                "required": ["score", "verdict", "feedback", "tip"]}

SUMMARY_INSTRUCTIONS = """אתם מורים למתמטיקה בכיתה ט. לפניכם הערכות של הדרך של תלמיד בשאלות של מבחן אחד (לכל שאלה: הנושא, הערכה ומשוב).
כתבו summary: משפט או שניים לתלמיד, בעברית, בפנייה ברבים (אתם): חוזקה אחת בדרך ודבר אחד לשפר. בלי תשובות נכונות ובלי מספרים של תשובות."""

SCHEMA = {"type": "OBJECT", "properties": {"verdict": {"type": "STRING", "enum": list(VERDICTS)}, "feedback": {"type": "STRING"}, "tip": {"type": "STRING"}},
          "required": ["verdict", "feedback", "tip"]}
SUMMARY_SCHEMA = {"type": "OBJECT", "properties": {"summary": {"type": "STRING"}}, "required": ["summary"]}
STOPPING = ("rate_limited", "api_key_invalid", "permission", "model_not_found", "no_connection")   # no point in asking about the next question
MIN_GAP = 5.0                                   # seconds between requests: the free tier counts requests a minute


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

    def __init__(self, key: str, model: str = "", sleep=time.sleep, gap: float = MIN_GAP, now=time.monotonic) -> None:
        self.key, self.model, self.sleep, self.gap, self.now = key, clean_model(model) or DEFAULT_MODEL, sleep, gap, now
        self._last = None
        self._lock = threading.Lock()                   # one request at a time: the free tier counts requests a minute

    def _parts(self, item: dict) -> list[dict]:
        if item.get("written"):                         # the written simulation: an open question, its board and the typed final answer
            typed = item.get("typed")
            final = ("התלמיד לא הקליד תשובה סופית" if not typed else
                     f"התשובה הסופית שהתלמיד הקליד: {typed} ({'שווה' if item.get('matches') else 'לא שווה'} לתשובה הנכונה)") if item.get("has_box") \
                else "לשאלה הזו אין תיבה לתשובה סופית: התשובה צריכה להופיע בלוח"
            return [{"text": WRITTEN_INSTRUCTIONS},
                    {"text": f"\n\nהשאלה:\n{item['question']}\nהתשובה הנכונה (לא לגלות): {item['right']}\n{final}\nהלוח של התלמיד:"},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(_small(item["image"])).decode()}}]
        choices = "\n".join(f"  {_letter(i)}. {c}" for i, c in enumerate(item["choices"]))
        picked = _letter(item["picked"]) if item["picked"] is not None else "לא ענה"
        return [{"text": INSTRUCTIONS},
                {"text": f"\n\nהשאלה:\n{item['question']}\nאפשרויות:\n{choices}\nהתשובה הנכונה (לא לגלות): {_letter(item['correct'])}\n"
                         f"התלמיד בחר: {picked}\nהלוח של התלמיד:"},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(_small(item["image"])).decode()}}]

    def _call(self, body: bytes) -> dict:
        request = urllib.request.Request(ENDPOINT.format(model=self.model), data=body, method="POST",
                                         headers={"Content-Type": "application/json", "x-goog-api-key": self.key})
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read())

    def _models(self) -> list[str]:
        """The names of the models this key can generate with (no "models/" prefix)."""
        request = urllib.request.Request(MODELS, headers={"x-goog-api-key": self.key})
        with urllib.request.urlopen(request, timeout=30) as response:
            listed = json.loads(response.read()).get("models", [])
        return [clean_model(m.get("name", "")) for m in listed if "generateContent" in m.get("supportedGenerationMethods", [])]

    def _another_model(self) -> str | None:
        """When the model is not found (a wrong name, or retired): a Flash model this key has, the newest stable one first."""
        try:
            names = self._models()
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None
        return pick_model(names, self.model)

    def review_one(self, item: dict, on_event=lambda step, **info: None) -> dict:
        """One question with its board -> {verdict, feedback, tip}."""
        return self._ask(self._parts(item), SCHEMA, on_event)

    def read_question(self, image: bytes, skills: list[dict], subject: str = "") -> dict:
        """A photographed question -> {readable, question, answer, steps, skill} (skill: an id of `skills`, or "" for external)."""
        listed = "\n".join(f"  {s['id']}: {s['name']}" for s in skills)
        return self._ask([{"text": READ_INSTRUCTIONS},
                          {"text": f"\n\nהמקצוע: {subject or 'מתמטיקה'}\nהמיומנויות (מזהה: שם):\n{listed}\n\nהתמונה:"},
                          {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(_small(image)).decode()}}], READ_SCHEMA, lambda *a, **k: None)

    def grade_open(self, question: str, answer: str, typed: str | None, board: bytes | None, proof: str | None = None) -> dict:
        """A student's work on an open question (the board, a claim/reason table, or both) -> {score, verdict, feedback, tip, parts}."""
        final = f"התשובה הסופית שהתלמיד הקליד (בשאלה עם סעיפים: אות=תשובה): {typed}" if typed else "התלמיד לא הקליד תשובה סופית"
        table = f"\nטבלת הטענה/נימוק של התלמיד:\n{proof}\n" if proof else ""
        parts = [{"text": GRADE_INSTRUCTIONS},
                 {"text": f"\n\nהשאלה:\n{question}\nהתשובה הנכונה (לא לגלות): {answer}\n{final}\n{table}"
                          + ("הלוח של התלמיד:" if board else "התלמיד לא כתב בלוח.")}]
        if board:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(_small(board)).decode()}})
        return self._ask(parts, GRADE_SCHEMA, lambda *a, **k: None)

    def tutor_reply(self, context: dict, history: list[dict], message: str, board: bytes | None = None) -> str:
        """One reply of the help conversation. `context`: question, answer, steps (all, for the tutor), shown (how many steps the student
        has), full (the full solution was revealed or the question was checked), review (the check's feedback, if any)."""
        known = ("הפתרון המלא כבר נחשף לתלמיד או שהשאלה נבדקה: מותר להסביר הכול." if context.get("full")
                 else f"התלמיד קיבל עד עכשיו {context.get('shown', 0)} צעדים מהפתרון. אל תגלו את התשובה ואת הצעדים הבאים.")
        steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(context.get("steps") or []))
        review = context.get("review") or {}
        talk = "\n".join(f"{'תלמיד' if m['role'] == 'student' else 'מורה'}: {m['text']}" for m in history[-12:])
        parts = [{"text": TUTOR_INSTRUCTIONS},
                 {"text": f"\n\nהשאלה:\n{context.get('question', '')}\nהתשובה הנכונה (רק בשבילכם): {context.get('answer', '')}\n"
                          f"שלבי הפתרון (רק בשבילכם):\n{steps}\n{known}\n"
                          + (f"הבדיקה: {review.get('verdict', '')}. {review.get('feedback', '')}\n" if review.get("verdict") else "")
                          + (f"{context['note']}\n" if context.get("note") else "")
                          + (f"הטבלה שהתלמיד הגיש:\n{review['proof_text']}\n" if review.get("proof_text") else "")
                          + (f"\nהשיחה עד עכשיו:\n{talk}\n" if talk else "") + f"\nהתלמיד כותב עכשיו: {message}"}]
        if board:
            parts += [{"text": "הלוח שהתלמיד הגיש:"}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(_small(board)).decode()}}]
        return str(self._ask(parts, TUTOR_SCHEMA, lambda *a, **k: None).get("reply") or "").strip()

    def summarize(self, reviewed: list[dict], on_event=lambda step, **info: None) -> str:
        """A line about the way in the whole test, from the per-question reviews (text only, no pictures)."""
        lines = "\n".join(f"שאלה {r['n']} ({r.get('skill', '')}): {r['verdict']}. {r['feedback']}" for r in reviewed)
        return str(self._ask([{"text": SUMMARY_INSTRUCTIONS}, {"text": "\n\n" + lines}], SUMMARY_SCHEMA, on_event).get("summary") or "")

    def _ask(self, parts: list[dict], schema: dict, on_event) -> dict:
        body = json.dumps({"contents": [{"role": "user", "parts": parts}],
                           "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "responseSchema": schema}}).encode()
        with self._lock:
            for attempt in range(RETRIES + 1):
                if self._last is not None and self.gap:                     # keep under the free tier's requests a minute
                    left = self.gap - (self.now() - self._last)
                    if left > 0:
                        self.sleep(left)
                try:
                    data = self._call(body)
                    break
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", "replace")[:500]
                    if exc.code == 429 and attempt < RETRIES:
                        wait = _retry_after(detail, 20 * (attempt + 1))
                        on_event("busy", seconds=round(wait))
                        self.sleep(wait)
                        on_event("resumed")
                        continue
                    if exc.code == 404 and not getattr(self, "_switched", False):
                        other = self._another_model()
                        if other:
                            log.warning("Gemini model %s not found; using %s", self.model, other)
                            self.model, self._switched = other, True      # kept for the next reviews too
                            continue
                    raise ReviewFailure({400: "bad_request", 401: "api_key_invalid", 403: "permission", 404: "model_not_found",
                                         429: "rate_limited"}.get(exc.code, "provider_error"), f"HTTP {exc.code} ({self.model}): {detail}") from None
                except (urllib.error.URLError, TimeoutError) as exc:
                    raise ReviewFailure("no_connection", str(exc)[:300]) from None
                finally:
                    self._last = self.now()
        try:
            candidate = data["candidates"][0]
            if candidate.get("finishReason") not in (None, "STOP"):
                raise ReviewFailure("incomplete", str(candidate.get("finishReason")))
            text = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
            out = json.loads(text)
            if not isinstance(out, dict):
                raise ValueError("not an object")
        except ReviewFailure:
            raise
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ReviewFailure("bad_output", f"{type(exc).__name__}: {str(data)[:300]}") from None
        return out


def clean_model(name: str) -> str:
    """A model name as people paste it: spaces, quotes, a "models/" prefix."""
    name = (name or "").strip().strip("'\"").strip()
    return name[len("models/"):] if name.startswith("models/") else name


def pick_model(names: list[str], not_this: str = "") -> str | None:
    """A Flash model to fall back to: stable before preview, full before lite, the newest version first; never an image/audio/TTS one."""
    import re
    def version(n):
        m = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        return float(m.group(1)) if m else 0.0
    special = ("image", "tts", "audio", "live", "embedding", "thinking", "exp", "learnlm", "robotics")
    flash = [n for n in names if n.startswith("gemini-") and "flash" in n and n != not_this and not any(w in n for w in special)]
    flash.sort(key=lambda n: ("preview" in n, "lite" in n, -version(n), len(n)))
    return flash[0] if flash else None


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
        image, skill = app.state.pictures.get(picture["path"]), (bank.skill(q["skill_id"]) or {}).get("name", "")
        if writtentest.is_written(row):
            final, typed = writtentest.final_of(bank, q), writtentest.typed(row, q["key"])
            items.append({"n": n, "skill": skill, "written": True, "question": served["question"], "right": writtentest.right_text(bank, q) or "",
                          "has_box": final is not None, "typed": typed, "matches": writtentest.matches(typed, final), "image": image})
            keys[n] = q["key"]
            continue
        correct = next((c["index"] for c in served["choices"] if (bank.grade(q["skill_id"], q["key"], c["index"]) or {}).get("correct")), 0)
        picked = row["answers"].get(q["key"])
        items.append({"n": n, "skill": skill,
                      "question": served["question"], "choices": [c["text"] for c in served["choices"]], "correct": correct,
                      "picked": picked if isinstance(picked, int) else None, "image": image})
        keys[n] = q["key"]
    return items, keys


def _clean(got: dict) -> dict | None:
    if not isinstance(got, dict) or got.get("verdict") not in VERDICTS:
        return None
    return {"verdict": got["verdict"], "feedback": str(got.get("feedback", ""))[:600], "tip": str(got.get("tip", ""))[:300]}


def run(app, attempt_id: str, keys: list[str] | None = None) -> None:
    """Review a handed-in attempt question by question (`keys`: only these, kept with the earlier review of the rest), then a summary line.
    Never raises: a review with no question checked is stored as {"state": "failed", "reason"}. While it runs, the pending review carries
    its steps (`events`) and the questions checked so far, for the screens."""
    store, reviewer = app.state.store, app.state.reviewer
    started = clock.now().isoformat()
    events: list[dict] = []
    row = store.get_attempt(attempt_id)
    earlier = (row.get("review") or {}) if row and keys else {}          # one question: the rest of the review (kept on the pending one) stays
    questions: dict = dict(earlier.get("questions") or {})

    def save(review: dict) -> None:
        try:
            store.save_attempt(attempt_id, review=review)
        except Exception:                                  # the steps are a courtesy: never fail the review for them
            log.warning("could not save a review step")

    def event(step: str, **info) -> None:
        events.append({"step": step, "at": clock.now().isoformat(), **info})
        save({"state": "pending", "at": started, "events": list(events), "questions": dict(questions), "summary": earlier.get("summary")})

    reason, checked = None, 0
    try:
        items, by_n = _items(app, row)
        if keys:
            items = [it for it in items if by_n[it["n"]] in keys]
        event("boards", count=len(items), total=len(row["questions"]))
        reviewed = []
        for i, item in enumerate(items):
            key = by_n[item["n"]]
            event("question", n=item["n"], i=i + 1, of=len(items))
            try:
                got = _clean(reviewer.review_one(item, on_event=event))
            except ReviewFailure as exc:
                log.warning("board review of a question failed: %s %s", exc.reason, exc.detail)
                reason = exc.reason
                if exc.reason in STOPPING:
                    break
                continue
            if got is None:
                reason = "bad_output"
                continue
            questions[key], checked = got, checked + 1
            reviewed.append({"n": item["n"], "skill": item["skill"], **got})
        summary = earlier.get("summary")
        if reviewed and not keys:
            event("summary")
            try:
                summary = reviewer.summarize(reviewed, on_event=event)[:800] or None
            except ReviewFailure as exc:
                log.warning("board review summary failed: %s", exc.reason)
        if items and not checked:
            result = {"state": "failed", "reason": reason or "provider_error", "model": getattr(reviewer, "model", None)}
        else:
            result = {"state": "done", "summary": summary, "questions": questions, "missing": len(items) - checked,
                      **({"reason": reason} if reason and checked < len(items) else {})}
    except Exception:
        log.exception("board review failed")
        result = {"state": "failed", "reason": "provider_error"}
    result["at"] = clock.now().isoformat()
    try:
        saved = store.save_attempt(attempt_id, review=result)
        if result["state"] == "done":                                   # a written simulation: its grade from the verdicts
            try:
                writtentest.settle_grade(store, app.state.bank, saved)
            except Exception:
                log.exception("could not set the written test's grade")
    finally:
        with _running_lock:
            _running.discard(attempt_id)


def start_in_thread(app, attempt_id: str, keys: list[str] | None = None) -> None:
    threading.Thread(target=run, args=(app, attempt_id, keys), name="board-review", daemon=True).start()


def ensure(app, row: dict, force: bool = False, keys: list[str] | None = None) -> dict:
    """For a handed-in practice test or simulation: start its review if it has none yet (or a lost one). Returns the row as it is now.
    `force` (the teacher asked): any graded attempt, and again after a failed or a finished review."""
    if row["submitted_at"] is None or getattr(app.state, "reviewer", None) is None:
        return row
    if not force and row["kind"] not in REVIEWED:
        return row
    review = row.get("review")
    lost = review and review.get("state") == "pending" and clock.now() - datetime.fromisoformat(review["at"]) > STALE
    if review and not lost and not (force and review.get("state") != "pending"):
        return row
    with _running_lock:
        if row["id"] in _running:
            return row
        _running.add(row["id"])
    try:
        earlier = row.get("review") or {}
        row = app.state.store.save_attempt(row["id"], review={"state": "pending", "at": clock.now().isoformat(),
                                                              **({"questions": earlier.get("questions", {}), "summary": earlier.get("summary")} if keys else {})})
    except Exception:                                   # e.g. the review column's migration was not run: the result still shows
        log.exception("board review could not be saved")
        with _running_lock:
            _running.discard(row["id"])
        return {**row, "review": {"state": "failed", "reason": "database"}}
    if keys:
        app.state.run_review(app, row["id"], keys)
    else:
        app.state.run_review(app, row["id"])
    return app.state.store.get_attempt(row["id"]) or row


def student_view(row: dict) -> dict | None:
    """What the student sees: pending, failed, or per question its verdict, feedback and tip (by question key), and the summary."""
    review = row.get("review")
    if not review:
        return None
    if review["state"] == "pending":
        return {"state": "pending", "at": review.get("at"), "events": review.get("events", []), "questions": review.get("questions", {})}
    if review["state"] != "done":
        return {"state": review["state"]}
    return {"state": "done", "summary": review.get("summary"), "questions": review.get("questions", {})}
