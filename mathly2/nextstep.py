"""The next step on home (הצעד הבא): one exercise to do now and why it moves the student forward, in the first, most effective way:

0. A round already open: finish it.
1. A crown one right answer away: a skill whose next right answer today masters it (mastery: 3 right in a row on 2 or more days).
2. A lesson behind the curriculum: catch up on the earliest one.
3. A test within two weeks: the weakest lesson of its material (the lowest chance of a right answer, forecast.py).
4. A test further away: the lesson whose good round raises the forecast the most (toward the next league).
5. Otherwise, the map's next lesson.

It carries data only (ids, names, numbers); the screen words it. Each step says how long it takes, how many questions, and whether it
completes today's goal."""
from __future__ import annotations

from datetime import date

from . import forecast
from .learning import MASTERY_DAYS, MASTERY_RUN

CLOSE_DAYS = 14                # a test this close: the weakest topic first
ROUND_MINUTES, ROUND_QUESTIONS = 5, 10


def one_answer_from_crown(recent: list[dict], today: date) -> list[str]:
    """Skills whose next right answer, given today, masters them: the last MASTERY_RUN - 1 counted answers are right and, with today,
    fall on MASTERY_DAYS days or more. `recent`: the store's recent answers, newest first."""
    runs: dict[str, list[dict]] = {}
    for a in recent:
        if a.get("counted", True):
            runs.setdefault(a["skill_id"], []).append(a)
    ready = []
    for skill, rows in runs.items():
        last = rows[:MASTERY_RUN - 1]
        if len(last) == MASTERY_RUN - 1 and all(a["correct"] for a in last) and len({a["day"] for a in last} | {today}) >= MASTERY_DAYS:
            ready.append(skill)
    return ready


def choose(*, bank, lessons: list[dict], next_lesson: str | None, states: dict[str, str], recent: list[dict], today: date,
           daily: dict, test: dict | None = None, test_facts: dict | None = None, test_answers: dict | None = None,
           faded: set[str] | None = None) -> dict | None:
    """`lessons`: the home map's rows (id, name, behind, due_date) in order. `test`: the nearest test's card (or None), with its facts
    (covered skills and states) and the answers per skill as the forecast reads them."""
    shown = [l["id"] for l in lessons]
    unit_of = {s["id"]: s["unit"] for s in bank.skills}
    name_of = {l["id"]: l["name"] for l in lessons}
    left_today = max(0, daily.get("goal", 0) - daily.get("done", 0))

    def lesson_ref(lesson_id):
        return {"id": lesson_id, "name": name_of.get(lesson_id, "")}

    def step(kind, href, questions, minutes, **data):
        return {"kind": kind, "href": href, "questions": questions, "minutes": minutes,
                "completes_goal": 0 < left_today <= questions, "test": bool(test), **data}

    # 0. a round already open
    started = next((l for l in lessons if l.get("round_open")), None)
    if started:
        return step("continue", f"#/round/{started['id']}", ROUND_QUESTIONS, ROUND_MINUTES, lesson=lesson_ref(started["id"]))

    # 1. one right answer from a crown (the test's material first)
    covered = set(test_facts["covered"]) if test_facts else set()
    crowns = [s for s in one_answer_from_crown(recent, today)
              if states.get(s) != "mastered" and unit_of.get(s) in shown]
    if crowns:
        crowns.sort(key=lambda s: (s not in covered, shown.index(unit_of[s])))
        skill = bank.skill(crowns[0])
        return step("crown", f"#/skill/{skill['id']}", 1, 2, skill={"id": skill["id"], "name": skill["name"]}, lesson=lesson_ref(unit_of[skill["id"]]))

    # 2. a lesson behind the curriculum
    behind = sorted((l for l in lessons if l.get("behind")), key=lambda l: (l["due_date"] or "", shown.index(l["id"])))
    if behind:
        l = behind[0]
        return step("behind", f"#/round/{l['id']}", ROUND_QUESTIONS, ROUND_MINUTES, lesson=lesson_ref(l["id"]), due_date=l["due_date"])

    # 3-4. the nearest test's material
    if test and test_facts and test_facts["covered"]:
        skills, f_states, answers = test_facts["covered"], test_facts["states"], test_answers or {}
        by_lesson: dict[str, list[str]] = {}
        for s in skills:
            if unit_of.get(s) in shown:
                by_lesson.setdefault(unit_of[s], []).append(s)
        if by_lesson:
            p = forecast.chances(skills, f_states, faded or set(), answers)
            if test["days_left"] <= CLOSE_DAYS:
                weakest = min(by_lesson, key=lambda lid: (sum(p[s] for s in by_lesson[lid]) / len(by_lesson[lid]), shown.index(lid)))
                share = round(test["questions"] * len(by_lesson[weakest]) / len(skills))
                return step("test", f"#/round/{weakest}", ROUND_QUESTIONS, ROUND_MINUTES, lesson=lesson_ref(weakest),
                            days_left=test["days_left"], date=test["date"], in_test=max(1, share))
            gains = {lid: forecast.gain_of_round(skills, f_states, faded or set(), answers, by_lesson[lid], ROUND_QUESTIONS) for lid in by_lesson}
            best = max(by_lesson, key=lambda lid: (gains[lid], -shown.index(lid)))
            if gains[best] > 0:
                return step("league", f"#/round/{best}", ROUND_QUESTIONS, ROUND_MINUTES, lesson=lesson_ref(best), gain=gains[best])

    # 5. the next lesson
    if next_lesson:
        stars = next((l.get("stars", 0) for l in lessons if l["id"] == next_lesson), 0)
        return step("next", f"#/round/{next_lesson}", ROUND_QUESTIONS, ROUND_MINUTES, lesson=lesson_ref(next_lesson), stars=stars)
    return None
