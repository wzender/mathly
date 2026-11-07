"""Settings, read from the environment when the app is created."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


def _emails(name: str) -> frozenset[str]:
    return frozenset(re.split(r"[\s,;]+", os.environ.get(name, "").strip().lower())) - {""}


@dataclass(frozen=True)
class Settings:
    supabase_url: str = ""
    supabase_key: str = ""         # publishable key, sent to the browser for Google sign-in
    supabase_secret: str = ""      # secret key, server only
    teachers: frozenset[str] = field(default_factory=frozenset)

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


def load_settings() -> Settings:
    env = lambda name: os.environ.get(name, "").strip()
    return Settings(
        supabase_url=env("SUPABASE_URL").rstrip("/"),
        supabase_key=env("SUPABASE_PUBLISHABLE_KEY"),
        supabase_secret=env("SUPABASE_SECRET_KEY"),
        teachers=_emails("TEACHER_EMAILS"),
    ).check()
