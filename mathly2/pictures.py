"""Pictures: students' written answers and the pages of a teacher's assignment. The server is the only door to them.

An uploaded image is checked (JPEG, PNG or WebP, at most 5 MB and 20 million pixels), turned upright, stripped of its metadata and
re-encoded as JPEG. A teacher's PDF becomes one picture per page. The bytes live in a private bucket read and written only with the server's
key (`SupabasePictures`; `MemoryPictures` for tests and local development); the rows that name them are in `m2_pictures`."""
from __future__ import annotations

import io
import json
import logging
import time
import urllib.error
import urllib.parse
import uuid
import warnings
from datetime import datetime

from PIL import Image, ImageOps, UnidentifiedImageError

from . import pooled

log = logging.getLogger("mathly.pictures")

MAX_IMAGE = 5_000_000
MAX_PDF = 10_000_000
MAX_PAGES = 20
MAX_SIDE = 2400                 # the longest side of a stored picture, in pixels
PAGE_WIDTH = 1600               # a rendered PDF page
RENDER_BUDGET = 30.0            # seconds for all the pages of one PDF
ALLOWED = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
Image.MAX_IMAGE_PIXELS = 20_000_000


class PictureError(Exception):
    """A picture that cannot be taken, with the HTTP status to answer and a short code."""

    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status, self.code = status, code


def clean_image(data: bytes, content_type: str) -> bytes:
    """A stored picture from an uploaded one: checked, upright, without metadata, as JPEG."""
    if len(data) > MAX_IMAGE:
        raise PictureError(413, "image_too_large")
    expected = ALLOWED.get((content_type or "").split(";")[0].strip().lower())
    if expected is None:
        raise PictureError(415, "unsupported_image")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            if image.format != expected:
                raise PictureError(415, "unsupported_image")
            image.load()
    except PictureError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError, SyntaxError) as exc:
        raise PictureError(400, "bad_image") from exc
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):                       # flatten transparency onto white
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    else:
        image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=88)                         # a new file: none of the original's metadata comes along
    return out.getvalue()


def render_pdf(data: bytes, limit: int = MAX_PDF) -> list[bytes]:
    """The pages of a teacher's PDF as stored pictures (JPEG); PictureError 413, 415 or 400 when it is not one we take."""
    if len(data) > limit:
        raise PictureError(413, "pdf_too_large")
    if not data.startswith(b"%PDF-"):
        raise PictureError(415, "not_a_pdf")
    import pypdfium2 as pdfium
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise PictureError(400, "bad_pdf") from exc
    try:
        if len(doc) == 0:
            raise PictureError(400, "bad_pdf")
        if len(doc) > MAX_PAGES:
            raise PictureError(413, "pdf_too_many_pages")
        started, pages = time.monotonic(), []
        for index in range(len(doc)):
            if time.monotonic() - started > RENDER_BUDGET:
                raise PictureError(413, "pdf_too_slow")
            page = doc[index]
            width = page.get_width() or 1
            image = page.render(scale=PAGE_WIDTH / width).to_pil().convert("RGB")
            out = io.BytesIO()
            image.save(out, "JPEG", quality=85)
            pages.append(out.getvalue())
        return pages
    finally:
        doc.close()


class MemoryPictures:
    """The bytes of pictures in memory: tests and local development."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, path: str, data: bytes, content_type: str = "image/jpeg") -> None:
        self.files[path] = data

    def get(self, path: str) -> bytes:
        try:
            return self.files[path]
        except KeyError:
            raise PictureError(404, "picture_missing") from None

    def delete(self, path: str) -> None:
        self.files.pop(path, None)


class SupabasePictures:
    """The bytes of pictures in a private Supabase Storage bucket, read and written with the secret key. The bucket is made when first needed."""

    def __init__(self, url: str, secret: str, bucket: str = "m2-answers") -> None:
        self.url, self.secret, self.bucket = url.rstrip("/"), secret, bucket
        self._ready = False

    def _headers(self, content_type: str | None = None) -> dict:
        headers = {"apikey": self.secret, "Authorization": f"Bearer {self.secret}", "User-Agent": "mathly2/1.0"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _object(self, path: str) -> str:
        return f"{self.url}/storage/v1/object/{self.bucket}/{urllib.parse.quote(path)}"

    def ensure_bucket(self) -> None:
        """Create the private bucket if it is not there (idempotent)."""
        if self._ready:
            return
        body = json.dumps({"id": self.bucket, "name": self.bucket, "public": False}).encode()
        try:
            pooled.request("POST", f"{self.url}/storage/v1/bucket", self._headers("application/json"), body, 15)
        except urllib.error.HTTPError as exc:
            if exc.code not in (400, 409):                            # 400/409: it already exists
                log.error("cannot create the picture bucket: %s", exc.code)
                raise PictureError(503, "answer_storage_unavailable") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise PictureError(503, "answer_storage_unavailable") from exc
        self._ready = True

    def put(self, path: str, data: bytes, content_type: str = "image/jpeg") -> None:
        self.ensure_bucket()
        try:
            pooled.request("POST", self._object(path), {**self._headers(content_type), "x-upsert": "true"}, data, 30)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            log.error("cannot store a picture: %s", exc)
            raise PictureError(503, "answer_storage_unavailable") from exc

    def get(self, path: str) -> bytes:
        try:
            return pooled.request("GET", self._object(path), self._headers(), None, 30)[1]
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                raise PictureError(404, "picture_missing") from exc
            raise PictureError(503, "answer_storage_unavailable") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise PictureError(503, "answer_storage_unavailable") from exc

    def delete(self, path: str) -> None:
        try:
            pooled.request("DELETE", self._object(path), self._headers(), None, 30)
        except urllib.error.HTTPError as exc:
            if exc.code not in (400, 404):                            # already gone is fine
                raise PictureError(503, "answer_storage_unavailable") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise PictureError(503, "answer_storage_unavailable") from exc


def store_picture(store, backend, owner_id: str, kind: str, jpeg: bytes, created_at: datetime | None = None) -> dict:
    """Keep one cleaned picture: its bytes in the bucket, its row in the database. Returns the row."""
    path = f"{owner_id}/{uuid.uuid4()}.jpg"
    backend.put(path, jpeg, "image/jpeg")
    return store.create_picture(owner_id, kind, path, "image/jpeg", len(jpeg), created_at)


def remove_picture(store, backend, picture: dict, at: datetime | None = None) -> None:
    """Delete a picture's bytes and mark its row deleted (the row stays, so what referred to it can say "the pictures were deleted")."""
    backend.delete(picture["path"])
    store.mark_picture_deleted(picture["id"], at)
