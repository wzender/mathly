"""The science path and its class vote (app/science.py)."""
import copy

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.science import problems, science

A, B, C = "voter-aaaa", "voter-bbbb", "voter-cccc"


@pytest.fixture
def client():
    return TestClient(create_app())


def open_room(client):
    r = client.post("/api/science/rooms", json={"skill": "rocket"})
    assert r.status_code == 200
    body = r.json()
    return body["code"], {"X-Host": body["host_key"]}


def vote(client, code, voter, choice, n=1):
    return client.post(f"/api/science/rooms/{code}/vote", json={"voter": voter, "choice": choice, "n": n})


def test_the_science_path_is_valid_and_hides_answers(client):
    assert problems(science()) == []
    graph = client.get("/api/science").json()
    assert graph["subject"] == "מדעים"
    assert [u["name"] for u in graph["units"]] == ["חידות"]
    assert [s["name"] for s in graph["skills"]] == ["טיל"]
    assert graph["skills"][0]["riddles"] == 3   # counted, not sent: they hold the answers
    assert "flies" not in str(graph)


def test_a_riddle_needs_exactly_one_answer_that_flies():
    broken = copy.deepcopy(science())
    for c in broken["skills"][0]["riddles"][0]["choices"]:
        c["outcome"] = "stuck"
    assert "rocket riddle 1: exactly one choice must fly" in problems(broken)


def test_votes_stay_hidden_until_the_host_checks_and_the_majority_is_launched(client):
    code, host = open_room(client)
    state = vote(client, code, A, 0).json()
    assert state["votes"] == 1 and state["mine"] == 0 and "counts" not in state and not state["host"]
    vote(client, code, B, 1)
    vote(client, code, C, 1)
    vote(client, code, A, 1)   # a voter may change their mind; still one vote
    assert client.get(f"/api/science/rooms/{code}?voter={A}").json()["votes"] == 3

    assert client.post(f"/api/science/rooms/{code}/check").status_code == 403   # only the host checks
    state = client.post(f"/api/science/rooms/{code}/check", headers=host).json()
    assert state["host"] and state["phase"] == "checked"
    assert state["counts"] == [0, 3, 0, 0] and state["picked"] == 1
    assert state["outcome"] == "flies" and state["right"] == 1
    assert vote(client, code, B, 2).status_code == 409   # checked: closed


def test_a_wrong_majority_does_not_fly_and_names_the_answer_that_would(client):
    code, host = open_room(client)
    vote(client, code, A, 2)
    vote(client, code, B, 2)
    vote(client, code, C, 0)
    state = client.post(f"/api/science/rooms/{code}/check", headers=host).json()
    assert state["picked"] == 2 and state["outcome"] == "stuck" and state["right"] == 1


def test_a_tie_is_not_launched(client):
    code, host = open_room(client)
    assert client.post(f"/api/science/rooms/{code}/check", headers=host).status_code == 400   # no votes yet
    vote(client, code, A, 0)
    vote(client, code, B, 3)
    state = client.post(f"/api/science/rooms/{code}/check", headers=host).json()
    assert state["phase"] == "voting" and state["tie"] == [0, 3]
    vote(client, code, C, 3)
    state = client.post(f"/api/science/rooms/{code}/check", headers=host).json()
    assert state["picked"] == 3 and state["outcome"] == "stuck" and state["tie"] == []


def test_the_host_moves_the_room_to_the_next_riddle(client):
    code, host = open_room(client)
    assert client.post(f"/api/science/rooms/{code}/next", headers=host).status_code == 409   # check first
    vote(client, code, A, 1)
    client.post(f"/api/science/rooms/{code}/check", headers=host)
    state = client.post(f"/api/science/rooms/{code}/next", headers=host).json()
    assert state["n"] == 2 and state["votes"] == 0 and state["phase"] == "voting"
    assert vote(client, code, B, 0, n=1).status_code == 409   # a late vote for the first riddle
    assert vote(client, code, B, 2, n=2).status_code == 200
    client.post(f"/api/science/rooms/{code}/check", headers=host)
    client.post(f"/api/science/rooms/{code}/next", headers=host)
    vote(client, code, B, 1, n=3)
    client.post(f"/api/science/rooms/{code}/check", headers=host)
    assert client.post(f"/api/science/rooms/{code}/next", headers=host).status_code == 409   # the last riddle


def test_unknown_codes_and_choices_are_refused(client):
    assert client.get("/api/science/rooms/0000").status_code == 404
    assert client.post("/api/science/rooms", json={"skill": "nope"}).status_code == 404
    code, _ = open_room(client)
    assert vote(client, code, A, 9).status_code == 400
