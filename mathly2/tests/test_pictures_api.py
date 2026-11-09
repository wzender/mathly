"""Pictures through the API (add-written-work 2.1): upload, the access rules, and the bytes only ever coming through the server."""
import io
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore

TEACHER, OTHER_TEACHER, KID, KID2, OUTSIDER, MGR, DEV = ("t@school.test", "t2@school.test", "kid@school.test", "kid2@school.test", "out@school.test",
                                                           "mgr@school.test", "dev@school.test")
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))


def uid(email):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def jpeg_bytes(color="red", size=(60, 40), secret=None):
    out = io.BytesIO()
    exif = Image.Exif()
    if secret:
        exif[0x010F] = secret
    Image.new("RGB", size, color).save(out, "JPEG", exif=exif)
    return out.getvalue()


@pytest.fixture
def world():
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    a = store.create_class("setup", "A", lessons=["t"], teacher_email=TEACHER)
    b = store.create_class("setup", "B", lessons=["t"], teacher_email=OTHER_TEACHER)
    for email in (KID, KID2):
        store.add_member(a["id"], email)
    store.add_member(b["id"], OUTSIDER)
    app = create_app(Settings(developers=frozenset({DEV})), bank=load_bank(), store=store)
    client = TestClient(app)
    client.store, client.backend, client.class_a = store, app.state.pictures, a["id"]
    return client


def upload(client, who=KID, data=None, kind="image/jpeg"):
    return client.post("/api/pictures", content=data if data is not None else jpeg_bytes(), headers={**auth(who), "Content-Type": kind})


def test_an_upload_is_cleaned_and_stored_and_the_uploader_reads_it_back(world):
    got = upload(world, data=jpeg_bytes(secret="SecretPhone"))
    assert got.status_code == 201
    body = got.json()
    assert set(body) == {"id", "size"} and "path" not in body                              # no storage name is ever given out
    row = world.store.get_picture(body["id"])
    assert row["owner_id"] == KID_ID and row["kind"] == "answer" and row["size"] == body["size"]
    assert b"SecretPhone" not in world.backend.get(row["path"])
    read = world.get(f"/api/pictures/{body['id']}", headers=auth(KID))
    assert read.status_code == 200 and read.headers["content-type"] == "image/jpeg" and Image.open(io.BytesIO(read.content)).size == (60, 40)
    assert "location" not in read.headers and row["path"] not in str(read.headers)


def test_not_an_image_the_wrong_type_and_too_large_are_refused_and_nothing_is_stored(world):
    assert upload(world, data=b"hello", kind="image/jpeg").status_code == 400
    assert upload(world, data=jpeg_bytes(), kind="application/pdf").status_code == 415
    assert upload(world, data=b"x" * 6_000_000).status_code == 413
    assert world.store.pictures(include_deleted=True) == [] and world.backend.files == {}


def test_a_signed_out_request_and_a_person_in_no_class_cannot_upload(world):
    assert world.post("/api/pictures", content=jpeg_bytes(), headers={"Content-Type": "image/jpeg"}).status_code == 401
    assert upload(world, who="nobody@school.test").status_code == 403


def hand_in(world, who=KID):
    pic = upload(world, who).json()["id"]
    a = world.store.create_assignment(world.class_a, "דף", date(2026, 12, 1), TEACHER, "quiz", quiz_lesson="t")
    world.store.save_submission(a["id"], uid(who), pictures=[pic])
    return pic


def test_who_can_read_a_handed_in_answer_picture(world):
    pic = hand_in(world)
    get = lambda who: world.get(f"/api/pictures/{pic}", headers=auth(who)).status_code
    assert get(KID) == 200 and get(TEACHER) == 200 and get(DEV) == 200                           # the owner, the class's teacher, a developer
    assert get(MGR) == 403                                                                      # a manager has no learning data
    assert get(KID2) == 404 and get(OUTSIDER) == 404 and get(OTHER_TEACHER) == 404            # another student, another class, another class's teacher
    assert world.get(f"/api/pictures/{pic}").status_code == 401


def test_a_picture_nothing_refers_to_is_only_the_uploaders(world):
    pic = upload(world).json()["id"]
    get = lambda who: world.get(f"/api/pictures/{pic}", headers=auth(who)).status_code
    assert get(KID) == 200 and get(TEACHER) == 404 and get(KID2) == 404 and get(DEV) == 200


def test_a_page_of_an_assignment_is_read_by_the_classs_students_and_teacher_only(world):
    page = world.store.create_picture(TEACHER, "page", "t/1.jpg", "image/jpeg", 10)
    world.backend.put("t/1.jpg", jpeg_bytes("blue"))
    world.store.create_assignment(world.class_a, "דף", date(2026, 12, 1), TEACHER, "pages", pages=[page["id"]])
    get = lambda who: world.get(f"/api/pictures/{page['id']}", headers=auth(who)).status_code
    assert get(KID) == 200 and get(KID2) == 200 and get(TEACHER) == 200
    assert get(OUTSIDER) == 404 and get(OTHER_TEACHER) == 404


def test_a_deleted_picture_is_gone_and_an_unknown_one_is_404(world):
    pic = hand_in(world)
    world.store.mark_picture_deleted(pic)
    assert world.get(f"/api/pictures/{pic}", headers=auth(KID)).status_code == 410
    assert world.get("/api/pictures/not-an-id", headers=auth(KID)).status_code == 404
    assert world.get(f"/api/pictures/{uuid.uuid4()}", headers=auth(KID)).status_code == 404


def test_storage_trouble_is_a_503_with_a_hebrew_message(world):
    from mathly2.pictures import PictureError

    class Down:
        def put(self, *a, **k):
            raise PictureError(503, "answer_storage_unavailable")
    world.app.state.pictures = Down()
    got = upload(world)
    assert got.status_code == 503 and "האחסון" in got.json()["detail"]
