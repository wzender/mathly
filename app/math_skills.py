"""The 9th-grade algebra skill graph for the math path (`math_algebra9.json`).

Each skill names its prerequisites and a sample question. Choice samples identify mistakes;
open-ended samples name their type and revision and accept a photographed answer.
A mistake sends the student back to the skill it comes from (`back`), or keeps them on the same skill (`null`).
The graph follows the Ministry of Education's 9th-grade teaching schedule (2026/27) and the summer review for
students placed in 5 units; `core` marks what that review stresses. The questions are written for the app, and
every skill, link and mistake still needs a 5-unit teacher's review.

`problems` is run by the tests and on loading: a broken graph is refused before a student meets it.
"""
from __future__ import annotations

import json
import hashlib
import copy
from functools import cache
from pathlib import Path

GRAPH = Path(__file__).with_name("math_algebra9.json")


def question_version(sample: dict) -> str:
    """Bind attempts to the complete prompt, including its diagram and revision."""
    return hashlib.sha256(json.dumps(sample, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def problems(graph: dict) -> list[str]:
    """What is wrong with a graph: unknown units, skills or mistakes, a cycle, a link implied by another,
    a question without exactly one right answer, or a mistake that sends the student to a skill that is not before it."""
    units = {u["id"] for u in graph["units"]}
    skills = {s["id"]: s for s in graph["skills"]}
    mistakes = graph["mistakes"]
    out = [f"{s['id']}: unknown unit {s['unit']}" for s in skills.values() if s["unit"] not in units]
    out += [f"{s['id']}: unknown prerequisite {p}" for s in skills.values() for p in s["prereqs"] if p not in skills]
    if out:
        return out
    below: dict[str, set[str]] = {}

    def ancestors(sid: str, path: tuple[str, ...] = ()) -> set[str]:
        if sid in path:
            raise ValueError(" -> ".join(path + (sid,)))
        if sid not in below:
            below[sid] = {a for p in skills[sid]["prereqs"] for a in (p, *ancestors(p, path + (sid,)))}
        return below[sid]

    try:
        for sid in skills:
            ancestors(sid)
    except ValueError as cycle:
        return [f"cycle: {cycle}"]
    for s in skills.values():
        out += [f"{s['id']}: {p} is implied by {q}" for p in s["prereqs"] for q in s["prereqs"] if p != q and p in below[q]]
        sample = s["sample"]
        kind = sample.get("type", "multiple-choice")
        if kind not in ("open-ended", "multiple-choice"):
            out.append(f"{s['id']}: unknown question type {kind}")
            continue
        if kind == "open-ended":
            if "choices" in sample:
                out.append(f"{s['id']}: open-ended questions cannot have choices")
            if not isinstance(sample.get("question"), str) or not sample["question"].strip():
                out.append(f"{s['id']}: question text is required")
            if type(sample.get("version")) is not int or sample["version"] < 1:
                out.append(f"{s['id']}: positive question version is required")
            continue
        choices = sample.get("choices", [])
        if sum(bool(c.get("correct")) for c in choices) != 1:
            out.append(f"{s['id']}: needs exactly one correct choice")
        if len({c["text"] for c in choices}) != len(choices):
            out.append(f"{s['id']}: two choices read the same")
        for c in choices:
            m = c.get("mistake")
            if c.get("correct"):
                continue
            if m not in mistakes:
                out.append(f"{s['id']}: unknown mistake {m}")
            elif (back := mistakes[m]["back"]) and back != s["id"] and back not in below[s["id"]]:
                out.append(f"{s['id']}: mistake {m} sends back to {back}, which is not before it")
    out += [f"mistake {k}: unknown skill {m['back']}" for k, m in mistakes.items() if m["back"] and m["back"] not in skills]
    return out


@cache
def algebra9() -> dict:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    if found := problems(graph):
        raise ValueError(f"{GRAPH.name}: " + "; ".join(found))
    return graph


def practice_graph(answer_scans_enabled: bool) -> dict:
    """Keep practice usable during a scan rollout or rollback.

    Public responses never expose fallback choices for an open-ended question.
    The original choice sample is served when authenticated storage is disabled.
    """
    graph = copy.deepcopy(algebra9())
    for skill in graph["skills"]:
        fallback = skill.pop("fallback_sample", None)
        if not answer_scans_enabled and fallback is not None:
            skill["sample"] = fallback
        skill["question_version"] = question_version(skill["sample"])
    return graph
