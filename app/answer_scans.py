"""Durable answer scans. RPC transactions own state; the server owns image access.

No fallback to process memory is allowed. The adapter uses the same Supabase
project as sign-in; a verified user ID is passed on every student operation.

Images: with MATHLY_ANSWER_BUCKET set (a private Hugging Face storage bucket, written with HF_TOKEN), new answer
images are kept there instead of Supabase Storage, so reading them back (to grade and to show them) is not Supabase
egress. Their file names start with "hf-"; images saved before keep their names and stay in Supabase, where they
are still read from.
"""
from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE = 5_000_000
Image.MAX_IMAGE_PIXELS = 20_000_000
BUCKET = "mathly-answers"
HUB_MARK = "hf-"   # an image kept in the Hugging Face bucket: its file name starts with this
ORPHAN_AGE = timedelta(hours=24)
log = logging.getLogger("mathly.answers")


@dataclass
class ScanError(Exception):
    status: int
    code: str
    reason: str = ""   # why an AI check failed (math_photo.failure_reason), for the teacher's error details
    detail: str = ""   # the technical line behind it


def clean_image(data: bytes, content_type: str) -> bytes:
    if not data:
        raise ScanError(400, "empty_image")
    if len(data) > MAX_IMAGE:
        raise ScanError(413, "image_too_large")
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise ScanError(415, "unsupported_image")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ("JPEG", "PNG", "WEBP") or source.width * source.height > 20_000_000:
                    raise ValueError("image dimensions or format")
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((2400, 2400))
                output = io.BytesIO()
                image.save(output, "JPEG", quality=88)  # drops EXIF, GPS, and embedded metadata
                result = output.getvalue()
                if len(result) > MAX_IMAGE:
                    raise ScanError(413, "image_too_large")
                return result
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ScanError(415, "invalid_image") from exc


class HubImages:
    """Answer images in a private Hugging Face storage bucket, under answers/<the object key>."""
    PREFIX = "answers/"

    def __init__(self, bucket: str, token: str | None = None):
        from huggingface_hub import HfApi
        from huggingface_hub.utils import disable_progress_bars
        disable_progress_bars()   # no progress bars in the server's log
        self.bucket, self.api = bucket, HfApi(token=token or None)

    @classmethod
    def from_env(cls):
        bucket = os.environ.get("MATHLY_ANSWER_BUCKET", "").strip()
        return cls(bucket, os.environ.get("HF_TOKEN", "").strip()) if bucket else None

    def _call(self, what, *args, **kwargs):
        from huggingface_hub.errors import EntryNotFoundError
        try:
            return what(self.bucket, *args, **kwargs)
        except EntryNotFoundError as exc:
            raise ScanError(404, "not_found") from exc
        except Exception as exc:   # network, token or quota: never pass the details on to the browser
            log.warning("answer bucket failed: %s", type(exc).__name__)
            raise ScanError(503, "answer_storage_unavailable") from exc

    def put(self, object_key: str, data: bytes):
        self._call(self.api.batch_bucket_files, add=[(data, self.PREFIX + object_key)])

    def read(self, object_key: str) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "image.jpg"
            self._call(self.api.download_bucket_files, [(self.PREFIX + object_key, str(target))], raise_on_missing_files=True)
            return target.read_bytes()

    def delete(self, object_key: str):
        self._call(self.api.batch_bucket_files, delete=[self.PREFIX + object_key])

    def older_than(self, age: timedelta) -> list[str]:
        """The object keys uploaded before now - age."""
        cutoff = datetime.now(timezone.utc) - age
        files = self._call(self.api.list_bucket_tree, prefix=self.PREFIX.rstrip("/"), recursive=True)
        return [f.path[len(self.PREFIX):] for f in files
                if getattr(f, "type", "") == "file" and f.path.startswith(self.PREFIX)
                and (getattr(f, "uploaded_at", None) or getattr(f, "mtime", None) or cutoff) < cutoff]


def on_hub(object_key: str) -> bool:
    return object_key.rsplit("/", 1)[-1].startswith(HUB_MARK)


class AnswerScans:
    def __init__(self, auth, *, enabled=None, images="env"):
        self.auth = auth
        self.enabled = (os.environ.get("MATHLY_ANSWER_SCANS_ENABLED") == "1") if enabled is None else enabled
        self.images = HubImages.from_env() if images == "env" else images   # None: every image in Supabase Storage

    def new_key(self, user_id: str, scan_id: str, lease_id: str) -> str:
        """A new image's object key; the database checks its user/scan/lease start."""
        return f"{user_id}/{scan_id}/{lease_id}/{HUB_MARK if self.images else ''}{uuid.uuid4()}.jpg"

    @property
    def configured(self):
        return bool(self.enabled and self.auth and self.auth.secret)

    def action(self, user_id: str | None, action: str, **data):
        if not self.configured:
            raise ScanError(503, "answer_storage_unavailable")
        body = {"p_user": user_id, "p_action": action, "p_data": data}
        raw = self._request("/rest/v1/rpc/math_answer_action", "POST", json.dumps(body).encode(), "application/json")
        return json.loads(raw)

    def grade(self, user_id: str, action: str, **data):
        if not self.configured:
            raise ScanError(503, "answer_storage_unavailable")
        body = {"p_user": user_id, "p_action": action, "p_data": data}
        raw = self._request("/rest/v1/rpc/math_grade_action", "POST", json.dumps(body).encode(), "application/json")
        return json.loads(raw)

    def _request(self, path, method="GET", data=None, content_type=None):
        headers = {"Authorization": "Bearer " + self.auth.secret, "apikey": self.auth.secret,
                   "User-Agent": "mathly/1.0"}
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(self.auth.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            # Only recognized database errors become public errors. Never expose SQL or keys.
            try:
                error = json.loads(exc.read())
            except (ValueError, OSError):
                error = {}
            code, message = error.get("code"), error.get("message", "")
            if code == "P0002":
                raise ScanError(404, "not_found") from exc
            if code == "P0001" and message == "grading_limit":
                raise ScanError(429, message) from exc
            if code == "P0001" and message in {"superseded", "invalid_upload", "upload_in_progress", "confirmation_required",
                                               "answer_required", "grading_busy", "grading_interrupted"}:
                raise ScanError(409, message) from exc
            raise ScanError(503, "answer_storage_unavailable") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ScanError(503, "answer_storage_unavailable") from exc

    def _hub(self, object_key):
        if not on_hub(object_key):
            return None
        if not self.images:   # an "hf-" image while the bucket is not configured: say so, never ask Supabase for it
            raise ScanError(503, "answer_storage_unavailable")
        return self.images

    def put(self, object_key, data):
        if hub := self._hub(object_key):
            return hub.put(object_key, data)
        self._request(f"/storage/v1/object/{BUCKET}/{urllib.parse.quote(object_key, safe='/')}",
                      "POST", data, "image/jpeg")

    def read(self, object_key):
        if hub := self._hub(object_key):
            return hub.read(object_key)
        return self._request(f"/storage/v1/object/authenticated/{BUCKET}/{urllib.parse.quote(object_key, safe='/')}")

    def delete(self, object_key):
        if hub := self._hub(object_key):
            return hub.delete(object_key)
        self._request(f"/storage/v1/object/{BUCKET}", "DELETE",
                      json.dumps({"prefixes": [object_key]}).encode(), "application/json")

    def referenced(self, keys: list[str]) -> set[str]:
        """Which of these object keys an answer still uses."""
        found = set()
        for i in range(0, len(keys), 40):
            chunk = keys[i:i + 40]
            names = ",".join('"' + k.replace('"', "") + '"' for k in chunk)
            raw = self._request("/rest/v1/math_answer_attachments?select=object_key&object_key=in."
                                + urllib.parse.quote(f"({names})", safe="(),"))
            found |= {row["object_key"] for row in json.loads(raw)}
        return found

    def cleanup(self):
        """Removes images no answer uses, a day after they were uploaded (an upload's answer is saved right after it)."""
        candidates = self.action(None, "cleanup_candidates")
        for key in candidates:
            self.delete(key)
        removed = len(candidates)
        if self.images:   # the database cannot list the bucket: the bucket is listed and each image looked up
            old = self.images.older_than(ORPHAN_AGE)
            used = self.referenced(old) if old else set()
            for key in old:
                if key not in used:
                    self.images.delete(key)
                    removed += 1
        return removed


def public_result(result):
    """Keep storage paths and upload coordination secrets out of public responses."""
    if isinstance(result, list):
        return [public_result(item) for item in result]
    result = {k: dict(v) if isinstance(v, dict) else v for k, v in result.items()}
    if result.get("scan"):
        for key in ("idempotency_key", "lease_id", "lease_until"):
            result["scan"].pop(key, None)
        result["scan"]["code"] = scan_code(result["scan"].get("id"))
    if result.get("attachment"):
        result["attachment"].pop("object_key", None)
    if result.get("grading"):
        result["grading"].pop("lease_id", None)
        result["grading"].pop("lease_until", None)
    return result


def scan_code(scan_id):
    """The 4 digits shown on both the computer and the phone, so the student can match the request."""
    try:
        return f"{uuid.UUID(str(scan_id)).int % 10000:04d}"
    except (ValueError, TypeError, AttributeError):
        return ""


def uuid_text(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ScanError(404, "not_found") from exc
