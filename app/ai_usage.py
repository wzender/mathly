"""What the Claude API costs: each call's tokens and estimated dollars, kept in the Supabase table `math_ai_usage`.

Photo help (math_photo.py) and answer grading (answer_grading.py) attach a "usage" dict to their result; the routes
pop it and call record(). Saving runs in the background and never fails a student's request.

The cost is an estimate from the list prices below (USD per million tokens, Anthropic API, November 2026).
The Anthropic Console's Cost page is the real bill.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from .auth import AuthUnavailable

log = logging.getLogger("mathly.ai_usage")
MIGRATION = "supabase/migrations/20261103220000_math_ai_usage.sql"
TABLE = "/rest/v1/math_ai_usage"
FEATURES = ("photo", "grading", "prompter")

# model prefix -> (input, output, cache read) in USD per million tokens. A cache write is 1.25 x input.
PRICES = {
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-fable-5": (10.00, 50.00, 1.00),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4": (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    "claude-sonnet-4": (3.00, 15.00, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-haiku-4": (1.00, 5.00, 0.10),
}
UNKNOWN = PRICES["claude-opus-5-5"]   # an unlisted model is priced as the app's default

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-usage")
_warned_missing = False


def prices(model: str) -> tuple[float, float, float]:
    # Longest prefix first, so "claude-opus-5-5" wins over "claude-opus-5".
    for prefix in sorted(PRICES, key=len, reverse=True):
        if model.startswith(prefix):
            return PRICES[prefix]
    return UNKNOWN


def usage_of(response) -> dict | None:
    """The tokens of an API response, or None when it has no usage (test fakes)."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    tokens = {name: int(getattr(usage, field, 0) or 0) for name, field in (
        ("input_tokens", "input_tokens"), ("output_tokens", "output_tokens"),
        ("cache_read_tokens", "cache_read_input_tokens"), ("cache_write_tokens", "cache_creation_input_tokens"))}
    return {"model": str(getattr(response, "model", "") or "unknown")[:100], **tokens}


def cost(usage: dict) -> float:
    inp, out, read = prices(usage.get("model", ""))
    return round((usage.get("input_tokens", 0) * inp + usage.get("output_tokens", 0) * out
                  + usage.get("cache_read_tokens", 0) * read
                  + usage.get("cache_write_tokens", 0) * inp * 1.25) / 1_000_000, 6)


def record(auth, user_id: str | None, feature: str, usage: dict | None) -> None:
    """Save one call's usage in the background. Does nothing without usage or a database."""
    if not usage or auth is None or not getattr(auth, "secret", None) or feature not in FEATURES:
        return
    row = {"user_id": user_id or None, "feature": feature, **usage, "cost_usd": cost(usage)}
    log.info("claude %s: %s, %d in + %d out tokens, ~$%.4f", feature, usage["model"],
             usage["input_tokens"], usage["output_tokens"], row["cost_usd"])
    _pool.submit(_save, auth, row)


def _save(auth, row: dict) -> None:
    global _warned_missing
    try:
        auth._admin(TABLE, "POST", row, prefer="return=minimal")
    except AuthUnavailable as exc:
        if "answered 404" in str(exc):
            if not _warned_missing:
                log.warning("the math_ai_usage table is missing; apply %s", MIGRATION)
                _warned_missing = True
        else:
            log.warning("Claude usage not saved: %s", exc)
    except Exception as exc:   # never let bookkeeping take anything down
        log.warning("Claude usage not saved: %s", type(exc).__name__)


def summary(auth, days: int = 30) -> dict:
    """Totals for the last `days` days: overall, per feature, per model, and today."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = auth._admin(f"{TABLE}?select=created_at,feature,model,input_tokens,output_tokens,"
                       f"cache_read_tokens,cache_write_tokens,cost_usd"
                       f"&created_at=gte.{since.isoformat().replace('+', '%2B')}&order=created_at.desc&limit=50000") or []
    today = datetime.now(timezone.utc).date().isoformat()

    def empty():
        return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_tokens": 0, "cost_usd": 0.0}

    total, day, by_feature, by_model = empty(), empty(), {}, {}
    for row in rows:
        for bucket in (total, by_feature.setdefault(row["feature"], empty()), by_model.setdefault(row["model"], empty()),
                       *((day,) if str(row["created_at"]).startswith(today) else ())):
            bucket["calls"] += 1
            bucket["input_tokens"] += row.get("input_tokens") or 0
            bucket["output_tokens"] += row.get("output_tokens") or 0
            bucket["cache_tokens"] += (row.get("cache_read_tokens") or 0) + (row.get("cache_write_tokens") or 0)
            bucket["cost_usd"] += float(row.get("cost_usd") or 0)
    for bucket in (total, day, *by_feature.values(), *by_model.values()):
        bucket["cost_usd"] = round(bucket["cost_usd"], 4)
    return {"days": days, "total": total, "today": day, "by_feature": by_feature, "by_model": by_model}
