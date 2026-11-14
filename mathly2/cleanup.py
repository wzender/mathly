"""The hourly cleanup of pictures, and deleting a student's pictures on request. `python -m mathly2.cleanup` runs it once; the server runs it
every hour when it is connected to Supabase."""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from . import clock, pictures, retention

log = logging.getLogger("mathly.cleanup")


def run(store, backend, now: datetime | None = None) -> dict:
    """Remove pictures nothing refers to (after a day), answer pictures past their school year, and the pages of removed assignments.
    Returns how many of each were removed. A picture whose bytes cannot be deleted now is left for the next run."""
    now = now or clock.now()
    today = clock.school_day(now)
    removed = {"orphans": 0, "expired": 0, "removed_assignments": 0}
    for pic in store.pictures():
        refs = store.picture_refs(pic["id"])
        referenced = any(refs.values())
        if pic["kind"] in ("answer", "work") and retention.is_expired(clock.school_day(pic["created_at"]), today):
            reason = "expired"
        elif not referenced and now - pic["created_at"] > retention.ORPHAN_AGE:
            reason = "orphans"
        elif pic["kind"] == "page" and refs["assignments"] and all((store.get_assignment(a) or {}).get("removed_at") for a in refs["assignments"]):
            reason = "removed_assignments"
        else:
            continue
        try:
            pictures.remove_picture(store, backend, pic, now)
            removed[reason] += 1
        except pictures.PictureError as exc:
            log.warning("could not delete a picture (%s); it stays for the next run", exc.code)
    return removed


def delete_answer_pictures(store, backend, assignment_ids, user_id: str, now: datetime | None = None) -> int:
    """Delete a student's answer pictures for these assignments now (a teacher of the class, a manager or a developer asked). The submissions
    keep their grade and note. Returns how many pictures were deleted."""
    count = 0
    for sub in store.submissions_of_assignments(assignment_ids):
        if sub["user_id"] != user_id:
            continue
        for pid in sub["pictures"]:
            pic = store.get_picture(pid)
            if pic and pic["kind"] == "answer" and pic["owner_id"] == user_id and not pic["deleted_at"]:
                pictures.remove_picture(store, backend, pic, now)
                count += 1
    return count


def start_hourly(store, backend, every: float = 3600.0) -> threading.Event:
    """Run the cleanup now and then every `every` seconds in a background thread. Returns an event that stops it when set."""
    stop = threading.Event()

    def loop() -> None:
        while True:
            try:
                log.info("cleanup removed %s", run(store, backend))
            except Exception:                                    # a failed run must not stop the next one
                log.exception("the picture cleanup failed")
            if stop.wait(every):
                return

    threading.Thread(target=loop, name="picture-cleanup", daemon=True).start()
    return stop


def main() -> None:
    from .config import load_settings
    from .store import SupabaseStore
    settings = load_settings()
    if not settings.supabase_on:
        raise SystemExit("Set the Supabase settings: the cleanup works on the real database.")
    store = SupabaseStore(settings.supabase_url, settings.supabase_secret)
    backend = pictures.SupabasePictures(settings.supabase_url, settings.supabase_secret, settings.answer_bucket)
    print("Removed", run(store, backend))


if __name__ == "__main__":
    main()
