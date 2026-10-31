"""The 9th-grade algebra skill graph for the math path (`math_algebra9.json`).

Each skill names its prerequisites and either one `sample` question or a list of multiple-choice `questions`.
Choice samples identify mistakes; open-ended samples name their type and revision and accept a photographed answer.
A mistake sends the student back to the skill it comes from (`back`), or keeps them on the same skill (`null`).
The units follow the Ministry of Education's 9th-grade teaching schedule for 2026/27 (`docs/prisa_9A.md`).
Units already split by the schedule's topics (טכניקה אלגברית, פונקציה ריבועית) have ten questions per skill;
the other units still have ten skills with one question each. `month` is when the schedule teaches a skill.
The questions are written for the app, and every skill, link and mistake still needs a teacher's review.

`problems` is run by the tests and on loading: a broken graph is refused before a student meets it.
"""
from __future__ import annotations

import json
import re
import hashlib
import copy
from functools import cache
from pathlib import Path

GRAPH = Path(__file__).with_name("math_algebra9.json")


def question_version(sample: dict) -> str:
    """Bind attempts to the complete prompt, including its diagram and revision."""
    return hashlib.sha256(json.dumps(sample, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def questions(skill: dict) -> list[dict]:
    """A skill's questions: its list of questions, or its one sample."""
    return skill["questions"] if "questions" in skill else [skill["sample"]]


FIGURE_POINT = re.compile(r"([A-Za-z_][\w']*)=(-?[\d.]+),(-?[\d.]+)(?:@(n|s|e|w|ne|nw|se|sw))?")
FIGURE_NAMES = {"poly": None, "line": 2, "dash": 2, "dot": None, "len": 2, "lenx": 2, "ang": 3, "ang2": 3, "ang3": 3,
                "right": 3, "tick": 2, "par": 2}   # how many point names an operation starts with (None: all of them)


def figure_problems(where: str, figure) -> list[str]:
    """A figure (drawn by `figure` in static/math.js) may only name points it places and operations it knows."""
    if not isinstance(figure, str) or not figure.strip():
        return [f"{where}: figure must be text"]
    points, out = set(), []
    statements = [s.strip() for s in figure.split(";") if s.strip()]
    for st in statements:
        if m := FIGURE_POINT.fullmatch(st):
            points.add(m[1])
    for st in statements:
        if FIGURE_POINT.fullmatch(st) or st == "grid":
            continue
        op, *args = st.split()
        if op == "note":
            if not args:
                out.append(f"{where}: figure note needs words")
            continue
        if op == "text":
            if not args or not re.fullmatch(r"-?[\d.]+,-?[\d.]+", args[0]) or len(args) < 2:
                out.append(f"{where}: figure text needs x,y and words: {st}")
            continue
        if op not in FIGURE_NAMES:
            out.append(f"{where}: unknown figure operation {op}")
            continue
        names = args if FIGURE_NAMES[op] is None else args[:FIGURE_NAMES[op]]
        if len(names) < (FIGURE_NAMES[op] or 1):
            out.append(f"{where}: figure {op} needs more points: {st}")
        out += [f"{where}: figure names unknown point {n}" for n in names if n not in points]
        if op in ("tick", "par") and len(args) > 2 and not args[2].isdigit():
            out.append(f"{where}: figure {op} count must be a number: {st}")
    if not points:
        out.append(f"{where}: figure has no points")
    return out


def sample_problems(where: str, sid: str, sample: dict, listed: bool, mistakes: dict, below: dict) -> list[str]:
    if "figure" in sample and (bad := figure_problems(where, sample["figure"])):
        return bad
    kind = sample.get("type", "multiple-choice")
    if kind not in ("open-ended", "multiple-choice"):
        return [f"{where}: unknown question type {kind}"]
    if kind == "open-ended":
        if listed:
            return [f"{where}: a question list holds multiple-choice questions only"]
        out = []
        if "choices" in sample:
            out.append(f"{where}: open-ended questions cannot have choices")
        if not isinstance(sample.get("question"), str) or not sample["question"].strip():
            out.append(f"{where}: question text is required")
        if type(sample.get("version")) is not int or sample["version"] < 1:
            out.append(f"{where}: positive question version is required")
        return out
    out = []
    choices = sample.get("choices", [])
    if sum(bool(c.get("correct")) for c in choices) != 1:
        out.append(f"{where}: needs exactly one correct choice")
    if len({c["text"] for c in choices}) != len(choices):
        out.append(f"{where}: two choices read the same")
    for c in choices:
        m = c.get("mistake")
        if c.get("correct"):
            continue
        if m not in mistakes:
            out.append(f"{where}: unknown mistake {m}")
        elif (back := mistakes[m]["back"]) and back != sid and back not in below[sid]:
            out.append(f"{where}: mistake {m} sends back to {back}, which is not before it")
    return out


def problems(graph: dict) -> list[str]:
    """What is wrong with a graph: unknown units, skills or mistakes, a cycle, a link implied by another,
    a question without exactly one right answer, or a mistake that sends the student to a skill that is not before it."""
    units = {u["id"] for u in graph["units"]}
    skills = {s["id"]: s for s in graph["skills"]}
    mistakes = graph["mistakes"]
    out = [f"{u['id']}: subject is required" for u in graph["units"] if not str(u.get("subject") or "").strip()]
    out += [f"{s['id']}: unknown unit {s['unit']}" for s in skills.values() if s["unit"] not in units]
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
        if ("questions" in s) == ("sample" in s):
            out.append(f"{s['id']}: needs a sample or a list of questions, not both")
            continue
        listed = "questions" in s
        if listed and (not isinstance(s["questions"], list) or not s["questions"]):
            out.append(f"{s['id']}: the question list is empty")
            continue
        for n, sample in enumerate(questions(s), 1):
            out += sample_problems(f"{s['id']} question {n}" if listed else s["id"], s["id"], sample, listed,
                                   mistakes, below)
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
    subject = {unit["id"]: unit["subject"] for unit in graph["units"]}
    for skill in graph["skills"]:
        skill["subject"] = subject[skill["unit"]]   # a subunit belongs to its unit's subject
        fallback = skill.pop("fallback_sample", None)
        if not answer_scans_enabled and fallback is not None:
            skill["sample"] = fallback
        if "sample" in skill:   # identifies an open-ended question's uploaded answers
            skill["question_version"] = question_version(skill["sample"])
    return graph
