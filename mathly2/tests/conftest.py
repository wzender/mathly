"""Tests run without Supabase regardless of the developer's local environment."""
import os

for name in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "TEACHER_EMAILS"):
    os.environ[name] = ""
