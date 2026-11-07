"""List the content the bank still lacks.   venv/bin/python -m mathly2.scripts.content_gaps [--min-questions N]

A skill needs: a worked example whose every step has "why this step?" choices, and faded examples
(field names below; build-skill-learning fixes the exact shape of their contents).
A lesson needs a quiz. A skill needs enough questions for similar questions and for retakes.
Mistakes should say which skill to go back to."""
from __future__ import annotations

import argparse
import sys

from mathly2.bank import load_bank

MIN_QUESTIONS = 10


def find_gaps(data: dict, min_questions: int = MIN_QUESTIONS) -> dict[str, list[str]]:
    gaps: dict[str, list[str]] = {
        "skills without a worked example": [],
        "worked-example steps without 'why this step?' choices": [],
        "skills without faded examples": [],
        "lessons without a quiz": [],
        "skills without questions": [],
        f"skills with fewer than {min_questions} questions": [],
        "mistakes without a skill to go back to": [],
    }
    for skill in data["skills"]:
        sid = skill["id"]
        example = skill.get("worked_example")
        if not example:
            gaps["skills without a worked example"].append(sid)
        else:
            for number, step in enumerate(example.get("steps", []), 1):
                if not step.get("why"):
                    gaps["worked-example steps without 'why this step?' choices"].append(f"{sid} step {number}")
        if not skill.get("faded_examples"):
            gaps["skills without faded examples"].append(sid)
        count = len(skill.get("questions", []))
        if count == 0:
            gaps["skills without questions"].append(sid)
        elif count < min_questions:
            gaps[f"skills with fewer than {min_questions} questions"].append(f"{sid} ({count})")
    for lesson in data["units"]:
        if not lesson.get("quiz"):
            gaps["lessons without a quiz"].append(lesson["id"])
    for mid, mistake in data["mistakes"].items():
        if not mistake.get("back"):
            gaps["mistakes without a skill to go back to"].append(mid)
    return gaps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-questions", type=int, default=MIN_QUESTIONS)
    args = parser.parse_args(argv)
    gaps = find_gaps(load_bank().data, args.min_questions)
    for title, items in gaps.items():
        print(f"{title}: {len(items)}")
        if 0 < len(items) <= 30:
            print("  " + ", ".join(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
