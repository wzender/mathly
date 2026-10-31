import copy
import asyncio

import httpx

from app.main import create_app
from app.math_skills import algebra9, practice_graph, problems, question_version


def test_open_ended_samples_and_content_identity():
    graph = copy.deepcopy(algebra9())
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
    graph["skills"][0]["sample"]["choices"] = []
    assert any("exactly one correct choice" in item for item in problems(graph))


def test_the_algebra_graph_is_whole():
    graph = algebra9()
    assert problems(graph) == []
    assert len(graph["skills"]) == 140
    assert {unit["id"] for unit in graph["units"]} == set("tkqearzhsmnpwd")
    assert {unit["subject"] for unit in graph["units"]} == {"מתמטיקה"}


def test_a_broken_graph_is_named():
    graph = copy.deepcopy(algebra9())
    skill = lambda sid: next(item for item in graph["skills"] if item["id"] == sid)
    skill("t_ext")["prereqs"] = ["t_square"]
    assert problems(graph)[0].startswith("cycle:")


def test_math_is_the_only_page_and_api():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://test") as client:
            assert "מתמטיקה בכיף" in (await client.get("/")).text
            assert "מתמטיקה בכיף" in (await client.get("/math")).text
            assert (await client.get("/api/math/skills")).json() == practice_graph(False)
            assert (await client.get("/api/health")).json() == {"ok": True, "app": "mathly"}
    asyncio.run(check())


class FakeSolver:
    def solve(self, image, media_type):
        return {"readable": True, "problem": "$x² = 9$", "steps": [{"hint": "h", "work": "w"}],
                "answer": "$x = ±3$", "skill": "e_simple", "note": ""}


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
