"""Which version of the code is running and when it was last updated, for the developer's status card.

A deployment writes `mathly2/version.json` ({"commit", "date", "title"}) when it builds (the Hugging Face sync does). Without it, as in a
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
    if not isinstance(data, dict):
        return None
    commit, date, title = data.get("commit"), data.get("date"), data.get("title")
    if not isinstance(commit, str) or not commit:
        return None
    return {"commit": commit, "date": date, "title": title[:200] if isinstance(title, str) and title.strip() else None}


def _from_git(folder: Path) -> dict | None:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%H%n%cI%n%s"], cwd=folder, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.splitlines()
    if out.returncode != 0 or len(lines) < 2 or not lines[0].strip():
        return None
    title = lines[2].strip()[:200] if len(lines) > 2 and lines[2].strip() else None
    return {"commit": lines[0].strip(), "date": lines[1].strip(), "title": title}


def read(path: Path = FILE, folder: Path = HERE) -> dict:
    """{"commit", "short", "date", "title", "source"}: the title is the change's name (the commit's subject line); source is "file",
    "git" or None when nothing is known."""
    found, source = _from_file(path), "file"
    if not found:
        found, source = _from_git(folder), "git"
    if not found:
        return {"commit": None, "short": None, "date": None, "title": None, "source": None}
    return {**found, "short": found["commit"][:7], "source": source}
