"""Settings, read from the environment when the app is created."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).parent / ".env"            # this app's own settings, if it has any
ROOT_ENV_FILE = Path(__file__).parent.parent / ".env"   # the repository's .env, shared with mathly1 (same Supabase project)


def _emails(name: str) -> frozenset[str]:
    return frozenset(re.split(r"[\s,;]+", os.environ.get(name, "").strip().lower())) - {""}


@dataclass(frozen=True)
class Settings:
    supabase_url: str = ""
    supabase_key: str = ""         # publishable key, sent to the browser for Google sign-in
    supabase_secret: str = ""      # secret key, server only
    teachers: frozenset[str] = field(default_factory=frozenset)
    developers: frozenset[str] = field(default_factory=frozenset)   # the developer role comes only from here
    admins: frozenset[str] = field(default_factory=frozenset)       # the first admins; others are given the role by an admin
    answer_bucket: str = "m2-answers"                               # the private bucket for answer pictures (not mathly1's)
    anthropic_key: str = ""                                         # the AI is unavailable without it (a send fails with "missing key")
    math_model: str = ""                                            # empty: the default model in ai.py
    cache_seconds: float = 30                                       # how long slow-changing reads are remembered; 0 is off
    vapid_private_key: str = ""                                     # the server's push key; push notifications are off without it
    vapid_subject: str = ""                                         # a contact the push services may write to ("mailto:...")

    @property
    def supabase_on(self) -> bool:
        return bool(self.supabase_url and self.supabase_key and self.supabase_secret)

    def check(self) -> "Settings":
        """Either all three Supabase settings are set, or none (local development with the "dev only" sign-in).
        A half-configured server must not fall back to dev sign-in, which trusts any email address."""
        given = [bool(self.supabase_url), bool(self.supabase_key), bool(self.supabase_secret)]
        if any(given) and not all(given):
            raise ValueError("Set all of SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY and SUPABASE_SECRET_KEY, or none of them.")
        return self


def load_settings(env_file: Path | None = None) -> Settings:
    """Settings from the environment. Files fill in what the environment does not set, in this order: mathly2/.env, then the
    repository's .env. A real environment variable always wins, so deployments are unaffected. Passing `env_file` reads only that file."""
    for path in ([env_file] if env_file else [ENV_FILE, ROOT_ENV_FILE]):
        load_dotenv(path, override=False)
    env = lambda name: os.environ.get(name, "").strip()
    return Settings(
        supabase_url=env("SUPABASE_URL").rstrip("/"),
        supabase_key=env("SUPABASE_PUBLISHABLE_KEY"),
        supabase_secret=env("SUPABASE_SECRET_KEY"),
        teachers=_emails("TEACHER_EMAILS"),
        developers=_emails("DEVELOPER_EMAILS"),
        admins=_emails("ADMIN_EMAILS"),
        answer_bucket=env("MATHLY_M2_ANSWER_BUCKET") or "m2-answers",
        anthropic_key=env("ANTHROPIC_API_KEY"),
        math_model=env("MATH_MODEL"),
        cache_seconds=float(env("MATHLY_CACHE_SECONDS") or 30),
        vapid_private_key=env("VAPID_PRIVATE_KEY"),
        vapid_subject=env("VAPID_SUBJECT"),
    ).check()
