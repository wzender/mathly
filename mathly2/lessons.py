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
