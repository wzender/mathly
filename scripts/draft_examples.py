#!/usr/bin/env python3
"""Draft worked examples for the skills of a unit, for a math teacher to review, and merge the approved ones.

The path shows a student who is stuck a worked example (`example` in app/math_algebra9.json): a question of its own,
solved in steps (what to do, and why), and the answer. Students never call the AI, so the examples are written in
advance. This script helps write them:

  draft  asks Claude for one example per skill of a unit that has none, checks each against the same rules the app
         loads the data with, and writes them to a REVIEW FILE. It never touches app/math_algebra9.json, and it
         spends API money (one request per skill: use --dry-run to see what it would send).
  merge  puts the drafts a teacher approved into app/math_algebra9.json. A draft is approved when its entry in the
         review file has "approved": true and the teacher's name in "reviewed_by". The teacher may edit an example in
         the review file first: what is merged is what the file says, after the app's own checks.

    python scripts/draft_examples.py draft --unit t --dry-run
    python scripts/draft_examples.py draft --unit t            # writes docs/example-drafts/t.json
    (the teacher reads docs/example-drafts/t.json, fixes what is wrong, and marks the good ones approved)
    python scripts/draft_examples.py merge docs/example-drafts/t.json

Needs ANTHROPIC_API_KEY (or CLAUDE_API_KEY) for `draft`; MATH_MODEL picks the model, as for the rest of the app.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.math_photo import PhotoUnavailable, failure_reason, math_model, photo_client   # noqa: E402
from app.math_skills import GRAPH, algebra9, example_problems, problems, questions, skills_without_example   # noqa: E402

DRAFTS_DIR = ROOT / "docs" / "example-drafts"
STATUS = "טיוטה: עוד לא נבדקה על ידי מורה. סמנו approved ושם ב־reviewed_by רק אחרי שבדקתם את הדוגמה."
EXAMPLE_SCHEMA = {   # Anthropic rejects numerical constraints in output schemas (minItems...): app.math_skills checks them
    "type": "object", "additionalProperties": False, "required": ["question", "steps", "answer"],
    "properties": {
        "question": {"type": "string"},
        "steps": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["do", "why"],
            "properties": {"do": {"type": "string"}, "why": {"type": "string"}}}},
        "answer": {"type": "string"}}}
SYSTEM = """אתם מורים למתמטיקה לכיתה ט׳ וכותבים דוגמה פתורה למיומנות אחת במסלול תרגול.
תלמיד שנתקע יפתח את הדוגמה, ילמד ממנה את השיטה ויחזור לשאלות התרגול של המיומנות.
כתבו שאלה חדשה משלכם באותה רמה ובאותו סגנון של שאלות התרגול. היא לא יכולה להיות אחת מהן, וגם לא אחת מהן עם שינוי קל של המספרים.
פתרו אותה בשלבים קצרים (בין שלושה לשישה). בכל שלב: do הוא מה עושים ומה יוצא, ו־why הוא הסיבה, הרעיון שמאחורי הצעד,
ולא חזרה על ה־do במילים אחרות. אם הטעויות הנפוצות שבהמשך רלוונטיות, הראו בשלב המתאים איך נמנעים מהן.
בסוף כתבו את התשובה בקצרה, ובדקו אותה: חשבו כל שלב פעם נוספת לפני שאתם כותבים אותו.
כתבו בעברית. נוסחאות בין סימני דולר, כמו בשאלות התרגול: $(x + 3)(x − 5)$. השתמשו במינוס ״−״ ובחזקה ״²״ כמו בהן.
החזירו רק את הדוגמה במבנה שנדרש."""


def skill_brief(skill: dict, mistakes: dict) -> dict:
    """What the model sees of a skill: its description and practice questions with the right answer and the mistakes."""
    out = []
    for q in questions(skill):
        right = next((c["text"] for c in q.get("choices", []) if c.get("correct")), "")
        slips = [{"answer": c["text"], "mistake": mistakes[c["mistake"]]["name"], "tip": mistakes[c["mistake"]]["tip"]}
                 for c in q.get("choices", []) if c.get("mistake") in mistakes]
        out.append({"question": q.get("question", ""), "right_answer": right, "common_mistakes": slips})
    return {"skill": skill["name"], "description": skill.get("description", ""), "practice_questions": out}


def draft_one(client, model: str, skill: dict, mistakes: dict) -> dict:
    """One example for a skill; raises PhotoUnavailable if the model could not give one."""
    import anthropic
    try:
        response = client.messages.create(
            model=model, max_tokens=8000, system=SYSTEM,
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": EXAMPLE_SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(skill_brief(skill, mistakes), ensure_ascii=False)}])
    except anthropic.APIError as exc:
        reason, detail = failure_reason(exc)
        raise PhotoUnavailable(f"{reason}: {detail}", reason, detail) from exc
    if response.stop_reason != "end_turn":
        raise PhotoUnavailable(f"stop_reason={response.stop_reason}", "refused" if response.stop_reason == "refusal" else "incomplete")
    try:
        return json.loads(next(b.text for b in response.content if b.type == "text"))
    except (ValueError, StopIteration) as exc:
        raise PhotoUnavailable("the answer was not JSON", "bad_output") from exc


def draft_unit(client, model: str, graph: dict, unit_id: str, only: list[str] | None = None, limit: int | None = None) -> dict:
    """The review file's content for a unit: a draft (and what is wrong with it, if anything) per skill without one."""
    wanted = [s for s in graph["skills"] if s["unit"] == unit_id and s["id"] in skills_without_example(graph)
              and (not only or s["id"] in only)]
    drafts = {}
    for skill in wanted[:limit]:
        entry = {"approved": False, "reviewed_by": "", "example": None, "problems": []}
        try:
            entry["example"] = draft_one(client, model, skill, graph["mistakes"])
            entry["problems"] = example_problems({**skill, "example": entry["example"]})
        except PhotoUnavailable as exc:
            entry["problems"] = [f"no draft: {exc}"]
        drafts[skill["id"]] = entry
    return {"status": STATUS, "model": model, "unit": unit_id, "drafted": date.today().isoformat(), "drafts": drafts}


def merge_approved(review: dict, graph: dict) -> tuple[dict, list[str], list[str]]:
    """The graph with the approved drafts added, the ids merged, and why any others were left out."""
    merged, skipped = [], []
    skills = {s["id"]: s for s in graph["skills"]}
    for sid, entry in review.get("drafts", {}).items():
        if not entry.get("approved"):
            skipped.append(f"{sid}: not approved")
        elif not str(entry.get("reviewed_by") or "").strip():
            skipped.append(f"{sid}: approved without the reviewer's name (reviewed_by)")
        elif sid not in skills:
            skipped.append(f"{sid}: no such skill")
        elif "example" in skills[sid]:
            skipped.append(f"{sid}: already has an example")
        elif found := example_problems({**skills[sid], "example": entry.get("example")}):
            skipped.append(f"{sid}: {'; '.join(found)}")
        else:
            skills[sid]["example"] = entry["example"]
            merged.append(sid)
    return graph, merged, skipped


def cmd_draft(args) -> int:
    graph = algebra9()
    if not any(u["id"] == args.unit for u in graph["units"]):
        print(f"no unit {args.unit}: " + ", ".join(u["id"] for u in graph["units"]), file=sys.stderr)
        return 2
    todo = [s for s in graph["skills"] if s["unit"] == args.unit and s["id"] in skills_without_example(graph)
            and (not args.skill or s["id"] in args.skill)][:args.limit]
    print(f"unit {args.unit}: {len(todo)} skills without an example: {', '.join(s['id'] for s in todo) or '-'}")
    if args.dry_run or not todo:
        if todo:
            print("\nsystem prompt:\n" + SYSTEM + "\n\nfirst request:\n" +
                  json.dumps(skill_brief(todo[0], graph["mistakes"]), ensure_ascii=False, indent=1))
            print(f"\n(dry run: {len(todo)} requests would be sent to {math_model()})")
        return 0
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or os.environ.get("CLAUDE_API_KEY", "").strip()
    if not key:
        print("set ANTHROPIC_API_KEY (or CLAUDE_API_KEY)", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else DRAFTS_DIR / f"{args.unit}.json"
    if out.exists() and not args.force:
        print(f"{out} exists: it may hold a teacher's review. Use --force to overwrite, or --out for another file.", file=sys.stderr)
        return 2
    review = draft_unit(photo_client(key), math_model(), graph, args.unit, args.skill, args.limit)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(review, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    bad = [sid for sid, e in review["drafts"].items() if e["problems"]]
    print(f"wrote {out}: {len(review['drafts'])} drafts, {len(bad)} with problems{': ' + ', '.join(bad) if bad else ''}")
    return 0


def cmd_merge(args) -> int:
    review = json.loads(Path(args.review).read_text(encoding="utf-8"))
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    graph, merged, skipped = merge_approved(review, graph)
    for line in skipped:
        print("left out: " + line)
    if not merged:
        print("nothing to merge")
        return 1
    if found := problems(graph):   # the app loads the file with this check: never write what it would refuse
        print("refusing to write, the data would not load: " + "; ".join(found), file=sys.stderr)
        return 2
    GRAPH.write_text(json.dumps(graph, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"added examples to {GRAPH.name}: {', '.join(merged)}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("draft", help="ask Claude for drafts and write a review file")
    d.add_argument("--unit", required=True)
    d.add_argument("--skill", action="append", help="only this skill (repeat for several)")
    d.add_argument("--limit", type=int, help="at most this many skills")
    d.add_argument("--out", help="the review file (default docs/example-drafts/<unit>.json)")
    d.add_argument("--force", action="store_true", help="overwrite an existing review file")
    d.add_argument("--dry-run", action="store_true", help="show what would be sent; call nothing")
    d.set_defaults(run=cmd_draft)
    m = sub.add_parser("merge", help="add the approved drafts of a review file to app/math_algebra9.json")
    m.add_argument("review")
    m.set_defaults(run=cmd_merge)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
