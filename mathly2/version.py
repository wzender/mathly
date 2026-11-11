"""Which version of the code is running and when it was last updated, for the developer's status card.

A deployment writes `mathly2/version.json` ({"commit", "date"}) when it builds (the Hugging Face sync does). Without it, as in a
local checkout, the last git commit is read instead; with neither, both are None. Read once, when the server starts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "version.json"


def _from_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    commit, date = data.get("commit"), data.get("date")
    return {"commit": commit, "date": date} if isinstance(commit, str) and commit else None


def _from_git(folder: Path) -> dict | None:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%H%n%cI"], cwd=folder, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.split()
    return {"commit": lines[0], "date": lines[1]} if out.returncode == 0 and len(lines) == 2 else None


def read(path: Path = FILE, folder: Path = HERE) -> dict:
    """{"commit", "short", "date", "source"}: source is "file", "git" or None when nothing is known."""
    found, source = _from_file(path), "file"
    if not found:
        found, source = _from_git(folder), "git"
    if not found:
        return {"commit": None, "short": None, "date": None, "source": None}
    return {**found, "short": found["commit"][:7], "source": source}
