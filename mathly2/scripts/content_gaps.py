"""List the content the bank still lacks.   venv/bin/python -m mathly2.scripts.content_gaps [--min-questions N]

A skill needs: a solved example for the help button, and enough questions for "a different question" (practice, quizzes and tests
draw from them). Mistakes should say which skill to go back to. Lesson quizzes need no authored content: they are drawn from
the questions."""
from __future__ import annotations

import argparse
import sys

from mathly2.bank import load_bank

MIN_QUESTIONS = 10


def find_gaps(data: dict, min_questions: int = MIN_QUESTIONS) -> dict[str, list[str]]:
    gaps: dict[str, list[str]] = {
        "skills without a solved example": [],
        "skills without questions": [],
        f"skills with fewer than {min_questions} questions": [],
        "mistakes without a skill to go back to": [],
    }
    for skill in data["skills"]:
        sid = skill["id"]
        if not skill.get("worked_example"):
            gaps["skills without a solved example"].append(sid)
        count = len(skill.get("questions", []))
        if count == 0:
            gaps["skills without questions"].append(sid)
        elif count < min_questions:
            gaps[f"skills with fewer than {min_questions} questions"].append(f"{sid} ({count})")
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
