"""The science path (`science.json`) and its class votes.

A riddle skill is solved by the class together, Kahoot style: someone (usually the teacher, on the board) opens a
vote and gets a 4-digit code, the students join with it and each picks an answer. Votes stay hidden until the host
presses check; then the answer most students chose is the one that is tried, and the rocket flies, falls back
(not enough fuel) or stays on the pad (too heavy). A tie is not checked: the tied answers are shown and the class
may change votes. The host can then move the room to the next riddle.

Rooms live in this process's memory: the app runs as one uvicorn process (see the Dockerfile), and a vote is
a few minutes of a lesson, so a restart only ends the votes in progress. A room is forgotten after ROOM_TTL
seconds without activity.
"""
from __future__ import annotations

import json
import secrets
import time
from functools import cache
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

GRAPH = Path(__file__).with_name("science.json")
OUTCOMES = ("flies", "falls", "stuck")
ROOM_TTL = 3 * 60 * 60
MAX_ROOMS = 500
MAX_VOTERS = 200


def problems(graph: dict) -> list[str]:
    """What is wrong with the science path: an unknown unit, or a riddle without exactly one answer that flies."""
    out = [] if str(graph.get("subject") or "").strip() else ["subject is required"]
    units = {u["id"] for u in graph.get("units", [])}
    for skill in graph.get("skills", []):
        sid = skill.get("id", "?")
        if skill.get("unit") not in units:
            out.append(f"{sid}: unknown unit {skill.get('unit')}")
        riddles = skill.get("riddles")
        if not isinstance(riddles, list) or not riddles:
            out.append(f"{sid}: needs riddles")
            continue
        for n, riddle in enumerate(riddles, 1):
            where = f"{sid} riddle {n}"
            for field in ("title", "story", "question"):
                if not str(riddle.get(field) or "").strip():
                    out.append(f"{where}: {field} is required")
            choices = riddle.get("choices") or []
            if len(choices) < 2:
                out.append(f"{where}: needs at least two choices")
            if len({c.get("text") for c in choices}) != len(choices):
                out.append(f"{where}: two choices read the same")
            if sum(c.get("outcome") == "flies" for c in choices) != 1:
                out.append(f"{where}: exactly one choice must fly")
            for c in choices:
                if c.get("outcome") not in OUTCOMES:
                    out.append(f"{where}: unknown outcome {c.get('outcome')}")
                if not str(c.get("why") or "").strip():
                    out.append(f"{where}: choice {c.get('text')} needs a why")
    return out


@cache
def science() -> dict:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    if found := problems(graph):
        raise ValueError(f"{GRAPH.name}: " + "; ".join(found))
    return graph


def public_path() -> dict:
    """The path for the screen: riddles are only counted here, their answers come with a room."""
    graph = science()
    return {"subject": graph["subject"], "units": graph["units"],
            "skills": [{k: v for k, v in s.items() if k != "riddles"} | {"riddles": len(s["riddles"])}
                       for s in graph["skills"]]}


def skill_of(skill_id: str) -> dict:
    found = next((s for s in science()["skills"] if s["id"] == skill_id), None)
    if found is None:
        raise HTTPException(404, "unknown riddle")
    return found


class Room:
    def __init__(self, code: str, skill: dict):
        self.code, self.skill, self.host = code, skill, secrets.token_urlsafe(16)
        self.index, self.votes, self.checked, self.tie = 0, {}, None, []
        self.touched = time.time()

    @property
    def riddle(self) -> dict:
        return self.skill["riddles"][self.index]

    def counts(self) -> list[int]:
        out = [0] * len(self.riddle["choices"])
        for choice in self.votes.values():
            out[choice] += 1
        return out

    def check(self) -> None:
        """Try the answer most voters chose; a tie leaves the vote open with the tied answers named."""
        counts = self.counts()
        top = max(counts)
        if top == 0:
            raise HTTPException(400, "no votes yet")
        leaders = [i for i, n in enumerate(counts) if n == top]
        if len(leaders) > 1:
            self.tie = leaders
            return
        self.tie, self.checked = [], leaders[0]

    def state(self, voter: str, host: str) -> dict:
        riddle, counts = self.riddle, self.counts()
        out = {"code": self.code, "skill": self.skill["id"], "name": self.skill["name"],
               "host": bool(host) and secrets.compare_digest(host, self.host),
               "n": self.index + 1, "of": len(self.skill["riddles"]),
               "title": riddle["title"], "story": riddle["story"], "question": riddle["question"],
               "choices": [c["text"] for c in riddle["choices"]],
               "votes": len(self.votes), "mine": self.votes.get(voter), "tie": self.tie,
               "phase": "checked" if self.checked is not None else "voting"}
        if self.checked is not None:
            picked = riddle["choices"][self.checked]
            out |= {"counts": counts, "picked": self.checked, "outcome": picked["outcome"], "why": picked["why"],
                    "right": next(i for i, c in enumerate(riddle["choices"]) if c["outcome"] == "flies")}
        return out


class StartBody(BaseModel):
    skill: str = Field(max_length=64)


class VoteBody(BaseModel):
    voter: str = Field(min_length=8, max_length=64)
    choice: int
    n: int   # the riddle the vote is for, so a late vote does not land on the next one


def install_science_routes(app: FastAPI) -> None:
    rooms: dict[str, Room] = {}
    app.state.science_rooms = rooms

    def prune() -> None:
        now = time.time()
        for code in [c for c, r in rooms.items() if now - r.touched > ROOM_TTL]:
            del rooms[code]

    def room_of(code: str) -> Room:
        prune()
        room = rooms.get(code)
        if room is None:
            raise HTTPException(404, "no vote with this code")
        room.touched = time.time()
        return room

    def hosted(code: str, host: str) -> Room:
        room = room_of(code)
        if not host or not secrets.compare_digest(host, room.host):
            raise HTTPException(403, "only the one who opened the vote can do this")
        return room

    @app.get("/api/science")
    async def science_path():
        return JSONResponse(public_path(), headers={"Cache-Control": "no-store"})

    @app.post("/api/science/rooms")
    async def open_room(body: StartBody):
        skill = skill_of(body.skill)
        prune()
        if len(rooms) >= MAX_ROOMS:
            raise HTTPException(503, "too many votes are open right now")
        code = f"{secrets.randbelow(9000) + 1000}"
        while code in rooms:
            code = f"{secrets.randbelow(9000) + 1000}"
        room = rooms[code] = Room(code, skill)
        return {**room.state("", room.host), "host_key": room.host}

    @app.get("/api/science/rooms/{code}")
    async def room_state(code: str, voter: str = "", x_host: str = Header("")):
        return JSONResponse(room_of(code).state(voter, x_host), headers={"Cache-Control": "no-store"})

    @app.post("/api/science/rooms/{code}/vote")
    async def vote(code: str, body: VoteBody, x_host: str = Header("")):
        room = room_of(code)
        if body.n != room.index + 1 or room.checked is not None:
            raise HTTPException(409, "this riddle is no longer open for votes")
        if not 0 <= body.choice < len(room.riddle["choices"]):
            raise HTTPException(400, "unknown choice")
        if body.voter not in room.votes and len(room.votes) >= MAX_VOTERS:
            raise HTTPException(409, "this vote is full")
        room.votes[body.voter] = body.choice
        return room.state(body.voter, x_host)

    @app.post("/api/science/rooms/{code}/check")
    async def check(code: str, voter: str = "", x_host: str = Header("")):
        room = hosted(code, x_host)
        if room.checked is None:
            room.check()
        return room.state(voter, x_host)

    @app.post("/api/science/rooms/{code}/next")
    async def next_riddle(code: str, voter: str = "", x_host: str = Header("")):
        room = hosted(code, x_host)
        if room.checked is None:
            raise HTTPException(409, "check this riddle first")
        if room.index + 1 >= len(room.skill["riddles"]):
            raise HTTPException(409, "this was the last riddle")
        room.index, room.votes, room.checked, room.tie = room.index + 1, {}, None, []
        return room.state(voter, x_host)
