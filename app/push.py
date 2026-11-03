"""Push notifications: the phone is told when the computer asks for a photo of an answer.

The computer creates a photo request (POST /api/math/answer-attempts/{id}/scans). The phone already looks for requests
while the app is open on it; this notification brings the student to the app when it is closed. A tap opens the app,
and its usual look for requests shows the request's window with the 4-digit code.

Only phones subscribe (the page offers it on the same devices that look for requests), so the computer that made the
request does not get it. The browser's subscription (its push service address and two keys) is kept in the Supabase
table `math_push_subs` with the account's user ID; only the server's secret key reads it. A subscription the push
service no longer knows (404/410) is deleted.

On an iPhone the browser sends them only from the app added to the home screen (iOS 16.4 and later).

Env:  VAPID_PRIVATE_KEY  (the server's push key; make one with  python -m app.push  and keep it as a secret.
                          Changing it drops every subscription: each phone has to turn notifications on again.)
      VAPID_SUBJECT      (a contact the push services may write to, "mailto:..."; default: the first developer's email)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone

from .answer_scans import scan_code
from .auth import AuthUnavailable

log = logging.getLogger("mathly.push")
MAX_ENDPOINT = 1000
MIGRATION = "supabase/migrations/20261103180000_math_push_subs.sql"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def new_private_key() -> str:
    """A new VAPID private key, as VAPID_PRIVATE_KEY keeps it: the raw 32 bytes, base64url."""
    from cryptography.hazmat.primitives.asymmetric import ec
    return _b64(ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value.to_bytes(32, "big"))


def public_key(private: str) -> str:
    """The browser's applicationServerKey for this private key: the uncompressed point, base64url."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    raw = base64.urlsafe_b64decode(private + "=" * (-len(private) % 4))
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).rstrip(b"=").decode() != private:
        raise ValueError("not a 32-byte base64url key")
    key = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
    return _b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))


def scan_payload(result: dict) -> dict:
    """What the service worker shows for a photo request. No question text or name: it may show on a locked screen.
    The tag is the attempt's, so a new request for the same question replaces the old notification."""
    code = scan_code((result.get("scan") or {}).get("id"))
    return {"title": "📷 בקשת צילום מהמחשב",
            "body": (f"קוד {code} · " if code else "") + "צלמו את התשובה ושלחו למחשב.",
            "url": "/?from=push-scan", "tag": f"scan-{result['attempt']['id']}"}


def seconds_left(result: dict, now: datetime | None = None) -> int:
    """How long the push service should keep trying: until the request expires (a dead request is not worth a ring)."""
    expires = (result.get("scan") or {}).get("expires_at")
    try:
        end = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
    except ValueError:
        return 900
    return max(0, min(900, int((end - (now or datetime.now(timezone.utc))).total_seconds())))


class Push:
    def __init__(self, auth, private: str = "", subject: str = ""):
        self.auth, self.private, self.subject = auth, private.strip(), subject
        self.public, self.why = "", ""   # why: what keeps notifications off, in words for logs and the API
        self.notified: set[str] = set()   # scan IDs already announced (a repeated create_scan returns the same scan)
        if not self.private:
            self.why = "VAPID_PRIVATE_KEY is not set"
        elif not getattr(auth, "secret", ""):
            self.why = "SUPABASE_SECRET_KEY is not set"
        else:
            try:
                self.public = public_key(self.private)
            except ValueError as e:
                log.error("VAPID_PRIVATE_KEY is not a valid key: push notifications are off (%s)", e)
                self.why = "VAPID_PRIVATE_KEY is not a valid key"

    @property
    def on(self) -> bool:
        return not self.why

    # the table
    def _admin(self, path: str, method: str = "GET", body=None, prefer: str = "return=representation"):
        try:
            return self.auth._admin(path, method, body, prefer=prefer)
        except AuthUnavailable as e:
            if "answered 404" in str(e) or "math_push_subs" in str(e):
                raise AuthUnavailable(f"the table math_push_subs is missing; apply {MIGRATION}") from e
            raise

    def save(self, user_id: str, sub: dict) -> None:
        """Keeps a browser's subscription for this account, raising ValueError when it is not one.
        A subscription that belonged to another account on this phone moves to this one."""
        endpoint, keys = str(sub.get("endpoint") or ""), sub.get("keys") or {}
        if not endpoint.startswith("https://") or len(endpoint) > MAX_ENDPOINT or not isinstance(keys, dict):
            raise ValueError("not a push subscription")
        p256dh, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
        if not (0 < len(p256dh) <= 200 and 0 < len(auth) <= 100):
            raise ValueError("not a push subscription")
        self._admin("/rest/v1/math_push_subs?on_conflict=endpoint", "POST",
                    {"endpoint": endpoint, "user_id": user_id, "p256dh": p256dh, "auth": auth},
                    prefer="resolution=merge-duplicates,return=minimal")

    def delete(self, endpoint: str, user_id: str | None = None) -> None:
        q = {"endpoint": f"eq.{endpoint}", **({"user_id": f"eq.{user_id}"} if user_id else {})}
        self._admin("/rest/v1/math_push_subs?" + urllib.parse.urlencode(q), "DELETE", prefer="return=minimal")

    def mine(self, user_id: str) -> list[dict]:
        return self._admin("/rest/v1/math_push_subs?select=*&" + urllib.parse.urlencode({"user_id": f"eq.{user_id}"})) or []

    # sending
    def send(self, row: dict, payload: dict, ttl: int) -> bool:
        """One notification; False when it did not go (a subscription that is gone is deleted)."""
        from pywebpush import WebPushException, webpush
        try:
            webpush({"endpoint": row["endpoint"], "keys": {"p256dh": row["p256dh"], "auth": row["auth"]}},
                    json.dumps(payload, ensure_ascii=False), vapid_private_key=self.private,
                    vapid_claims={"sub": self.subject}, ttl=ttl, timeout=10,
                    headers={"Urgency": "high"})   # the student is waiting at the computer
            return True
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                log.info("push subscription is gone: deleted")
                try:
                    self.delete(row["endpoint"])
                except AuthUnavailable as e2:
                    log.warning("push subscription not deleted: %s", e2)
            else:
                log.warning("push failed: %s", e)
        except Exception as e:   # a network failure: the phone still finds the request when the app opens
            log.warning("push failed: %s", e)
        return False

    def scan_requested(self, user_id: str, result: dict) -> int:
        """Tells the account's phones about a new photo request; how many went. Called in the background."""
        scan = result.get("scan") or {}
        if not self.on or scan.get("state") != "waiting" or not scan.get("id") or scan["id"] in self.notified:
            return 0
        ttl = seconds_left(result)
        if not ttl:
            return 0
        self.notified.add(scan["id"])
        if len(self.notified) > 10_000:
            self.notified.clear()
        try:
            rows = self.mine(user_id)
        except AuthUnavailable as e:
            log.warning("photo request not pushed: %s", e)
            return 0
        message = scan_payload(result)
        return sum(self.send(row, message, ttl) for row in rows)


def load_push(auth) -> Push | None:
    if auth is None:
        return None
    subject = os.environ.get("VAPID_SUBJECT", "").strip()
    if not subject:
        dev = sorted(getattr(auth, "developers", ()) or getattr(auth, "teachers", ()) or ())
        subject = f"mailto:{dev[0]}" if dev else "mailto:admin@example.com"
    push = Push(auth, os.environ.get("VAPID_PRIVATE_KEY", ""), subject)
    log.info("photo request notifications: %s", "on" if push.on else f"off ({push.why})")
    return push


def install_push_routes(app, signed_in):
    """GET /api/push (the public key), POST /api/push/subscribe and /api/push/unsubscribe."""
    from fastapi import Body, Depends, HTTPException
    from fastapi.responses import JSONResponse

    if not hasattr(app.state, "push"):
        app.state.push = load_push(app.state.auth)

    def account(user=Depends(signed_in)) -> str:
        if not user or not user.get("id"):
            raise HTTPException(401, "sign_in_required")
        return user["id"]

    def push_on() -> Push:
        p = app.state.push
        if not p or not p.on:
            raise HTTPException(503, f"push notifications are off: {p.why if p else 'no sign-in'}")
        return p

    @app.get("/api/push")
    def push_info(_user: str = Depends(account)):
        """The server's push key, for the page to subscribe with; empty when notifications are off."""
        p = app.state.push
        return JSONResponse({"key": p.public if p and p.on else ""}, headers={"Cache-Control": "no-store"})

    @app.post("/api/push/subscribe")
    def push_subscribe(body: dict = Body(...), user: str = Depends(account)):
        p = push_on()
        try:
            p.save(user, body)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except AuthUnavailable as e:
            log.error("push subscription not kept: %s", e)
            raise HTTPException(503, str(e)) from e
        return {"ok": True}

    @app.post("/api/push/unsubscribe")
    def push_unsubscribe(body: dict = Body(...), user: str = Depends(account)):
        p = push_on()
        try:
            p.delete(str(body.get("endpoint") or ""), user)
        except AuthUnavailable as e:
            raise HTTPException(503, str(e)) from e
        return {"ok": True}


if __name__ == "__main__":
    key = new_private_key()
    print(f"VAPID_PRIVATE_KEY={key}\n# its public key (the page reads it from the server): {public_key(key)}")
