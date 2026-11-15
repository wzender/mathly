"""The written simulation (written-simulation): no choices, the way on the board, a box for a plain-number answer, the AI's check as the
grade, the teacher's points as the last word, and nothing counted until it is checked."""
import json

import pytest

from mathly2 import attempts, boardreview, writtentest
from mathly2.tests.test_boardreview_api import FakeReviewer, make
from mathly2.tests.test_boardwork_api import KID, TEACHER, auth, send_work, uid


class Verdicts(FakeReviewer):
    """A fake AI that gives each question the next verdict of a list."""
    def __init__(self, verdicts, fail=None):
        super().__init__(fail)
        self.verdicts = list(verdicts)

    def review_one(self, item, on_event=lambda step, **info: None):
        self.calls.append(item)
        if self.fail:
            raise boardreview.ReviewFailure(self.fail)
        return {"verdict": self.verdicts.pop(0), "feedback": "משוב", "tip": "טיפ"}


def start(client, test):
    got = client.post(f"/api/tests/{test['id']}/simulation/start", headers=auth(KID))
    assert got.status_code == 200, got.text
    return got.json()


def write(client, sim, boards, typed=None):
    """A board on the first `boards` questions; `typed`: question index -> the typed final answer."""
    for i, q in enumerate(sim["questions"]):
        if typed and i in typed:
            assert client.put(f"/api/attempts/{sim['id']}/answers", headers=auth(KID), json={"key": q["key"], "final": typed[i]}).status_code == 200
        if i < boards:
            assert send_work(client, sim["id"], q["key"]).status_code == 201
    return client.post(f"/api/attempts/{sim['id']}/submit", headers=auth(KID)).json()


# ---- the plain-number answer ----

@pytest.mark.parametrize("text, label, unit, value", [("$5$", "", "", 5), ("$x = −10$", "x =", "", -10), ("$70°$", "", "°", 70),
                                                      ("$1/4$", "", "", 0.25), ("$0.3$", "", "", 0.3)])
def test_a_plain_number_answer_gets_a_box(text, label, unit, value):
    bank = type("B", (), {"practice_question": lambda self, s, k: {"choices": [{"index": 0, "text": text}]},
                          "grade": lambda self, s, k, i: {"correct": True}})()
    final = writtentest.final_of(bank, {"skill_id": "s", "key": "k"})
    assert final["label"] == label and final["unit"] == unit and float(final["value"]) == pytest.approx(value)


@pytest.mark.parametrize("text", ["$5$ ו־$8$", "$x² + 4x + 4$", "$(0, −5)$", "טרפז", "$x ≤ −3$ או $x ≥ 3$", "$AB = AC$"])
def test_anything_else_is_answered_on_the_board_only(text):
    bank = type("B", (), {"practice_question": lambda self, s, k: {"choices": [{"index": 0, "text": text}]},
                          "grade": lambda self, s, k, i: {"correct": True}})()
    assert writtentest.final_of(bank, {"skill_id": "s", "key": "k"}) is None


@pytest.mark.parametrize("typed, ok", [("5", True), ("5.0", True), ("10/2", True), ("x=5", True), ("x = 5", True), ("4", False), ("abc", False)])
def test_the_typed_answer_is_compared_as_a_number(typed, ok):
    from fractions import Fraction
    assert writtentest.matches(typed, {"label": "x =", "unit": "", "value": Fraction(5)}) is ok
    assert writtentest.matches("", {"label": "", "unit": "", "value": Fraction(5)}) is None


# ---- the open simulation ----

def test_the_simulation_has_no_choices_and_a_box_only_where_the_answer_is_a_number():
    client, store, bank, test, lessons = make(Verdicts([]))
    sim = start(client, test)
    assert sim["written"] is True and sim["questions"]
    assert all("choices" not in q for q in sim["questions"])
    for q, ref in zip(sim["questions"], store.get_attempt(sim["id"])["questions"]):
        assert (q["final"] is not None) == (writtentest.final_of(bank, ref) is not None)
    assert '"correct"' not in json.dumps(sim)
    key = sim["questions"][0]["key"]
    assert client.put(f"/api/attempts/{sim['id']}/answers", headers=auth(KID), json={"key": key, "choice": 0}).status_code == 422   # no choices here
    assert client.put(f"/api/attempts/{sim['id']}/answers", headers=auth(KID), json={"key": key, "final": " 12 "}).status_code == 200
    assert store.get_attempt(sim["id"])["answers"][key] == "12"


def test_after_handing_in_it_waits_for_the_check_and_the_ai_sets_the_grade():
    reviewer = Verdicts(["correct", "partial", "wrong"])
    client, store, bank, test, lessons = make(reviewer)
    sim = start(client, test)
    n = len(sim["questions"])
    done = write(client, sim, boards=3, typed={0: "7"})                       # three boards; the rest left empty
    assert done["state"] == "submitted" and done["written"] is True
    assert len(reviewer.calls) == 3 and all(c["written"] for c in reviewer.calls)
    first = reviewer.calls[0]
    assert first["typed"] == "7" and first["right"] and "choices" not in first   # the right answer goes to the AI only
    got = client.get(f"/api/attempts/{sim['id']}", headers=auth(KID)).json()
    assert got["checking"] is False and got["grade"] == attempts.percent(3, 2 * n)            # 1 + ½ points of n
    assert got["right"] == 1 and len(got["missed"]) == n - 1
    assert got["missed"][0]["points"] == 0.5 and got["missed"][-1]["no_work"] is True
    assert '"right"' not in json.dumps(got["missed"]) and first["right"] not in json.dumps(got, ensure_ascii=False)


def test_without_the_ai_it_waits_for_the_teacher_whose_points_are_final():
    client, store, bank, test, lessons = make(None)                           # no key: no AI check
    sim = start(client, test)
    done = write(client, sim, boards=2)
    assert done["checking"] is True and done["grade"] is None and done["readiness"] is None
    card = client.get(f"/api/tests/{test['id']}", headers=auth(KID)).json()
    assert card["simulation"]["taken"] == 1 and card["readiness"]["simulation_best"] is None and card["trail"][0]["checking"] is True
    assert client.get("/api/grades", headers=auth(KID)).json()["simulations"][0]["best"] is None
    assert client.post(f"/api/attempts/{sim['id']}/retry/start", headers=auth(KID)).status_code == 409   # nothing to retry before the check
    view = client.get(f"/api/teaching/work/{sim['id']}", headers=auth(TEACHER)).json()
    q0, q1, q2 = view["questions"][:3]
    assert q0["written"] and q0["right"] and q0["auto"] is None and q2["auto"] == 0       # a board waits for a check; no board is 0
    checked = client.post(f"/api/teaching/work/{sim['id']}", headers=auth(TEACHER), json={"credit": {q0["key"]: 1}}).json()
    n = len(view["questions"])
    assert checked["grade"] == (200 * 2 + 2 * n) // (4 * n)                              # 1 point; the unchecked board counts 0
    got = client.get(f"/api/attempts/{sim['id']}", headers=auth(KID)).json()
    assert got["checking"] is False and got["grade"] == checked["grade"] and got["readiness"] is not None
    review = {r["question_key"] for r in store.review_of(uid(KID))}
    assert q0["key"] not in review and {q1["key"], q2["key"]} <= review                  # what lost points goes to the review list


def test_a_failed_check_leaves_it_for_the_teacher():
    client, store, bank, test, lessons = make(Verdicts([], fail="rate_limited"))
    sim = start(client, test)
    done = write(client, sim, boards=2)
    assert done["checking"] is True and done["review"]["state"] == "failed"


def test_a_simulation_with_no_board_at_all_is_zero_without_a_check():
    client, store, bank, test, lessons = make(None)
    sim = start(client, test)
    done = write(client, sim, boards=0, typed={0: "5"})                         # a typed answer without a board is not an answer
    assert done["checking"] is False and done["grade"] == 0
