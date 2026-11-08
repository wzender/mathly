"""The twelve comets (PRD CMT-3) and the rule for when one crosses (CMT-1). The server decides both: the browser only draws."""
import random
from datetime import date

COMETS = [
    {"id": "pi", "sym": "π", "name": "פאי", "fact": "היחס בין ההיקף של מעגל לקוטר שלו. הספרות שלו אחרי הנקודה לא נגמרות ולא חוזרות על עצמן."},
    {"id": "fib", "sym": "1,1,2,3,5", "name": "פיבונאצ׳י", "fact": "כל מספר בסדרה הוא סכום שני הקודמים. הסדרה מופיעה בספירלות של גרעיני חמנייה ובאצטרובלים."},
    {"id": "phi", "sym": "φ", "name": "יחס הזהב", "fact": "בערך 1.618. מחלקים קטע כך שהיחס בין השלם לחלק הגדול שווה ליחס בין הגדול לקטן. מופיע בפרחים, בצדפים ובאמנות."},
    {"id": "inf", "sym": "∞", "name": "אינסוף", "fact": "יש אינסוף מספרים שלמים, ויש גם אינסוף מספרים בין 0 ל־1. מתברר שהאינסוף השני גדול יותר."},
    {"id": "e", "sym": "e", "name": "המספר e", "fact": "בערך 2.718. מופיע בכל מקום שבו משהו גדל בקצב שתלוי בגודל שלו: ריבית, אוכלוסיות, חיידקים."},
    {"id": "r2", "sym": "√2", "name": "שורש 2", "fact": "האורך של אלכסון בריבוע שצלעו 1. כבר היוונים הקדמונים הוכיחו שאי אפשר לכתוב אותו כשבר."},
    {"id": "zero", "sym": "0", "name": "אפס", "fact": "במשך אלפי שנים לא היה סימן לאפס. הוא הגיע מהודו, ובזכותו אפשר לכתוב כל מספר בעשר ספרות בלבד."},
    {"id": "pyth", "sym": "a²+b²=c²", "name": "פיתגורס", "fact": "במשולש ישר זווית, סכום ריבועי הניצבים שווה לריבוע היתר. ידוע ליותר מ־370 הוכחות שונות."},
    {"id": "prime", "sym": "2,3,5,7", "name": "מספרים ראשוניים", "fact": "מספרים שמתחלקים רק ב־1 ובעצמם. יש אינסוף כאלה, ועליהם בנויה ההצפנה של האינטרנט."},
    {"id": "pascal", "sym": "1 2 1", "name": "משולש פסקל", "fact": "כל מספר הוא סכום שני המספרים שמעליו. השורות שלו נותנות את המקדמים של (a + b) בכל חזקה."},
    {"id": "euler", "sym": "V−E+F=2", "name": "נוסחת אוילר", "fact": "בכל גוף משוכלל, קודקודים פחות מקצועות ועוד פאות שווה תמיד 2. נסו על קובייה: 8 − 12 + 6."},
    {"id": "mobius", "sym": "∞", "name": "טבעת מביוס", "fact": "רצועת נייר עם חצי סיבוב: יש לה רק צד אחד ושפה אחת. נמלה שהולכת עליה תעבור בשני ה״צדדים״."},
]
IDS = [c["id"] for c in COMETS]
CHANCE = 0.12          # a right answer's chance of a comet, once the student has been offered their first


def get(comet_id: str) -> dict | None:
    return next((c for c in COMETS if c["id"] == comet_id), None)


def due(state: dict | None, caught: set[str], today: date, goal_just_reached: bool, roll: float | None = None) -> bool:
    """Is a comet due after this right answer? At most one a day; none once all are caught; the first one only on the answer that
    reaches the daily goal; after any comet was offered, a small chance on each right answer. `roll` (0..1) is injectable for tests."""
    if len(caught) >= len(COMETS):
        return False
    last = (state or {}).get("last_comet_day")
    if last == today:
        return False
    if last is None:
        return goal_just_reached
    return (random.random() if roll is None else roll) < CHANCE


def surely_not(state: dict | None, today: date, goal_just_reached: bool, roll: float | None) -> bool:
    """True when no comet can be due whatever the student has caught, so the caught list need not be read (the usual case)."""
    last = (state or {}).get("last_comet_day")
    if last == today:
        return True
    if last is None:
        return not goal_just_reached
    return (random.random() if roll is None else roll) >= CHANCE


def pick(caught: set[str], roll: float | None = None) -> dict | None:
    """A comet the student does not have yet, at random."""
    left = [c for c in COMETS if c["id"] not in caught]
    if not left:
        return None
    return left[int((random.random() if roll is None else roll) * len(left)) % len(left)]

