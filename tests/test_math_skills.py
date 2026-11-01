import copy
import asyncio

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
    assert len(listed) == 95 and all(len(s["questions"]) == 10 for s in listed)
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
