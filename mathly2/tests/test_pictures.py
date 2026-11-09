"""Pictures (add-written-work 1.3): cleaning, PDF pages and the byte stores."""
import io
import urllib.error

import pytest
from PIL import Image

from mathly2 import pictures
from mathly2.pictures import MemoryPictures, PictureError, SupabasePictures, clean_image, render_pdf
from mathly2.store import InMemoryStore


def jpeg(size=(40, 20), color="red", exif=None, fmt="JPEG"):
    out = io.BytesIO()
    image = Image.new("RGB", size, color)
    kwargs = {"exif": exif} if exif is not None else {}
    image.save(out, fmt, **kwargs)
    return out.getvalue()


def test_a_jpeg_with_metadata_comes_back_without_it_and_upright():
    exif = Image.Exif()
    exif[0x0112] = 6                                                  # "rotate 90": a phone held sideways
    exif[0x010F] = "SecretPhone"                                      # a maker name that must not survive
    data = jpeg(size=(40, 20), exif=exif)
    assert b"SecretPhone" in data
    cleaned = clean_image(data, "image/jpeg")
    image = Image.open(io.BytesIO(cleaned))
    assert image.format == "JPEG" and image.size == (20, 40)           # turned upright: width and height swapped
    assert b"SecretPhone" not in cleaned and not image.getexif()


def test_png_and_webp_are_taken_and_transparency_becomes_white():
    out = io.BytesIO()
    Image.new("RGBA", (10, 10), (255, 0, 0, 0)).save(out, "PNG")      # fully transparent red
    cleaned = Image.open(io.BytesIO(clean_image(out.getvalue(), "image/png")))
    assert cleaned.format == "JPEG" and cleaned.getpixel((5, 5)) == (255, 255, 255)
    assert Image.open(io.BytesIO(clean_image(jpeg(fmt="WEBP"), "image/webp"))).format == "JPEG"


def test_a_picture_is_shrunk_to_a_sensible_size():
    big = Image.open(io.BytesIO(clean_image(jpeg(size=(4000, 3000)), "image/jpeg")))
    assert max(big.size) == pictures.MAX_SIDE


@pytest.mark.parametrize("data,kind,status,code", [
    (b"not an image", "image/jpeg", 400, "bad_image"),
    (b"%PDF-1.4 ...", "application/pdf", 415, "unsupported_image"),
    (b"", "image/gif", 415, "unsupported_image"),
    (b"x" * (pictures.MAX_IMAGE + 1), "image/jpeg", 413, "image_too_large"),
])
def test_what_is_not_an_image_or_is_too_large_is_refused(data, kind, status, code):
    with pytest.raises(PictureError) as caught:
        clean_image(data, kind)
    assert (caught.value.status, caught.value.code) == (status, code)


def test_a_png_sent_as_a_jpeg_and_an_image_with_too_many_pixels_are_refused():
    out = io.BytesIO()
    Image.new("RGB", (8, 8)).save(out, "PNG")
    with pytest.raises(PictureError) as wrong:
        clean_image(out.getvalue(), "image/jpeg")
    assert wrong.value.status == 415
    huge = io.BytesIO()
    Image.new("1", (6000, 4000)).save(huge, "PNG")                    # 24 million pixels, tiny file
    assert len(huge.getvalue()) < pictures.MAX_IMAGE
    with pytest.raises(PictureError) as bomb:
        clean_image(huge.getvalue(), "image/png")
    assert bomb.value.status == 400


def make_pdf(pages):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument.new()
    for _ in range(pages):
        doc.new_page(200, 300)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def test_a_pdf_gives_one_picture_per_page_and_bad_pdfs_are_refused():
    pages = render_pdf(make_pdf(3))
    assert len(pages) == 3 and all(Image.open(io.BytesIO(p)).format == "JPEG" for p in pages)
    assert Image.open(io.BytesIO(pages[0])).size[0] == pictures.PAGE_WIDTH
    for data, status in ((b"hello", 415), (b"%PDF-1.4 garbage", 400), (b"%PDF-" + b"0" * pictures.MAX_PDF, 413)):
        with pytest.raises(PictureError) as caught:
            render_pdf(data)
        assert caught.value.status == status


def test_too_many_pages_are_refused():
    with pytest.raises(PictureError) as caught:
        render_pdf(make_pdf(pictures.MAX_PAGES + 1))
    assert (caught.value.status, caught.value.code) == (413, "pdf_too_many_pages")


def test_the_memory_store_puts_gets_and_deletes_and_a_missing_one_is_404():
    m = MemoryPictures()
    m.put("a/1.jpg", b"bytes")
    assert m.get("a/1.jpg") == b"bytes"
    m.delete("a/1.jpg")
    m.delete("a/1.jpg")                                                # deleting twice is fine
    with pytest.raises(PictureError) as caught:
        m.get("a/1.jpg")
    assert caught.value.status == 404


def test_store_and_remove_a_picture_keep_the_row_and_drop_the_bytes():
    store, backend = InMemoryStore(), MemoryPictures()
    row = pictures.store_picture(store, backend, "user-1", "answer", b"jpegbytes")
    assert row["path"].startswith("user-1/") and row["size"] == 9 and backend.get(row["path"]) == b"jpegbytes" and store.get_picture(row["id"])["kind"] == "answer"
    pictures.remove_picture(store, backend, row)
    assert store.get_picture(row["id"])["deleted_at"] is not None
    with pytest.raises(PictureError):
        backend.get(row["path"])


class Calls:
    """A stand-in for the HTTP calls of SupabasePictures: records them and answers from a list."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, headers=None, body=None, timeout=10):
        self.calls.append((method, url, dict(headers or {}), body))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return 200, answer


def http_error(code):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b"{}"))


def test_supabase_pictures_make_a_private_bucket_once_then_store_read_and_delete(monkeypatch):
    calls = Calls([b"{}", b"{}", b"bytes", b"{}"])
    monkeypatch.setattr(pictures.pooled, "request", calls)
    s = SupabasePictures("https://p.test/", "secret", "m2-answers")
    s.put("user 1/a b.jpg", b"jpeg")
    s.put("user 1/c.jpg", b"jpeg2")                                    # the bucket is made only the first time
    assert [c[0] for c in calls.calls] == ["POST", "POST", "POST"] and calls.calls[0][1] == "https://p.test/storage/v1/bucket"
    assert b'"public": false' in calls.calls[0][3] and b"m2-answers" in calls.calls[0][3]
    assert calls.calls[1][1] == "https://p.test/storage/v1/object/m2-answers/user%201/a%20b.jpg" and calls.calls[1][3] == b"jpeg"
    assert calls.calls[1][2]["Authorization"] == "Bearer secret" and calls.calls[1][2]["Content-Type"] == "image/jpeg"
    calls.answers[:] = [b"bytes", b"{}"]
    assert s.get("user 1/c.jpg") == b"bytes"
    s.delete("user 1/c.jpg")
    assert calls.calls[-1][0] == "DELETE"


def test_an_existing_bucket_is_fine_and_storage_trouble_is_a_503_or_404(monkeypatch):
    monkeypatch.setattr(pictures.pooled, "request", Calls([http_error(409), b"{}"]))
    SupabasePictures("https://p.test", "k").put("a/1.jpg", b"x")        # "already exists" is not an error
    monkeypatch.setattr(pictures.pooled, "request", Calls([http_error(500)]))
    with pytest.raises(PictureError) as down:
        SupabasePictures("https://p.test", "k").put("a/1.jpg", b"x")
    assert down.value.status == 503
    s = SupabasePictures("https://p.test", "k")
    monkeypatch.setattr(pictures.pooled, "request", Calls([http_error(404)]))
    with pytest.raises(PictureError) as missing:
        s.get("a/1.jpg")
    assert missing.value.status == 404
    monkeypatch.setattr(pictures.pooled, "request", Calls([urllib.error.URLError("down")]))
    with pytest.raises(PictureError) as unreachable:
        s.get("a/1.jpg")
    assert unreachable.value.status == 503
    monkeypatch.setattr(pictures.pooled, "request", Calls([http_error(404)]))
    s.delete("a/1.jpg")                                                 # already gone is fine
