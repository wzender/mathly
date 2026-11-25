"""The forecast grade (הציון הצפוי) for a real test: "if the test were today, what would I get?", from everything the student did on the
test's skills. It moves after every activity (a round, practice, a quiz, a practice test, the simulation), up after right answers and down
after wrong ones, honestly.

Each skill of the test gets a chance of answering a question on it right. It starts from the skill's state (not started 30%, learning 50%,
mastered 85%, held like a few answers' worth) and moves with the student's latest answers on it: the newest weigh most, and answers in a
practice test or the simulation weigh double (they are closest to the real test). A mastered skill does not fall below 75%; a faded one
(not answered for a while) loses a tenth. The forecast grade is the mean chance over the test's skills, as the test draws its questions
evenly over them. With few answers it is a guess, so it comes with a range that narrows as the student practises."""
from __future__ import annotations

from math import sqrt

PRIOR = {"not_started": (0.30, 2.0), "learning": (0.50, 2.0), "mastered": (0.85, 4.0)}   # state -> (chance, how many answers it is worth)
DECAY = 0.85                     # each older answer on a skill weighs this much of the one after it
LAST = 12                        # answers per skill that count
TEST_WEIGHT = 2.0                # an answer in a practice test or the simulation
MASTERED_FLOOR = 0.75
FADED = 0.9
WIDEST, NARROWEST = 25, 3        # the range's half-width with no answers, and at the least

# What the student sees (the teacher sees the numbers): until PLACEMENT answers on the test's material, "finding your league" with a bar
# that only fills ("placement matches", as in competitive games); then a league with the points to the next one. A league is never left
# for a dip of less than KEEP points below its floor (the screens remember the league last shown).
PLACEMENT = 15
LEAGUES = [{"at": 0, "name": "ירח", "icon": "🌙"}, {"at": 55, "name": "כוכב לכת", "icon": "🪐"},
           {"at": 70, "name": "כוכב", "icon": "⭐"}, {"at": 85, "name": "גלקסיה", "icon": "🌌"}]
KEEP = 3


def league_of(grade: int) -> int:
    return max(i for i, league in enumerate(LEAGUES) if grade >= league["at"])


def skill_chance(state: str, faded: bool, answers: list[tuple[bool, float]]) -> float:
    """`answers`: the skill's latest answers, newest first, as (right, weight)."""
    chance, strength = PRIOR.get(state, PRIOR["not_started"])
    right, total = chance * strength, strength
    for i, (ok, weight) in enumerate(answers[:LAST]):
        w = weight * DECAY ** i
        right += w * (1.0 if ok else 0.0)
        total += w
    p = right / total
    if state == "mastered":
        p = max(p, MASTERED_FLOOR)
    return p * FADED if faded else p


def compute(skills: list[str], states: dict[str, str], faded: set[str], answers: dict[str, list[tuple[bool, float]]]) -> dict | None:
    """The forecast for a test on `skills`: {"grade", "low", "high", "answers"} (the range, and how many answers it rests on), or None
    for a test with no skills."""
    if not skills:
        return None
    chances = [skill_chance(states.get(s, "not_started"), s in faded, answers.get(s, [])) for s in skills]
    grade = round(100 * sum(chances) / len(chances))
    count = sum(min(len(answers.get(s, [])), LAST) for s in skills)
    half = max(NARROWEST, round(WIDEST / sqrt(1 + count / 5)))
    return {"grade": grade, "low": max(0, grade - half), "high": min(100, grade + half), "answers": count,
            "placement": {"done": count, "need": PLACEMENT} if count < PLACEMENT else None,
            "league": league_of(grade), "leagues": LEAGUES, "keep": KEEP}


def answers_by_skill(recent: list[dict], tests: list[tuple[str, bool]]) -> dict[str, list[tuple[bool, float]]]:
    """The answers per skill, newest first: the handed-in practice tests' and simulations' answers (`tests`: (skill, right), newest
    first) before the practice and round answers (`recent`: the store's recent answers, newest first; helped ones do not count)."""
    out: dict[str, list[tuple[bool, float]]] = {}
    for skill, ok in tests:
        out.setdefault(skill, []).append((ok, TEST_WEIGHT))
    for a in recent:
        if a.get("counted", True):
            out.setdefault(a["skill_id"], []).append((bool(a["correct"]), 1.0))
    return out


def chances(skills: list[str], states: dict[str, str], faded: set[str], answers: dict[str, list[tuple[bool, float]]]) -> dict[str, float]:
    """Each skill's chance of a right answer (as in compute)."""
    return {s: skill_chance(states.get(s, "not_started"), s in faded, answers.get(s, [])) for s in skills}


def boost(skills: list[str], states: dict[str, str], faded: set[str], answers: dict[str, list[tuple[bool, float]]],
          groups: dict[str, list[str]], rounds: int = 3, size: int = 10) -> dict:
    """Where good rounds take the forecast: `rounds` times, the group of skills (a lesson) whose good round adds the most, each counted after
    the ones before. {"gains": [points of each round], "grade": the grade after them}. What home shows beside the grade, so a low grade
    always comes with the way up."""
    now = {s: list(v) for s, v in answers.items()}
    grade = compute(skills, states, faded, now)["grade"] if skills else 0
    gains = []
    for _ in range(rounds):
        if not groups:
            break
        best = max(groups, key=lambda g: gain_of_round(skills, states, faded, now, groups[g], size))
        gain = gain_of_round(skills, states, faded, now, groups[best], size)
        if gain <= 0:
            break
        for i in range(size):
            s = groups[best][i % len(groups[best])]
            now[s] = [(True, 1.0)] + now.get(s, [])
        gains.append(gain)
        grade += gain
    return {"gains": gains, "grade": min(100, grade)}


def gain_of_round(skills: list[str], states: dict[str, str], faded: set[str], answers: dict[str, list[tuple[bool, float]]],
                  round_skills: list[str], size: int = 10) -> int:
    """How many points a good round (`size` right answers spread over `round_skills`) would add to the forecast grade."""
    if not skills or not round_skills:
        return 0
    before = compute(skills, states, faded, answers)["grade"]
    after = {s: list(v) for s, v in answers.items()}
    for i in range(size):
        s = round_skills[i % len(round_skills)]
        after[s] = [(True, 1.0)] + after.get(s, [])
    return compute(skills, states, faded, after)["grade"] - before
