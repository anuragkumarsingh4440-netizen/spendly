"""Pure date-range helpers for the profile page filter (Step 6).

No Flask imports here — these are plain functions so the date logic can be
unit-tested in isolation and reused by the route and SQL layers. All dates are
ISO ``YYYY-MM-DD`` strings, which compare and sort lexicographically and so can
be passed straight into ``date BETWEEN ? AND ?`` clauses.
"""

from datetime import date, datetime, timedelta

# Preset range keys understood by ``resolve_range``. Anything else (including
# None) falls back to all-time, i.e. (None, None).
PRESETS = ("this_month", "last_30_days", "this_year", "all_time")


def is_valid_date(value):
    """Return True if ``value`` is a well-formed ``YYYY-MM-DD`` string."""
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _preset_range(range_key, today):
    """Resolve a preset key to a concrete ``(start, end)`` pair, or None."""
    if range_key == "all_time":
        return (None, None)
    if range_key == "this_month":
        start = today.replace(day=1)
        return (start.isoformat(), today.isoformat())
    if range_key == "last_30_days":
        # 30 inclusive days ending today => 29 days back.
        start = today - timedelta(days=29)
        return (start.isoformat(), today.isoformat())
    if range_key == "this_year":
        start = today.replace(month=1, day=1)
        return (start.isoformat(), today.isoformat())
    return None


def resolve_range(range_key=None, start=None, end=None, today=None):
    """Resolve filter inputs to a concrete ``(start, end)`` pair.

    Precedence and fail-safe rules (never raises):
    - An explicit, valid ``start`` *and* ``end`` pair wins over any preset; if
      ``start > end`` the two are swapped.
    - Otherwise a recognised ``range_key`` preset is resolved against ``today``.
    - Anything else — only one bound, a malformed bound, an unknown preset, or
      no input at all — yields ``(None, None)`` (all-time).
    """
    today = today or date.today()

    # Explicit dates take precedence, but only when both are present and valid.
    if start is not None or end is not None:
        if is_valid_date(start) and is_valid_date(end):
            if start > end:
                start, end = end, start
            return (start, end)
        # Partial or malformed explicit input falls through to the preset check
        # below. If no valid range_key is present there, the result is all-time.

    if range_key in PRESETS:
        resolved = _preset_range(range_key, today)
        if resolved is not None:
            return resolved

    return (None, None)
