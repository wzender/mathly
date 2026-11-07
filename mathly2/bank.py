"""The exercise bank: lessons (units), skills, questions and mistakes. Loaded once and checked on start-up."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BANK_PATH = Path(__file__).parent / "content" / "math_algebra9.json"


class BankError(RuntimeError):
    """The bank is broken; the message lists every problem found."""


def check_bank(data: dict) -> list[str]:
    """Every problem found in a bank, as short messages. An empty list means the bank is sound."""
    problems: list[str] = []
    for key in ("units", "skills", "mistakes"):
        if key not in data:
            return [f"missing '{key}'"]

    def duplicates(kind: str, ids: list[str]) -> None:
        seen: set[str] = set()
        for item in ids:
            if item in seen:
                problems.append(f"duplicate {kind} id '{item}'")
            seen.add(item)

    unit_ids = [u.get("id") for u in data["units"]]
    skill_ids = [s.get("id") for s in data["skills"]]
    duplicates("lesson", unit_ids)
    duplicates("skill", skill_ids)
    units, skills, mistakes = set(unit_ids), set(skill_ids), data["mistakes"]

    for unit in data["units"]:
        for number, question in enumerate((unit.get("quiz") or {}).get("questions", []), 1):
            for skill in question.get("skills", []):
                if skill not in skills:
                    problems.append(f"lesson '{unit['id']}' quiz question {number}: unknown skill '{skill}'")

    for skill in data["skills"]:
        sid = skill["id"]
        if skill.get("unit") not in units:
            problems.append(f"skill '{sid}': unknown lesson '{skill.get('unit')}'")
        for pre in skill.get("prereqs", []):
            if pre not in skills:
                problems.append(f"skill '{sid}': unknown prerequisite '{pre}'")
        for number, question in enumerate(skill.get("questions", []), 1):
            where = f"skill '{sid}' question {number}"
            choices = question.get("choices", [])
            if len(choices) < 2:
                problems.append(f"{where}: fewer than 2 choices")
            right = sum(1 for c in choices if c.get("correct"))
            if right != 1:
                problems.append(f"{where}: {right} correct choices, expected 1")
            for choice in choices:
                mistake = choice.get("mistake")
                if mistake is not None and mistake not in mistakes:
                    problems.append(f"{where}: unknown mistake '{mistake}'")

    for mid, mistake in mistakes.items():
        # `back` is filled in for only some mistakes today (see scripts/content_gaps.py); check it when given.
        back = mistake.get("back")
        if back and back not in skills:
            problems.append(f"mistake '{mid}': unknown skill to go back to '{back}'")
    return problems


@dataclass(frozen=True)
class Bank:
    data: dict

    @property
    def lessons(self) -> list[dict]:
        return self.data["units"]

    @property
    def skills(self) -> list[dict]:
        return self.data["skills"]

    @property
    def mistakes(self) -> dict:
        return self.data["mistakes"]

    def lessons_with_skills(self) -> list[dict]:
        """Lessons with their skills, without any questions (those are served by later endpoints,
        which hide which choice is correct)."""
        by_lesson: dict[str, list[dict]] = {}
        for skill in self.skills:
            by_lesson.setdefault(skill["unit"], []).append({
                "id": skill["id"], "name": skill["name"], "short": skill.get("short", skill["name"]),
                "description": skill.get("description", ""), "prereqs": skill.get("prereqs", []),
                "month": skill.get("month", ""),
            })
        return [{
            "id": lesson["id"], "name": lesson["name"], "when": lesson.get("when", ""),
            "has_quiz": bool(lesson.get("quiz")), "skills": by_lesson.get(lesson["id"], []),
        } for lesson in self.lessons]


def load_bank(path: Path = BANK_PATH) -> Bank:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = check_bank(data)
    if problems:
        shown = "\n  - ".join(problems[:20])
        more = f"\n  … and {len(problems) - 20} more" if len(problems) > 20 else ""
        raise BankError(f"The exercise bank {path} has {len(problems)} problem(s):\n  - {shown}{more}")
    return Bank(data)
