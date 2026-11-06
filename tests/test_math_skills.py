import copy
import asyncio
import re

import pytest

import httpx

from app.main import create_app
from app.answer_routes import grading_key, open_ended_locked
from app.math_skills import algebra9, practice_graph, problems, question_version


def test_open_ended_samples_and_content_identity():
    graph = copy.deepcopy(algebra9())
    graph["skills"][0].pop("questions")
    sample = graph["skills"][0]["sample"] = {"type": "open-ended", "version": 1,
                                           "question": "Draw a triangle."}
    assert problems(graph) == []
    original = question_version(sample)
    sample["question"] = "Draw a rectangle."
    assert question_version(sample) != original
    sample["choices"] = []
    assert any("cannot have choices" in item for item in problems(graph))
    sample.pop("choices")
    sample["version"] = True
    assert any("version" in item for item in problems(graph))
    sample["type"] = "unknown"
    assert any("unknown question type" in item for item in problems(graph))


def test_choice_samples_still_require_one_correct_choice():
    graph = copy.deepcopy(algebra9())
    graph["skills"][0]["questions"][3]["choices"] = []
    assert "t_ext question 4: needs exactly one correct choice" in problems(graph)


GEOMETRY_UNITS = {"k", "i", "a", "l", "z", "z2", "g", "m", "b", "c", "o", "d"}


def test_every_geometry_question_has_a_figure():
    graph = algebra9()
    geometry = [q for s in graph["skills"] if s["unit"] in GEOMETRY_UNITS for q in s.get("questions", [])]
    assert len(geometry) == 410 and all(q.get("figure") for q in geometry)
    assert not any("figure" in q for s in graph["skills"] if s["unit"] not in GEOMETRY_UNITS
                   for q in s.get("questions", []))


def test_a_broken_figure_is_named():
    graph = copy.deepcopy(algebra9())
    question = next(s for s in graph["skills"] if s["id"] == "k_def")["questions"][1]
    question["figure"] = "A=0,0; B=1,0; poly A B C"
    assert "k_def question 2: figure names unknown point C" in problems(graph)
    question["figure"] = "A=0,0; B=1,0; spin A B"
    assert "k_def question 2: unknown figure operation spin" in problems(graph)
    question["figure"] = "A=0,0; B=1,0; tick A B many"
    assert any("count must be a number" in item for item in problems(graph))


def test_question_lists():
    graph = copy.deepcopy(algebra9())
    skill = lambda sid: next(item for item in graph["skills"] if item["id"] == sid)
    listed = [s for s in graph["skills"] if "questions" in s]
    assert [s["id"] for s in graph["skills"] if "sample" in s] == ["a_30_side"]   # the photographed answer
    assert len(listed) == 95
    # טכניקה אלגברית 1 has 30 questions a skill, a round asks a random 10 of them; the others have 10
    assert {s["id"]: len(s["questions"]) for s in listed if s["unit"] == "t"} == dict.fromkeys(
        ["t_ext", "t_simplify", "t_ext_eq", "t_area", "t_formulas"], 30)
    assert all(len(s["questions"]) == 10 for s in listed if s["unit"] != "t")
    skill("t_ext")["sample"] = skill("t_ext")["questions"][0]
    skill("t_gcf")["questions"] = []
    skill("q_props")["questions"][0] = {"type": "open-ended", "version": 1, "question": "Sketch it."}
    found = problems(graph)
    assert "t_ext: needs a sample or a list of questions, not both" in found
    assert "t_gcf: the question list is empty" in found
    assert "q_props question 1: a question list holds multiple-choice questions only" in found


def test_the_algebra_graph_is_whole():
    graph = algebra9()
    assert problems(graph) == []
    assert len(graph["skills"]) == 96
    assert {unit["id"] for unit in graph["units"]} == set("tkiqalzevgrmhsnbcopwd") | {"t2", "q2", "z2"}
    assert {unit["subject"] for unit in graph["units"]} == {"מתמטיקה"}


def test_a_broken_graph_is_named():
    graph = copy.deepcopy(algebra9())
    skill = lambda sid: next(item for item in graph["skills"] if item["id"] == sid)
    skill("t_ext")["prereqs"] = ["t_formulas"]
    assert problems(graph)[0].startswith("cycle:")


def test_math_is_the_only_page_and_api():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://test") as client:
            assert "לומדים בכיף" in (await client.get("/")).text
            assert "לומדים בכיף" in (await client.get("/math")).text
            assert (await client.get("/api/math/skills")).json() == practice_graph(False)
            assert (await client.get("/api/health")).json() == {"ok": True, "app": "mathly"}
    asyncio.run(check())


class FakeSolver:
    def solve(self, image, media_type):
        return {"readable": True, "problem": "$x² = 9$", "steps": [{"hint": "h", "work": "w"}],
                "answer": "$x = ±3$", "skill": "e_way", "note": ""}


def test_a_photographed_problem_is_solved(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    app = create_app()
    app.state.photo, app.state.photo_key = FakeSolver(), "test"
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/math/photo", files={"photo": ("problem.jpg", b"jpeg", "image/jpeg")})
            assert response.status_code == 200
            assert response.json()["answer"] == "$x = ±3$"
            assert response.json()["left"] is None
    asyncio.run(check())


def test_rollout_and_rollback_question_variants():
    enabled, disabled = practice_graph(True), practice_graph(False)
    assert problems(enabled) == problems(disabled) == []
    opened = next(s for s in enabled['skills'] if s['id']=='a_30_side')
    fallback = next(s for s in disabled['skills'] if s['id']=='a_30_side')
    assert opened['sample']['type']=='open-ended' and 'choices' not in opened['sample']
    assert opened['question_version']==question_version(opened['sample'])
    assert len(fallback['sample']['choices']) == 3
    assert all('fallback_sample' not in s for s in enabled['skills'])


def test_each_subunit_names_its_units_subject():
    graph = practice_graph(False)
    subject = {unit["id"]: unit["subject"] for unit in graph["units"]}
    assert all(skill["subject"] == subject[skill["unit"]] for skill in graph["skills"])


def test_a_class_of_a_split_unit_keeps_its_content():
    from app.main import units_of
    assert units_of({"lessons": ["k"]}) == ["k", "i"]                       # דלתון ומשולש שווה שוקיים
    assert units_of({"lessons": ["m", "t"]}) == ["t", "t2", "m", "b", "c"]       # מלבן, מעוין וריבוע
    assert units_of({"lessons": ["i"]}) == ["i"]
    assert units_of({"lessons": ["t", "z"]}) == ["t", "t2", "z", "z2", "g"]  # both parts of a long unit
    assert units_of({}) == [unit["id"] for unit in algebra9()["units"]]


def test_open_ended_questions_are_locked_by_default(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("MATHLY_OPEN_ENDED_LOCKED", raising=False)
    assert open_ended_locked() and grading_key() == ""   # no key, so no grading call can start
    locked = [s["id"] for s in practice_graph(True, True)["skills"] if s.get("locked")]
    assert locked == ["a_30_side"]
    assert not any(s.get("locked") for s in practice_graph(False, True)["skills"])   # a choice question is never locked
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    assert not open_ended_locked() and grading_key() == "test"
    assert not any(s.get("locked") for s in practice_graph(True, False)["skills"])
    app = create_app()
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            monkeypatch.delenv("MATHLY_OPEN_ENDED_LOCKED")
            skills = (await client.get("/api/math/skills")).json()["skills"]
            assert all(not s.get("locked") for s in skills)   # without answer storage the choice version is served
    asyncio.run(check())


def test_no_unit_has_more_than_six_subunits():
    from collections import Counter
    graph = algebra9()
    count = Counter(skill["unit"] for skill in graph["skills"])
    assert all(1 <= count[unit["id"]] <= 6 for unit in graph["units"]), count


def test_unit_t_answers_are_right_and_no_wrong_choice_is_equivalent():
    """Recomputes, independently of how they were written, every unit-t question that is a bare expression,
    an expression to simplify, or an equation: the marked answer is right and every other choice is not."""
    sp = pytest.importorskip("sympy")
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
    tf = standard_transformations + (implicit_multiplication_application,)
    x = sp.Symbol("x")
    names = {v: sp.Symbol(v) for v in "xab"}

    def expr(t):
        t = t.strip().strip("$").replace("−", "-").replace("²", "**2").replace("·", "*").replace(" : 2", "/2")
        return sp.nsimplify(parse_expr(t, local_dict=names, transformations=tf), rational=True)

    def solution(text):
        if "$" not in text:
            return None   # "אין פתרון"
        return expr(text.split("=")[1])

    checked = 0
    for skill in algebra9()["skills"]:
        if skill["unit"] != "t":
            continue
        for q in skill["questions"]:
            body = re.fullmatch(r"(?:פשטו: |איזה ביטוי שווה ל־)?\$([^$]+)\$\??", q["question"])
            eq = re.fullmatch(r"פתרו: \$([^$=]+)=([^$=]+)\$", q["question"])
            if body and body[1].endswith("= ?") and not re.search(r"\d{2,}[²·]|^\d+ ·", body[1]):
                value = sp.expand(expr(body[1][:-3]))
                same = lambda c: sp.expand(expr(c["text"]) - value) == 0
            elif body and "=" not in body[1]:
                value = sp.expand(expr(body[1]))
                same = lambda c: sp.expand(expr(c["text"]) - value) == 0
            elif eq:
                roots = sp.solve(sp.Eq(expr(eq[1]), expr(eq[2])), x)
                same = lambda c: (solution(c["text"]) is None and not roots) or (solution(c["text"]) is not None and roots == [solution(c["text"])])
            else:
                continue
            for c in q["choices"]:
                assert same(c) == bool(c.get("correct")), (skill["id"], q["question"], c["text"])
            checked += 1
    assert checked >= 90


# ---- worked examples
EXAMPLE = {"question": "$(x + 5)(x − 2) = ?$",
           "steps": [{"do": "כופלים כל איבר בסוגריים הראשונים בכל איבר בשניים: $x·x + x·(−2) + 5·x + 5·(−2)$",
                      "why": "כך לא שוכחים אף מכפלה."},
                     {"do": "מחברים את האיברים הדומים: $−2x + 5x = 3x$", "why": "אותו חזקה של $x$ אפשר לחבר."}],
           "answer": "$x² + 3x − 10$"}


def with_example(example):
    graph = copy.deepcopy(algebra9())
    graph["skills"][0]["example"] = example
    return graph


def test_a_well_formed_worked_example_loads_and_reaches_the_page():
    graph = with_example(copy.deepcopy(EXAMPLE))
    assert problems(graph) == []


def test_the_skills_api_sends_a_skills_example(monkeypatch):
    graph = with_example(copy.deepcopy(EXAMPLE))
    monkeypatch.setattr("app.math_skills.algebra9", lambda: graph)
    sent = practice_graph(False)
    assert sent["skills"][0]["example"] == EXAMPLE and "example" not in sent["skills"][1]


def test_a_broken_worked_example_is_named():
    skill_id = algebra9()["skills"][0]["id"]
    broken = lambda **changes: problems(with_example({**copy.deepcopy(EXAMPLE), **changes}))
    assert f"{skill_id} example: needs at least one step" in broken(steps=[])
    assert f"{skill_id} example: needs at least one step" in broken(steps="x")
    assert any("step 2: needs what to do" in item for item in broken(steps=[EXAMPLE["steps"][0], {"do": "מחברים", "why": " "}]))
    assert any("step 1: needs what to do" in item for item in broken(steps=["not an object"]))
    assert f"{skill_id} example: an answer is required" in broken(answer="")
    assert f"{skill_id} example: question text is required" in broken(question=" ")
    assert problems(with_example("text")) == [f"{skill_id} example: must be an object"]


def test_an_example_may_not_be_one_of_the_skills_practice_questions():
    skill = algebra9()["skills"][0]
    practice = skill["questions"][2]["question"]
    spaced = "  " + practice.replace(" ", "   ") + "\n"   # the same question, spaced differently
    for copied in (practice, spaced):
        found = problems(with_example({**copy.deepcopy(EXAMPLE), "question": copied}))
        assert f"{skill['id']} example: repeats one of the skill's practice questions" in found


def test_the_skills_still_missing_a_worked_example_are_listed():
    from app.math_skills import skills_without_example
    graph = with_example(copy.deepcopy(EXAMPLE))
    missing = skills_without_example(graph)
    assert graph["skills"][0]["id"] not in missing and graph["skills"][1]["id"] in missing
    assert set(missing) <= {s["id"] for s in graph["skills"]}


def test_every_unit_quiz_question_names_skills_of_its_unit():
    graph = algebra9()
    for unit in (u for u in graph["units"] if "quiz" in u):
        mine = {s["id"] for s in graph["skills"] if s["unit"] == unit["id"]}
        for q in unit["quiz"]["questions"]:
            assert 1 <= len(q["skills"]) <= 3 and set(q["skills"]) <= mine


def test_a_quiz_question_without_skills_or_with_a_foreign_skill_is_named():
    graph = copy.deepcopy(algebra9())
    t = next(u for u in graph["units"] if u["id"] == "t")
    t["quiz"]["questions"][0].pop("skills")
    t["quiz"]["questions"][1]["skills"] = ["k_def"]
    t["quiz"]["questions"][2]["skills"] = ["t_ext", "t_ext", "t_area"]
    t["quiz"]["questions"][3]["skills"] = ["t_ext", "t_simplify", "t_area", "t_formulas"]
    found = problems(graph)
    assert "t quiz question 1: skills must name 1 to 3 different skills" in found
    assert "t quiz question 2: skill k_def is not a skill of unit t" in found
    assert "t quiz question 3: skills must name 1 to 3 different skills" in found
    assert "t quiz question 4: skills must name 1 to 3 different skills" in found


def test_skill_tags_do_not_change_a_quiz_questions_version():
    from app.math_skills import quiz_snapshot
    graph = copy.deepcopy(algebra9())
    t = next(u for u in graph["units"] if u["id"] == "t")
    before = question_version(quiz_snapshot(t, 0))
    t["quiz"]["questions"][0]["skills"] = ["t_formulas"]
    assert question_version(quiz_snapshot(t, 0)) == before
    assert "skills" not in quiz_snapshot(t, 0)
