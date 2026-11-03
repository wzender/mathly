"""Tests run without sign-in regardless of the developer's local environment."""
import os

os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_PUBLISHABLE_KEY"] = ""
os.environ["VAPID_PRIVATE_KEY"] = ""   # push notifications are off unless a test turns them on
os.environ["MATHLY_ANSWER_BUCKET"] = ""   # answer images never go to a real Hugging Face bucket from a test
