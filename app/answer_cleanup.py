"""Run hourly: python -m app.answer_cleanup (same server-only configuration). Removes unreferenced answer images
and worksheets that no assignment uses."""
from pathlib import Path

from dotenv import load_dotenv

from .answer_scans import AnswerScans, ScanError
from .assignments import Assignments, AssignmentsUnavailable
from .auth import load_auth
from .worksheets import Worksheets, WorksheetsUnavailable, cleanup_unused


def main():
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
    auth = load_auth()
    failed = []
    try:
        # Rollback disables student access, not deletion of orphaned private data.
        removed = AnswerScans(auth, enabled=True).cleanup()
        print(f'Removed {removed} unreferenced answer images.')
    except ScanError as exc:
        failed.append('answers: ' + exc.code)
    try:   # worksheets uploaded a day ago that no assignment uses (app/worksheets.py)
        removed = cleanup_unused(Worksheets(auth), Assignments(auth))
        print(f'Removed {removed} unused worksheets.')
    except (WorksheetsUnavailable, AssignmentsUnavailable) as exc:
        failed.append('worksheets: ' + str(exc))
    if failed:
        raise SystemExit('Cleanup failed: ' + '; '.join(failed))


if __name__ == '__main__':
    main()
