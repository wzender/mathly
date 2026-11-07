from fastapi.testclient import TestClient

from mathly2.config import Settings
from mathly2.main import create_app


def test_lessons_list_has_every_lesson_and_skill_but_no_questions():
    lessons = TestClient(create_app(Settings(teachers=frozenset({"t@school.test"})))).get("/api/lessons", headers={"Authorization": "Bearer dev:t@school.test"}).json()
    assert len(lessons) == 24
    assert sum(len(lesson["skills"]) for lesson in lessons) == 96
    assert "questions" not in lessons[0]["skills"][0]
    assert lessons[0]["name"] == "טכניקה אלגברית 1"
    assert sum(l["has_quiz"] for l in lessons) == 4


def test_lessons_need_sign_in():
    assert TestClient(create_app()).get("/api/lessons").status_code == 401
