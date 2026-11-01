"""Lesson resources: photos a teacher adds to a unit (an exercise, a theory explanation, or a free note).

Rows live in `math_unit_resources`, images in the private `mathly-resources` bucket. Only the backend, with the
service key, reads or writes either; teachers reach them through `/api/math/units/.../resources`.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import uuid

from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .access import has_permission
from .answer_scans import MAX_IMAGE, ScanError, clean_image
from .math_skills import algebra9

log = logging.getLogger("mathly.unit_resources")
BUCKET = "mathly-resources"
KINDS = {"exercise": "תרגיל חדש", "theory": "הסבר תיאורטי", "other": "אחר"}
MAX_NOTE = 200


class ResourceUnavailable(RuntimeError):
    pass


class UnitResources:
    """Supabase storage for lesson resources, through the service key."""

    def __init__(self, auth):
        self.auth = auth

    @property
    def configured(self) -> bool:
        return bool(self.auth and self.auth.secret)

    def _request(self, path, method="GET", data=None, content_type=None, prefer=None) -> bytes:
        headers = {"Authorization": "Bearer " + self.auth.secret, "apikey": self.auth.secret,
                   "User-Agent": "mathly/1.0"}
        if content_type:
            headers["Content-Type"] = content_type
        if prefer:
            headers["Prefer"] = prefer
        req = urllib.request.Request(self.auth.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Never pass SQL, keys or storage paths on to the browser.
            log.warning("resource storage failed: %s", getattr(exc, "code", type(exc).__name__))
            raise ResourceUnavailable("resource storage unavailable") from exc

    def _rows(self, path, method="GET", body=None):
        raw = self._request(path, method, json.dumps(body).encode() if body is not None else None,
                            "application/json", "return=representation")
        return json.loads(raw or b"null") or []

    def list(self, unit_id: str) -> list[dict]:
        query = urllib.parse.urlencode({"unit_id": f"eq.{unit_id}", "select": "*", "order": "created_at.desc"})
        return self._rows(f"/rest/v1/math_unit_resources?{query}")

    def get(self, resource_id: str) -> dict | None:
        rows = self._rows(f"/rest/v1/math_unit_resources?id=eq.{resource_id}&select=*")
        return rows[0] if rows else None

    def add(self, row: dict) -> dict:
        return self._rows("/rest/v1/math_unit_resources", "POST", row)[0]

    def remove(self, resource_id: str) -> None:
        self._rows(f"/rest/v1/math_unit_resources?id=eq.{resource_id}", "DELETE")

    def put(self, object_key: str, data: bytes) -> None:
        self._request(f"/storage/v1/object/{BUCKET}/{urllib.parse.quote(object_key, safe='/')}",
                      "POST", data, "image/jpeg")

    def read(self, object_key: str) -> bytes:
        return self._request(f"/storage/v1/object/authenticated/{BUCKET}/{urllib.parse.quote(object_key, safe='/')}")

    def delete(self, object_key: str) -> None:
        self._request(f"/storage/v1/object/{BUCKET}", "DELETE",
                      json.dumps({"prefixes": [object_key]}).encode(), "application/json")


def public(row: dict) -> dict:
    """A resource as the browser sees it: no storage path."""
    return {key: row.get(key) for key in ("id", "unit_id", "kind", "note", "skill_id", "created_email", "created_at",
                                          "created_by")}


def resource_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise HTTPException(404, "resource not found") from exc


def install_resource_routes(app, signed_in):
    if not hasattr(app.state, "resources"):
        app.state.resources = UnitResources(app.state.auth)

    def teacher(user=Depends(signed_in)) -> dict:
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        if not has_permission(user, "students.view"):
            raise HTTPException(403, "teacher permission required")
        if not app.state.resources.configured:
            raise HTTPException(503, "resource storage is not configured")
        return user

    def unit_of(unit_id: str) -> dict:
        unit = next((u for u in algebra9()["units"] if u["id"] == unit_id), None)
        if unit is None:
            raise HTTPException(404, "unit not found")
        return unit

    async def storage(call, *args):
        try:
            return await run_in_threadpool(call, *args)
        except ResourceUnavailable as exc:
            raise HTTPException(503, "resource storage unavailable") from exc

    @app.get("/api/math/units/{unit_id}/resources")
    async def list_resources(unit_id: str, _user: dict = Depends(teacher)):
        unit_of(unit_id)
        rows = await storage(app.state.resources.list, unit_id)
        return JSONResponse({"resources": [public(row) for row in rows]}, headers={"Cache-Control": "no-store"})

    @app.post("/api/math/units/{unit_id}/resources")
    async def add_resource(unit_id: str, photo: UploadFile = File(...), kind: str = Form(...),
                           note: str = Form(""), skill: str = Form(""), user: dict = Depends(teacher)):
        unit = unit_of(unit_id)
        if kind not in KINDS:
            raise HTTPException(400, "choose what the photo shows")
        note = " ".join(note.split())
        if len(note) > MAX_NOTE:
            raise HTTPException(400, f"the description is longer than {MAX_NOTE} characters")
        if kind == "other" and not note:
            raise HTTPException(400, "describe the photo")
        skills = {s["id"]: s for s in algebra9()["skills"] if s["unit"] == unit_id}
        if skill and skill not in skills:
            raise HTTPException(400, "the topic is not part of this lesson")
        data = await photo.read(MAX_IMAGE + 1)
        try:
            image = clean_image(data, photo.content_type or "")
        except ScanError as exc:
            raise HTTPException(exc.status, exc.code) from exc
        key = f"{unit_id}/{uuid.uuid4()}.jpg"
        await storage(app.state.resources.put, key, image)
        try:
            row = await storage(app.state.resources.add, {
                "unit_id": unit_id, "kind": kind, "note": note, "skill_id": skill or None, "object_key": key,
                "byte_size": len(image), "created_by": user["id"], "created_email": user.get("email", "")})
        except HTTPException:
            try:
                await run_in_threadpool(app.state.resources.delete, key)
            except ResourceUnavailable:
                pass   # an orphaned image holds no row and is never shown
            raise
        label = " · ".join(filter(None, [unit["name"], KINDS[kind], skills[skill]["short"] if skill else ""]))
        app.state.actions.record(user, "resource_added", label)
        return JSONResponse(public(row), status_code=201, headers={"Cache-Control": "no-store"})

    @app.get("/api/math/resources/{rid}/image")
    async def resource_image(rid: str, _user: dict = Depends(teacher)):
        row = await storage(app.state.resources.get, resource_id(rid))
        if not row:
            raise HTTPException(404, "resource not found")
        return Response(await storage(app.state.resources.read, row["object_key"]), media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})

    @app.delete("/api/math/resources/{rid}")
    async def delete_resource(rid: str, user: dict = Depends(teacher)):
        row = await storage(app.state.resources.get, resource_id(rid))
        if not row:
            raise HTTPException(404, "resource not found")
        if row.get("created_by") != user["id"] and not has_permission(user, "management.access"):
            raise HTTPException(403, "only the teacher who added it can delete it")
        await storage(app.state.resources.remove, row["id"])
        try:
            await run_in_threadpool(app.state.resources.delete, row["object_key"])
        except ResourceUnavailable:
            log.warning("a deleted resource's image stayed in storage")
        return {"ok": True}
