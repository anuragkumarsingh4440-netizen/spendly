"""Step 6 — date-scoped query-helper tests.

Expected values are computed from the seeded temp DB with raw SQL, so the tests
stay correct regardless of what ``seed_db()`` contains. A subset window is
derived from the actual seed dates rather than hardcoded.
"""

import pytest

from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

# A range guaranteed to contain no seed expenses (seed data is in 2026).
EMPTY_START, EMPTY_END = "1990-01-01", "1990-12-31"


def _seed_dates(raw_conn, user_id):
    rows = raw_conn.execute(
        "SELECT DISTINCT date FROM expenses WHERE user_id = ? ORDER BY date",
        (user_id,),
    ).fetchall()
    return [r["date"] for r in rows]


def _subset_window(raw_conn, user_id):
    """A range covering the earliest few seed dates but not all of them."""
    dates = _seed_dates(raw_conn, user_id)
    assert len(dates) >= 3, "seed data should span several dates"
    return dates[0], dates[len(dates) // 2]


# --------------------------------------------------------------------- #
# get_summary_stats                                                     #
# --------------------------------------------------------------------- #

def test_summary_full_range_matches_all_time(seed_user_id, raw_conn):
    dates = _seed_dates(raw_conn, seed_user_id)
    scoped = get_summary_stats(seed_user_id, start=dates[0], end=dates[-1])
    all_time = get_summary_stats(seed_user_id)
    assert scoped == all_time


def test_summary_subset(seed_user_id, raw_conn):
    start, end = _subset_window(raw_conn, seed_user_id)
    exp_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE user_id = ? AND date BETWEEN ? AND ?",
        (seed_user_id, start, end),
    ).fetchone()[0]
    exp_count = raw_conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?",
        (seed_user_id, start, end),
    ).fetchone()[0]

    stats = get_summary_stats(seed_user_id, start=start, end=end)
    assert stats["total_spent"] == exp_total
    assert stats["transaction_count"] == exp_count
    assert 0 < stats["transaction_count"] < len(_seed_dates(raw_conn, seed_user_id)) + 1


def test_summary_empty_range(seed_user_id):
    assert get_summary_stats(seed_user_id, start=EMPTY_START, end=EMPTY_END) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


# --------------------------------------------------------------------- #
# get_recent_transactions                                               #
# --------------------------------------------------------------------- #

def test_recent_subset_in_range_and_ordered(seed_user_id, raw_conn):
    start, end = _subset_window(raw_conn, seed_user_id)
    txns = get_recent_transactions(seed_user_id, start=start, end=end)
    assert txns, "subset window should contain expenses"
    for t in txns:
        assert start <= t["date"] <= end
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)  # newest first


def test_recent_empty_range(seed_user_id):
    assert get_recent_transactions(seed_user_id, start=EMPTY_START, end=EMPTY_END) == []


# --------------------------------------------------------------------- #
# get_category_breakdown                                                #
# --------------------------------------------------------------------- #

def test_breakdown_subset_pct_sums_to_100(seed_user_id, raw_conn):
    start, end = _subset_window(raw_conn, seed_user_id)
    breakdown = get_category_breakdown(seed_user_id, start=start, end=end)
    assert breakdown
    amounts = [item["amount"] for item in breakdown]
    assert amounts == sorted(amounts, reverse=True)
    assert sum(item["pct"] for item in breakdown) == 100


def test_breakdown_empty_range(seed_user_id):
    assert get_category_breakdown(seed_user_id, start=EMPTY_START, end=EMPTY_END) == []


# --------------------------------------------------------------------- #
# No regression: None bounds == Step 5 behaviour                       #
# --------------------------------------------------------------------- #

def test_none_bounds_match_step5(seed_user_id):
    assert get_summary_stats(seed_user_id, None, None) == get_summary_stats(seed_user_id)
    assert get_recent_transactions(seed_user_id, start=None, end=None) == \
        get_recent_transactions(seed_user_id)
    assert get_category_breakdown(seed_user_id, None, None) == \
        get_category_breakdown(seed_user_id)
