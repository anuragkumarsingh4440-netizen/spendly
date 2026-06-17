"""Step 6 — pure date-helper tests (no DB, no Flask).

``resolve_range`` is exercised with an explicit ``today`` so the preset windows
are deterministic.
"""

from datetime import date

import pytest

from database.date_filter import is_valid_date, resolve_range

TODAY = date(2026, 6, 17)


# --------------------------------------------------------------------- #
# is_valid_date                                                         #
# --------------------------------------------------------------------- #

def test_is_valid_date_true():
    assert is_valid_date("2026-06-17") is True


@pytest.mark.parametrize("value", ["2026-13-01", "06/17/2026", "", None, "banana", 20260617])
def test_is_valid_date_false(value):
    assert is_valid_date(value) is False


# --------------------------------------------------------------------- #
# resolve_range — presets                                              #
# --------------------------------------------------------------------- #

def test_all_time():
    assert resolve_range(range_key="all_time", today=TODAY) == (None, None)


def test_this_month():
    assert resolve_range(range_key="this_month", today=TODAY) == ("2026-06-01", "2026-06-17")


def test_last_30_days():
    assert resolve_range(range_key="last_30_days", today=TODAY) == ("2026-05-19", "2026-06-17")


def test_this_year():
    assert resolve_range(range_key="this_year", today=TODAY) == ("2026-01-01", "2026-06-17")


def test_unknown_range_key():
    assert resolve_range(range_key="last_century", today=TODAY) == (None, None)


# --------------------------------------------------------------------- #
# resolve_range — explicit dates                                       #
# --------------------------------------------------------------------- #

def test_explicit_valid_pair():
    assert resolve_range(start="2026-03-01", end="2026-03-31", today=TODAY) == (
        "2026-03-01",
        "2026-03-31",
    )


def test_explicit_swapped_when_start_after_end():
    assert resolve_range(start="2026-03-31", end="2026-03-01", today=TODAY) == (
        "2026-03-01",
        "2026-03-31",
    )


def test_only_start_falls_back_to_all_time():
    assert resolve_range(start="2026-03-01", today=TODAY) == (None, None)


def test_malformed_start_falls_back_to_all_time():
    assert resolve_range(start="banana", end="2026-03-31", today=TODAY) == (None, None)


def test_explicit_dates_win_over_preset():
    assert resolve_range(
        range_key="this_month", start="2026-03-01", end="2026-03-31", today=TODAY
    ) == ("2026-03-01", "2026-03-31")


def test_no_input_is_all_time():
    assert resolve_range(today=TODAY) == (None, None)
