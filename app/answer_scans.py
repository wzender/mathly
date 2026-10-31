"""Durable answer scans. RPC transactions own state; the server owns image access.

No fallback to process memory is allowed. The adapter uses the same Supabase
project as sign-in; a verified user ID is passed on every student operation.
"""
from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE = 5_000_000
Image.MAX_IMAGE_PIXELS = 20_000_000
BUCKET = "mathly-answers"


@dataclass
class ScanError(Exception):
    status: int
    code: str


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


class AnswerScans:
    def __init__(self, auth, *, enabled=None):
        self.auth = auth
        self.enabled = (os.environ.get("MATHLY_ANSWER_SCANS_ENABLED") == "1") if enabled is None else enabled

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

    def put(self, object_key, data):
        self._request(f"/storage/v1/object/{BUCKET}/{urllib.parse.quote(object_key, safe='/')}",
                      "POST", data, "image/jpeg")

    def read(self, object_key):
        return self._request(f"/storage/v1/object/authenticated/{BUCKET}/{urllib.parse.quote(object_key, safe='/')}")

    def delete(self, object_key):
        self._request(f"/storage/v1/object/{BUCKET}", "DELETE",
                      json.dumps({"prefixes": [object_key]}).encode(), "application/json")

    def cleanup(self):
        candidates = self.action(None, "cleanup_candidates")
        for key in candidates:
            self.delete(key)
        return len(candidates)


def public_result(result):
    """Keep storage paths and upload coordination secrets out of public responses."""
    if isinstance(result, list):
        return [public_result(item) for item in result]
    result = {k: dict(v) if isinstance(v, dict) else v for k, v in result.items()}
    if result.get("scan"):
        for key in ("idempotency_key", "lease_id", "lease_until"):
            result["scan"].pop(key, None)
    if result.get("attachment"):
        result["attachment"].pop("object_key", None)
    if result.get("grading"):
        result["grading"].pop("lease_id", None)
        result["grading"].pop("lease_until", None)
    return result


def uuid_text(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ScanError(404, "not_found") from exc
