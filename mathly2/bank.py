"""The exercise bank: lessons (units), skills, questions and mistakes. Loaded once and checked on start-up."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

BANK_PATH = Path(__file__).parent / "content" / "math_algebra9.json"


class BankError(RuntimeError):
    """The bank is broken; the message lists every problem found."""


PRACTICE_QUESTIONS = 10   # practice shows "question n of N" with N at most this, whatever the skill has in the bank


def question_key(skill_id: str, question: dict) -> str:
    """A stable id for a question: the skill plus a hash of the question's content.
    Reordering or adding questions keeps every key; editing a question gives it a new one."""
    canonical = json.dumps(question, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{skill_id}:{hashlib.sha1(canonical.encode('utf-8')).hexdigest()[:10]}"


def _one_correct(choices: list, where: str, mistakes: dict, problems: list[str]) -> None:
    if not isinstance(choices, list) or len(choices) < 2:
        problems.append(f"{where}: fewer than 2 choices")
        return
    right = sum(1 for c in choices if c.get("correct"))
    if right != 1:
        problems.append(f"{where}: {right} correct choices, expected 1")
    for choice in choices:
        mistake = choice.get("mistake")
        if mistake is not None and mistake not in mistakes:
            problems.append(f"{where}: unknown mistake '{mistake}'")


def example_problems(skill: dict, mistakes: dict) -> list[str]:
    """What is wrong with a skill's solved example (the same checks the bank is loaded with)."""
    problems: list[str] = []
    _check_example(skill, problems)
    return problems


def _check_example(skill: dict, problems: list[str]) -> None:
    """The help button's solved example is optional; when present it is one question solved in steps, each with what is done
    and why, and an answer. It is plain text: nothing is chosen. (`faded_examples` from an earlier plan is not read.)"""
    example = skill.get("worked_example")
    if example is None:
        return
    where = f"skill '{skill['id']}' solved example"
    steps = example.get("steps") or []
    if not example.get("question") or not steps or not example.get("answer"):
        problems.append(f"{where}: needs a question, steps and an answer")
    for number, step in enumerate(steps, 1):
        if not step.get("do"):
            problems.append(f"{where} step {number}: no 'do'")
        if not isinstance(step.get("why"), str) or not step["why"].strip():
            problems.append(f"{where} step {number}: 'why' must be text")


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
        keys: set[str] = set()
        for number, question in enumerate(skill.get("questions", []), 1):
            where = f"skill '{sid}' question {number}"
            _one_correct(question.get("choices", []), where, mistakes, problems)
            key = question_key(sid, question)
            if key in keys:
                problems.append(f"{where}: identical to an earlier question of the skill")
            keys.add(key)
        _check_example(skill, problems)

    for mid, mistake in mistakes.items():
        # `back` is filled in for only some mistakes today (see scripts/content_gaps.py); check it when given.
        back = mistake.get("back")
        if back and back not in skills:
            problems.append(f"mistake '{mid}': unknown skill to go back to '{back}'")
    return problems


# ---- lessons kept in the database (add-subjects-and-worksheets) ----
#
# A lesson row of m2_lessons holds a document per state (draft, published), one unit in this shape:
#   {"name": "...", "skills": [{"id": "w7_1", "name", "short", "description", "questions": [question, ...]}, ...],
#    "mistakes": {"w7_m1": {"name", "tip", "back"?}, ...}, "next_skill": 2, "next_mistake": 2}
# A question is as in the content file ({"question", "choices": [{"text", "correct"?: true, "mistake"?: id}]}) plus "source":
# "sheet", "ai" or "person", which the editor shows and the bank drops (so the label never changes a question's key).
# Ids are made by the server from the row's id and counters that only grow, so they never clash with the content file's ids
# or with each other, and deleting or moving a skill keeps every other id.

MATH = {"id": "math", "name": "מתמטיקה", "icon": "∑"}
QUESTION_FIELDS = ("question", "choices", "figure", "graph")


def lesson_unit_id(lesson_id: int) -> str:
    return f"w{lesson_id}"


def lesson_problems(document: dict, lesson_id: int) -> list[str]:
    """What is wrong with a lesson document as the bank would load it (its shape, its own ids, then the bank's own checks)."""
    if not isinstance(document, dict):
        return ["the lesson is not a document"]
    prefix, problems = lesson_unit_id(lesson_id), []
    if not str(document.get("name") or "").strip():
        problems.append("the lesson has no name")
    skills, mistakes = document.get("skills"), document.get("mistakes", {})
    if not isinstance(skills, list) or not isinstance(mistakes, dict):
        return problems + ["the lesson needs a list of skills and a set of mistakes"]
    for skill in skills:
        if not isinstance(skill, dict) or not str(skill.get("id", "")).startswith(prefix + "_") or not str(skill.get("name") or "").strip():
            problems.append(f"skill '{skill.get('id') if isinstance(skill, dict) else skill}': needs a name and an id of this lesson")
        elif not isinstance(skill.get("questions", []), list) or any(not isinstance(q, dict) or not str(q.get("question") or "").strip()
                                                                    for q in skill.get("questions", [])):
            problems.append(f"skill '{skill['id']}': every question needs its text")
    for mid, mistake in mistakes.items():
        if not mid.startswith(prefix + "_m") or not isinstance(mistake, dict) or not str(mistake.get("name") or "").strip():
            problems.append(f"mistake '{mid}': needs a name and an id of this lesson")
    if problems:
        return problems
    unit, unit_skills, unit_mistakes = lesson_unit(document, lesson_id, "x")
    return check_bank({"units": [unit], "skills": unit_skills, "mistakes": unit_mistakes})


def lesson_unit(document: dict, lesson_id: int, subject_id: str) -> tuple[dict, list[dict], dict]:
    """A lesson document as the bank's unit, skills and mistakes."""
    unit = {"id": lesson_unit_id(lesson_id), "subject_id": subject_id, "name": document["name"].strip()}
    skills = [{"id": s["id"], "unit": unit["id"], "name": s["name"].strip(), "short": (s.get("short") or s["name"]).strip(),
               "description": s.get("description", ""), "prereqs": [],
               "questions": [{k: q[k] for k in QUESTION_FIELDS if k in q} for q in s.get("questions", [])]}
              for s in document["skills"]]
    mistakes = {mid: {k: m[k] for k in ("name", "tip", "back") if m.get(k)} for mid, m in document.get("mistakes", {}).items()}
    return unit, skills, mistakes


def merge(data: dict, subjects: list[dict], lessons: list[dict], log=None) -> dict:
    """The content file's data with the published lessons added: math's file lessons first, then each subject's lessons in the
    subjects' order and the lessons' positions. A lesson that fails the checks is left out (and logged); the rest load."""
    merged = {**data, "units": [{**u, "subject_id": "math"} for u in data["units"]], "skills": list(data["skills"]),
              "mistakes": dict(data["mistakes"]), "subjects": [{k: s[k] for k in ("id", "name", "icon")} for s in subjects] or [MATH]}
    known = {s["id"] for s in merged["subjects"]}
    order = {s["id"]: i for i, s in enumerate(merged["subjects"])}
    for row in sorted(lessons, key=lambda r: (order.get(r["subject_id"], len(order)), r.get("position", 0), r["id"])):
        document = row.get("published")
        problems = ["its subject does not exist"] if row["subject_id"] not in known else lesson_problems(document, row["id"])
        if not problems:
            unit, skills, mistakes = lesson_unit(document, row["id"], row["subject_id"])
            backs = {m["back"] for m in mistakes.values() if m.get("back")} - {s["id"] for s in merged["skills"] + skills}
            problems = [f"mistake points back to unknown skill '{b}'" for b in sorted(backs)]
        if problems:
            if log:
                log(f"lesson {row['id']} left out of the bank: {'; '.join(problems[:5])}")
            continue
        merged["units"].append(unit)
        merged["skills"].extend(skills)
        merged["mistakes"].update(mistakes)
    return merged


@dataclass(frozen=True)
class Bank:
    data: dict

    @property
    def subjects(self) -> list[dict]:
        """The subjects in order, math first: [{"id", "name", "icon"}]."""
        return self.data.get("subjects") or [MATH]

    @cached_property
    def _subject_of_lesson(self) -> dict[str, str]:
        return {u["id"]: u.get("subject_id", "math") for u in self.lessons}

    def subject_of_lesson(self, lesson_id: str) -> str | None:
        return self._subject_of_lesson.get(lesson_id)

    def subject_of_skill(self, skill_id: str) -> str | None:
        skill = self.skill(skill_id)
        return self.subject_of_lesson(skill["unit"]) if skill else None

    def lessons_of_subject(self, subject_id: str) -> list[dict]:
        return [u for u in self.lessons if u.get("subject_id", "math") == subject_id]

    @property
    def lessons(self) -> list[dict]:
        return self.data["units"]

    @property
    def skills(self) -> list[dict]:
        return self.data["skills"]

    @property
    def mistakes(self) -> dict:
        return self.data["mistakes"]

    @cached_property
    def _skills_by_id(self) -> dict[str, dict]:
        return {s["id"]: s for s in self.skills}

    @cached_property
    def _questions(self) -> dict[str, dict[str, dict]]:
        """skill id -> question key -> question, in bank order."""
        return {s["id"]: {question_key(s["id"], q): q for q in s.get("questions", [])} for s in self.skills}

    def skill(self, skill_id: str) -> dict | None:
        return self._skills_by_id.get(skill_id)

    def question_keys(self, skill_id: str) -> list[str]:
        return list(self._questions.get(skill_id, {}))

    def practice_keys(self, skill_id: str) -> list[str]:
        """The questions practice on the exercise screen uses: the first PRACTICE_QUESTIONS of the skill. Quizzes and tests draw from all of them."""
        return self.question_keys(skill_id)[:PRACTICE_QUESTIONS]

    def practice_question(self, skill_id: str, key: str) -> dict | None:
        """A question as the browser may see it: no `correct` flag and no `mistake`, so nothing reveals the
        answer. Each choice keeps its position in the bank (`index`); the browser may shuffle the display."""
        question = self._questions.get(skill_id, {}).get(key)
        if question is None:
            return None
        served = {"key": key, "question": question["question"],
                  "choices": [{"index": i, "text": c["text"]} for i, c in enumerate(question["choices"])]}
        for extra in ("figure", "graph"):
            if extra in question:
                served[extra] = question[extra]
        return served

    def grade(self, skill_id: str, key: str, choice: int) -> dict | None:
        """{"correct": bool, "mistake": {"id","name","tip","back"} | None}, or None for an unknown question or choice.
        Never says which choice was right."""
        question = self._questions.get(skill_id, {}).get(key)
        if question is None or not isinstance(choice, int) or not 0 <= choice < len(question["choices"]):
            return None
        picked = question["choices"][choice]
        if picked.get("correct"):
            return {"correct": True, "mistake": None}
        return {"correct": False, "mistake": self.mistake(picked.get("mistake"))}

    def mistake(self, mistake_id: str | None) -> dict | None:
        found = self.mistakes.get(mistake_id) if mistake_id else None
        if not found:
            return None
        return {"id": mistake_id, "name": found["name"], "tip": found.get("tip", ""), "back": found.get("back") or None}

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
