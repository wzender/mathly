#!/usr/bin/env python3
"""Draft the solved example for the help button, for the skills of a lesson, for a teacher to review, and merge the approved ones.

The "?" help of a skill shows its explanation and, where the bank has one, a solved example: one question solved in steps (what
is done, and why) with its answer. No skill has one yet. Students never call the AI, so the examples are written in advance:

  draft  asks Claude for one solved example per skill of a lesson that lacks one, checks each with the same rules the bank is
         loaded with, and writes them to a REVIEW FILE. It never touches the bank, and it spends API money (one request per
         skill: use --dry-run to see what it would send).
  merge  puts the drafts a teacher approved into the bank. A draft is approved when its entry in the review file has
         "approved": true and the teacher's name in "reviewed_by". The teacher may edit an example in the review file
         first: what is merged is what the file says, after the bank's own checks.

    venv/bin/python -m mathly2.scripts.draft_examples draft --lesson t --dry-run
    venv/bin/python -m mathly2.scripts.draft_examples draft --lesson t     # writes mathly2/content/drafts/t.json
    (the teacher reads that file, fixes what is wrong, and marks the good ones approved)
    venv/bin/python -m mathly2.scripts.draft_examples merge mathly2/content/drafts/t.json

Needs ANTHROPIC_API_KEY (or CLAUDE_API_KEY) for `draft`; MATH_MODEL picks the model.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from mathly2.bank import BANK_PATH, check_bank, example_problems, load_bank

DRAFTS_DIR = BANK_PATH.parent / "drafts"
DEFAULT_MODEL = "claude-opus-5-5"
SAMPLE_QUESTIONS = 6          # practice questions shown to the model per skill
STATUS = "טיוטה: עוד לא נבדקה על ידי מורה. סמנו approved ושם ב־reviewed_by רק אחרי שבדקתם את הדוגמה."


class DraftUnavailable(Exception):
    """The model could not give a draft; the message says why."""


# Anthropic rejects numerical constraints in output schemas (minItems...): bank.example_problems checks them.
EXAMPLE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["worked_example"],
    "properties": {"worked_example": {
        "type": "object", "additionalProperties": False, "required": ["question", "steps", "answer"],
        "properties": {
            "question": {"type": "string"}, "answer": {"type": "string"},
            "steps": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["do", "why"],
                "properties": {"do": {"type": "string"}, "why": {"type": "string"}}}}}}}}

SYSTEM = """אתם מורים למתמטיקה לכיתה ט׳ וכותבים דוגמה פתורה אחת למיומנות אחת במסלול תרגול.
תלמיד שנתקע יפתח את העזרה, יקרא את הדוגמה, ילמד ממנה את השיטה ויחזור לשאלות התרגול של המיומנות.
כתבו שאלה חדשה משלכם באותה רמה ובאותו סגנון של שאלות התרגול. היא לא יכולה להיות אחת מהן, וגם לא אחת מהן עם שינוי קל של המספרים.
פתרו אותה בשלבים קצרים (בין שלושה לשישה). בכל שלב: do הוא מה עושים ומה יוצא, ו־why הוא הסיבה, הרעיון שמאחורי הצעד,
ולא חזרה על ה־do במילים אחרות. אם הטעויות הנפוצות שבהמשך רלוונטיות, הראו בשלב המתאים איך נמנעים מהן.
בסוף כתבו את התשובה בקצרה, ובדקו אותה: חשבו כל שלב פעם נוספת לפני שאתם כותבים אותו.
כתבו בעברית. נוסחאות בין סימני דולר, כמו בשאלות התרגול: $(x + 3)(x − 5)$. השתמשו במינוס ״−״ ובחזקה ״²״ כמו בהן.
החזירו רק את הדוגמה במבנה שנדרש."""


def skills_without_examples(data: dict, lesson_id: str) -> list[dict]:
    return [s for s in data["skills"] if s["unit"] == lesson_id and not s.get("worked_example")]


def skill_brief(skill: dict, mistakes: dict) -> dict:
    """What the model sees of a skill: its description, some practice questions with the right answer, and the
    common mistakes that those questions' wrong choices stand for (names and tips, to show how to avoid them)."""
    questions, known = [], {}
    for q in skill.get("questions", [])[:SAMPLE_QUESTIONS]:
        right = next((c["text"] for c in q["choices"] if c.get("correct")), "")
        slips = []
        for c in q["choices"]:
            if c.get("mistake") in mistakes:
                known[c["mistake"]] = {"name": mistakes[c["mistake"]]["name"], "tip": mistakes[c["mistake"]]["tip"]}
                slips.append({"answer": c["text"], "mistake": mistakes[c["mistake"]]["name"]})
        questions.append({"question": q["question"], "right_answer": right, "wrong_answers": slips})
    return {"skill": skill["name"], "description": skill.get("description", ""), "practice_questions": questions,
            "common_mistakes": list(known.values())}


def clean(answer: dict) -> dict:
    """The model's answer in the bank's shape."""
    worked = answer["worked_example"]
    return {"worked_example": {"question": worked["question"], "answer": worked["answer"],
                               "steps": [{"do": s["do"], "why": s["why"]} for s in worked["steps"]]}}


def draft_one(client, model: str, skill: dict, mistakes: dict) -> dict:
    """A solved example for a skill; raises DraftUnavailable if the model could not give one."""
    import anthropic
    try:
        response = client.messages.create(
            model=model, max_tokens=8000, system=SYSTEM,
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": EXAMPLE_SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(skill_brief(skill, mistakes), ensure_ascii=False)}])
    except anthropic.APIError as exc:
        raise DraftUnavailable(f"{type(exc).__name__}: {getattr(exc, 'message', exc)}") from exc
    if response.stop_reason != "end_turn":
        raise DraftUnavailable(f"stop_reason={response.stop_reason}")
    try:
        return clean(json.loads(next(b.text for b in response.content if b.type == "text")))
    except (ValueError, StopIteration, KeyError, TypeError) as exc:
        raise DraftUnavailable("the answer was not the expected JSON") from exc


def draft_lesson(client, model: str, data: dict, lesson_id: str, only: list[str] | None = None,
                 limit: int | None = None) -> dict:
    """The review file's content for a lesson: a draft (and what is wrong with it, if anything) per skill without one."""
    wanted = [s for s in skills_without_examples(data, lesson_id) if not only or s["id"] in only]
    drafts = {}
    for skill in wanted[:limit]:
        entry = {"approved": False, "reviewed_by": "", "example": None, "problems": []}
        try:
            entry["example"] = draft_one(client, model, skill, data["mistakes"])
            entry["problems"] = example_problems({**skill, **entry["example"]}, data["mistakes"])
        except DraftUnavailable as exc:
            entry["problems"] = [f"no draft: {exc}"]
        drafts[skill["id"]] = entry
    return {"status": STATUS, "model": model, "lesson": lesson_id, "drafted": date.today().isoformat(), "drafts": drafts}


def merge_approved(review: dict, data: dict) -> tuple[dict, list[str], list[str]]:
    """The bank data with the approved drafts added, the ids merged, and why any others were left out."""
    merged, skipped = [], []
    skills = {s["id"]: s for s in data["skills"]}
    for sid, entry in review.get("drafts", {}).items():
        example = entry.get("example") or {}
        if not entry.get("approved"):
            skipped.append(f"{sid}: not approved")
        elif not str(entry.get("reviewed_by") or "").strip():
            skipped.append(f"{sid}: approved without the reviewer's name (reviewed_by)")
        elif sid not in skills:
            skipped.append(f"{sid}: no such skill")
        elif skills[sid].get("worked_example"):
            skipped.append(f"{sid}: already has a solved example")
        elif not example.get("worked_example"):
            skipped.append(f"{sid}: the draft has no solved example")
        elif found := example_problems({**skills[sid], **example}, data["mistakes"]):
            skipped.append(f"{sid}: {'; '.join(found)}")
        else:
            skills[sid]["worked_example"] = example["worked_example"]
            merged.append(sid)
    return data, merged, skipped


def write_bank(data: dict, path: Path | None = None) -> None:
    """Write the bank in the file's own format. The path is looked up now, not when this module is loaded."""
    (path or BANK_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")   # the file's own format


def cmd_draft(args) -> int:
    data = load_bank().data
    if not any(u["id"] == args.lesson for u in data["units"]):
        print(f"no lesson {args.lesson}: " + ", ".join(u["id"] for u in data["units"]), file=sys.stderr)
        return 2
    todo = [s for s in skills_without_examples(data, args.lesson) if not args.skill or s["id"] in args.skill][:args.limit]
    model = os.environ.get("MATH_MODEL", "").strip() or DEFAULT_MODEL
    print(f"lesson {args.lesson}: {len(todo)} skills without a solved example: {', '.join(s['id'] for s in todo) or '-'}")
    if args.dry_run or not todo:
        if todo:
            print("\nsystem prompt:\n" + SYSTEM + "\n\nfirst request:\n" +
                  json.dumps(skill_brief(todo[0], data["mistakes"]), ensure_ascii=False, indent=1))
            print(f"\n(dry run: {len(todo)} requests would be sent to {model}; nothing was sent)")
        return 0
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or os.environ.get("CLAUDE_API_KEY", "").strip()
    if not key:
        print("set ANTHROPIC_API_KEY (or CLAUDE_API_KEY)", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else DRAFTS_DIR / f"{args.lesson}.json"
    if out.exists() and not args.force:
        print(f"{out} exists: it may hold a teacher's review. Use --force to overwrite, or --out for another file.", file=sys.stderr)
        return 2
    import anthropic
    review = draft_lesson(anthropic.Anthropic(api_key=key, timeout=120.0, max_retries=1), model, data, args.lesson,
                          args.skill, args.limit)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(review, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    bad = [sid for sid, e in review["drafts"].items() if e["problems"]]
    print(f"wrote {out}: {len(review['drafts'])} drafts, {len(bad)} with problems{': ' + ', '.join(bad) if bad else ''}")
    return 0


def cmd_merge(args) -> int:
    review = json.loads(Path(args.review).read_text(encoding="utf-8"))
    data = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    data, merged, skipped = merge_approved(review, data)
    for line in skipped:
        print("left out: " + line)
    if not merged:
        print("nothing to merge")
        return 1
    if found := check_bank(data):    # the app loads the bank with this check: never write what it would refuse
        print("refusing to write, the bank would not load: " + "; ".join(found), file=sys.stderr)
        return 2
    write_bank(data)
    print(f"added solved examples to {BANK_PATH.name}: {', '.join(merged)}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("draft", help="ask Claude for drafts and write a review file")
    d.add_argument("--lesson", required=True)
    d.add_argument("--skill", action="append", help="only this skill (repeat for several)")
    d.add_argument("--limit", type=int, help="at most this many skills")
    d.add_argument("--out", help="the review file (default mathly2/content/drafts/<lesson>.json)")
    d.add_argument("--force", action="store_true", help="overwrite an existing review file")
    d.add_argument("--dry-run", action="store_true", help="show what would be sent; call nothing")
    d.set_defaults(run=cmd_draft)
    m = sub.add_parser("merge", help="add the approved drafts of a review file to the bank")
    m.add_argument("review")
    m.set_defaults(run=cmd_merge)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
