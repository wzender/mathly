"""Tests run without sign-in regardless of the developer's local environment."""
import os

os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_PUBLISHABLE_KEY"] = ""
