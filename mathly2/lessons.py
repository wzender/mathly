"""Lesson documents kept in the database (add-subjects-and-worksheets): giving their parts ids, and the checks before publishing.

The document's shape is described in bank.py. The editor, the JSON load and the AI's draft may hand in skills and mistakes without
ids, or with temporary ones; `assign_ids` gives each a server-made id `w<lesson>_<k>` / `w<lesson>_m<k>` from counters kept in
the document that only grow, so an id is never reused after a delete and a reorder changes none.
"""
from __future__ import annotations

import copy
import re

from .bank import lesson_unit_id


def _counter(document: dict, key: str, used: list[int]) -> int:
    return max([int(document.get(key) or 1)] + [n + 1 for n in used])


def assign_ids(document: dict, lesson_id: int) -> dict:
    """A copy of the document in which every skill and mistake has an id of this lesson, choices point at the renamed mistakes,
    and the counters are past every id used."""
    doc = copy.deepcopy(document)
    prefix = lesson_unit_id(lesson_id)
    skill_id, mistake_id = re.compile(rf"^{prefix}_(\d+)$"), re.compile(rf"^{prefix}_m(\d+)$")
    skills = doc.get("skills") if isinstance(doc.get("skills"), list) else []
    mistakes = doc.get("mistakes") if isinstance(doc.get("mistakes"), dict) else {}

    next_skill = _counter(doc, "next_skill", [int(m.group(1)) for s in skills if isinstance(s, dict) for m in [skill_id.match(str(s.get("id", "")))] if m])
    for skill in skills:
        if isinstance(skill, dict) and not skill_id.match(str(skill.get("id", ""))):
            skill["id"] = f"{prefix}_{next_skill}"
            next_skill += 1

    next_mistake = _counter(doc, "next_mistake", [int(m.group(1)) for k in mistakes for m in [mistake_id.match(k)] if m])
    renamed: dict[str, str] = {}
    for key in list(mistakes):
        if not mistake_id.match(key):
            renamed[key] = f"{prefix}_m{next_mistake}"
            next_mistake += 1
    doc["mistakes"] = {renamed.get(k, k): v for k, v in mistakes.items()}
    for skill in skills:
        for question in (skill.get("questions") or []) if isinstance(skill, dict) else []:
            for choice in question.get("choices") or [] if isinstance(question, dict) else []:
                if isinstance(choice, dict) and choice.get("mistake") in renamed:
                    choice["mistake"] = renamed[choice["mistake"]]
    doc["skills"], doc["next_skill"], doc["next_mistake"] = skills, next_skill, next_mistake
    return doc


MIN_QUESTIONS = 5               # questions a skill needs before its lesson can be published


def publish_problems(document: dict, lesson_id: int) -> list[str]:
    """Every reason the draft cannot be published yet, in words and with where it is: a name, at least one skill, at least
    MIN_QUESTIONS questions per skill, exactly one right choice per question, and for every wrong choice a mistake with a name
    and a tip. Then the bank's own checks (bank.lesson_problems), so a published lesson always loads."""
    from .bank import lesson_problems
    problems: list[str] = []
    if not str(document.get("name") or "").strip():
        problems.append("לשיעור אין שם")
    skills, mistakes = document.get("skills") or [], document.get("mistakes") or {}
    if not skills:
        problems.append("אין בשיעור אף מיומנות")
    for si, skill in enumerate(skills, 1):
        where = f"מיומנות {si}"
        if not str(skill.get("name") or "").strip():
            problems.append(f"{where}: אין שם")
        questions = skill.get("questions") or []
        if len(questions) < MIN_QUESTIONS:
            problems.append(f"{where}: יש {len(questions)} שאלות, צריך לפחות {MIN_QUESTIONS}")
        for qi, question in enumerate(questions, 1):
            at = f"{where}, שאלה {qi}"
            if not str(question.get("question") or "").strip():
                problems.append(f"{at}: אין נוסח")
            choices = question.get("choices") or []
            right = sum(1 for c in choices if c.get("correct"))
            if right != 1:
                problems.append(f"{at}: צריכה תשובה נכונה אחת בדיוק (יש {right})")
            if len(choices) < 2:
                problems.append(f"{at}: צריך לפחות שתי תשובות")
            for ci, choice in enumerate(choices, 1):
                if not str(choice.get("text") or "").strip():
                    problems.append(f"{at}, תשובה {ci}: אין טקסט")
                if choice.get("correct"):
                    continue
                mistake = mistakes.get(choice.get("mistake") or "")
                if not mistake:
                    problems.append(f"{at}, תשובה {ci}: לתשובה השגויה אין טעות")
                elif not str(mistake.get("name") or "").strip() or not str(mistake.get("tip") or "").strip():
                    problems.append(f"{at}, תשובה {ci}: לטעות שהיא מראה חסר שם או טיפ")
    if not problems:
        problems += lesson_problems(document, lesson_id)
    return problems
