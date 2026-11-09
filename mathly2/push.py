"""Push notifications: the student's phone is told when a computer asks for a photo of an answer (PRD PSH-1, PSH-2).

The phone already looks for requests while the app is open; the notification brings the student to the app when it is closed. Only phones
subscribe, so the computer that asked gets none. A subscription the push service no longer knows (404 or 410) is deleted, and changing the
server's key (VAPID_PRIVATE_KEY) drops every subscription: each phone turns notifications on again. Without a key, notifications are off and
everything else works. On an iPhone they work only from the app added to the home screen (iOS 16.4 and later).

Make a key with `python -m mathly2.push` and keep it as a secret."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import datetime

log = logging.getLogger("mathly.push")
MAX_ENDPOINT = 1000


class Gone(Exception):
    """The push service no longer knows this subscription (404 or 410)."""


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def new_private_key() -> str:
    """A new VAPID private key as VAPID_PRIVATE_KEY keeps it: the raw 32 bytes, base64url."""
    from cryptography.hazmat.primitives.asymmetric import ec
    return _b64(ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value.to_bytes(32, "big"))


def public_key(private: str) -> str:
    """The browser's applicationServerKey for a private key: the uncompressed point, base64url. ValueError for a key that is not one."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    try:
        raw = base64.urlsafe_b64decode(private + "=" * (-len(private) % 4))
    except ValueError as exc:
        raise ValueError("not a 32-byte base64url key") from exc
    if len(raw) != 32 or _b64(raw) != private:
        raise ValueError("not a 32-byte base64url key")
    key = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
    return _b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))


def request_payload(request: dict, assignment: dict | None) -> dict:
    """What the service worker shows for a photo request. No question text or name: it may show on a locked screen. The tag is the assignment's,
    so a newer request for the same answer replaces the older notification."""
    return {"title": "📷 בקשת צילום מהמחשב", "body": f"קוד {request['code']} · צלמו את התשובה ושלחו למחשב.",
            "url": f"/#/assignment/{request['assignment_id']}", "tag": f"photo-{request['assignment_id']}"}


def seconds_left(request: dict, now: datetime) -> int:
    """How long the push service should keep trying: until the request expires (a dead request is not worth a ring)."""
    return max(0, min(900, int((request["expires_at"] - now).total_seconds())))


def web_push(subscription: dict, payload: dict, private: str, subject: str, ttl: int) -> None:
    """The real sender (pywebpush). Raises Gone for a subscription the push service no longer knows."""
    from pywebpush import WebPushException, webpush
    try:
        webpush({"endpoint": subscription["endpoint"], "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]}},
                json.dumps(payload, ensure_ascii=False), vapid_private_key=private, vapid_claims={"sub": subject}, ttl=ttl, timeout=10,
                headers={"Urgency": "high"})                        # the student is waiting at the computer
    except WebPushException as exc:
        if getattr(exc.response, "status_code", None) in (404, 410):
            raise Gone() from exc
        raise


class Pusher:
    """Subscriptions and sending, on the store's table. `sender(subscription, payload, ttl)` is injectable so tests do not touch the network."""

    def __init__(self, store, private: str = "", subject: str = "", sender=None) -> None:
        self.store, self.private, self.subject = store, private.strip(), subject
        self.public, self.why, self.key_id = "", "", ""
        if not self.private:
            self.why = "VAPID_PRIVATE_KEY is not set"
        else:
            try:
                self.public = public_key(self.private)
                self.key_id = hashlib.sha256(self.public.encode()).hexdigest()[:16]
            except ValueError as exc:
                log.error("VAPID_PRIVATE_KEY is not a valid key: push notifications are off (%s)", exc)
                self.why = "VAPID_PRIVATE_KEY is not a valid key"
        self.sender = sender or (lambda sub, payload, ttl: web_push(sub, payload, self.private, self.subject, ttl))

    @property
    def on(self) -> bool:
        return not self.why

    def subscribe(self, user_id: str, body: dict) -> None:
        """Keep a browser's subscription for this account (ValueError when it is not one). Subscriptions made under another key are dropped first."""
        endpoint, keys = str(body.get("endpoint") or ""), body.get("keys") or {}
        if not endpoint.startswith("https://") or len(endpoint) > MAX_ENDPOINT or not isinstance(keys, dict):
            raise ValueError("not a push subscription")
        p256dh, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
        if not (0 < len(p256dh) <= 200 and 0 < len(auth) <= 100):
            raise ValueError("not a push subscription")
        self.store.drop_push_subscriptions_not_of(self.key_id)
        self.store.add_push_subscription(user_id, endpoint, p256dh, auth, self.key_id)

    def notify(self, user_id: str, payload: dict, ttl: int) -> int:
        """Send to the account's phones; how many went. A dead subscription is deleted, other failures are logged (the phone still finds the
        request when the app opens)."""
        if not self.on or ttl <= 0:
            return 0
        self.store.drop_push_subscriptions_not_of(self.key_id)
        sent = 0
        for sub in self.store.push_subscriptions_of(user_id):
            try:
                self.sender(sub, payload, ttl)
                sent += 1
            except Gone:
                self.store.delete_push_subscription(sub["endpoint"])
            except Exception as exc:
                log.warning("push failed: %s", exc)
        return sent


def default_subject(settings) -> str:
    if settings.vapid_subject:
        return settings.vapid_subject
    first = sorted(settings.developers)
    return f"mailto:{first[0]}" if first else "mailto:admin@example.com"


if __name__ == "__main__":
    key = new_private_key()
    print(f"VAPID_PRIVATE_KEY={key}\n# its public key (the page reads it from the server): {public_key(key)}")
