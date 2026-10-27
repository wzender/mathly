import copy
import asyncio

import httpx

from app.main import create_app
from app.math_skills import algebra9, problems


def test_the_algebra_graph_is_whole():
    graph = algebra9()
    assert problems(graph) == []
    assert len(graph["skills"]) == 56
    assert {unit["id"] for unit in graph["units"]} == {"f", "t", "n", "q", "p", "w"}


def test_a_broken_graph_is_named():
    graph = copy.deepcopy(algebra9())
    skill = lambda sid: next(item for item in graph["skills"] if item["id"] == sid)
    skill("f_neg")["prereqs"] = ["f_ops"]
    assert problems(graph)[0].startswith("cycle:")


def test_math_is_the_only_page_and_api():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://test") as client:
            assert "מתמטיקה בכיף" in (await client.get("/")).text
            assert "מתמטיקה בכיף" in (await client.get("/math")).text
            assert (await client.get("/api/math/skills")).json() == algebra9()
            assert (await client.get("/api/health")).json() == {"ok": True, "app": "mathly"}
    asyncio.run(check())


class FakeSolver:
    def solve(self, image, media_type):
        return {"readable": True, "problem": "$x² = 9$", "steps": [{"hint": "h", "work": "w"}],
                "answer": "$x = ±3$", "skill": "q_eq_simple", "note": ""}


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
