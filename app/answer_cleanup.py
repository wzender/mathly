"""Run hourly: python -m app.answer_cleanup (same server-only configuration)."""
from pathlib import Path

from dotenv import load_dotenv

from .answer_scans import AnswerScans, ScanError
from .auth import load_auth


def main():
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
    try:
        # Rollback disables student access, not deletion of orphaned private data.
        removed = AnswerScans(load_auth(), enabled=True).cleanup()
    except ScanError as exc:
        raise SystemExit('Answer cleanup failed: ' + exc.code) from None
    print(f'Removed {removed} unreferenced answer images.')


if __name__ == '__main__':
    main()
