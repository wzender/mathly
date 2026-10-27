import asyncio
import time
import threading

import httpx

from app.main import create_app
from app.math_photo import PhotoUnavailable


class GeometrySolver:
    def solve(self, image, media_type):
        assert image == b"photo"
        assert media_type == "image/jpeg"
        return {"readable": True, "problem": "triangle", "steps": [{"hint": "h", "work": "w"}],
                "answer": "10 cm", "skill": "g_pythagoras", "note": ""}


def photo_app(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    app = create_app()
    app.state.photo, app.state.photo_key = GeometrySolver(), "test"
    return app


def upload():
    return {"photo": ("triangle.jpg", b"photo", "image/jpeg")}


def test_phone_photo_arrives_on_computer_and_can_only_be_sent_once(monkeypatch):
    app = photo_app(monkeypatch)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as computer:
            pairing = await computer.post("/api/math/photo-sessions")
            assert pairing.status_code == 200
            token = pairing.json()["token"]
            assert pairing.json()["expires_in"] == 900
            endpoint = f"/api/math/photo-sessions/{token}"
            assert (await computer.get(endpoint)).json()["state"] == "waiting"
            # A separate phone browser has no desktop cookies or login token.
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as phone:
                result = await phone.post("/api/math/phone-photo", headers={"X-Photo-Token": token}, files=upload())
                assert result.json() == {"ok": True, "readable": True}
                assert (await phone.post("/api/math/phone-photo", headers={"X-Photo-Token": token}, files=upload())).status_code == 409
            result = await computer.get(endpoint)
            assert result.headers["cache-control"] == "no-store"
            assert result.json()["state"] == "done"
            assert result.json()["result"]["answer"] == "10 cm"

    asyncio.run(check())


def test_invalid_and_expired_phone_links_are_rejected(monkeypatch):
    app = photo_app(monkeypatch)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post("/api/math/phone-photo", files=upload())).status_code == 410
            assert (await client.get("/api/math/photo-sessions/unknown")).status_code == 410
            token = (await client.post("/api/math/photo-sessions")).json()["token"]
            monkeypatch.setattr("app.main.time.monotonic", lambda: time_value + 901)
            assert (await client.post("/api/math/phone-photo", headers={"X-Photo-Token": token}, files=upload())).status_code == 410

    time_value = time.monotonic()
    asyncio.run(check())


def test_failed_upload_can_be_retried(monkeypatch):
    app = photo_app(monkeypatch)

    class Unavailable:
        def solve(self, *_):
            raise PhotoUnavailable("try again")

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            token = (await client.post("/api/math/photo-sessions")).json()["token"]
            headers = {"X-Photo-Token": token}
            app.state.photo = Unavailable()
            assert (await client.post("/api/math/phone-photo", headers=headers, files=upload())).status_code == 503
            status = (await client.get(f"/api/math/photo-sessions/{token}")).json()
            assert status["state"] == "error"
            assert status["error"] == "try again"
            app.state.photo = GeometrySolver()
            assert (await client.post("/api/math/phone-photo", headers=headers, files=upload())).status_code == 200

    asyncio.run(check())


def test_pairing_requires_configuration_and_qr_is_local_svg(monkeypatch):
    app = photo_app(monkeypatch)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            qr = await client.post("/api/math/photo-qr", json={"url": "http://test/phone#token"})
            assert qr.status_code == 200
            assert qr.headers["content-type"] == "image/svg+xml"
            assert "<svg" in qr.text
            assert (await client.post("/api/math/photo-qr", json={"url": "javascript:alert(1)"})).status_code == 400
            phone = await client.get("/phone")
            assert phone.status_code == 200
            assert phone.headers["referrer-policy"] == "no-referrer"
            monkeypatch.delenv("ANTHROPIC_API_KEY")
            monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
            assert (await client.post("/api/math/photo-sessions")).status_code == 503

    asyncio.run(check())


def test_only_desktop_owner_can_read_solution_and_phone_uses_owner_quota(monkeypatch):
    app = photo_app(monkeypatch)
    app.state.auth = object()
    monkeypatch.setattr("app.main.resolve_access", lambda store, token: {"email": token, "roles": []})
    monkeypatch.setattr("app.main.DAILY_PHOTOS", 1)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            owner = {"Authorization": "Bearer student"}
            assert (await client.post("/api/math/photo-sessions")).status_code == 401
            token = (await client.post("/api/math/photo-sessions", headers=owner)).json()["token"]
            endpoint = f"/api/math/photo-sessions/{token}"
            assert (await client.get(endpoint)).status_code == 401
            assert (await client.get(endpoint, headers={"Authorization": "Bearer other"})).status_code == 404
            assert (await client.post("/api/math/phone-photo", headers={"X-Photo-Token": token}, files=upload())).status_code == 200
            assert (await client.get(endpoint, headers=owner)).json()["result"]["left"] == 0
            second = (await client.post("/api/math/photo-sessions", headers=owner)).json()["token"]
            assert (await client.post("/api/math/phone-photo", headers={"X-Photo-Token": second}, files=upload())).status_code == 429

    asyncio.run(check())


def test_polling_stays_responsive_while_solving_and_duplicate_upload_is_rejected(monkeypatch):
    app = photo_app(monkeypatch)
    started, release = threading.Event(), threading.Event()

    class SlowSolver(GeometrySolver):
        def solve(self, image, media_type):
            started.set()
            assert release.wait(5)
            return super().solve(image, media_type)

    app.state.photo = SlowSolver()

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            token = (await client.post("/api/math/photo-sessions")).json()["token"]
            headers = {"X-Photo-Token": token}
            request = asyncio.create_task(client.post("/api/math/phone-photo", headers=headers, files=upload()))
            try:
                for _ in range(100):
                    if started.is_set():
                        break
                    await asyncio.sleep(.01)
                assert started.is_set()
                status = await asyncio.wait_for(client.get(f"/api/math/photo-sessions/{token}"), timeout=1)
                assert status.json()["state"] == "solving"
                assert (await client.post("/api/math/phone-photo", headers=headers, files=upload())).status_code == 409
            finally:
                release.set()
                assert (await request).status_code == 200

    asyncio.run(check())
