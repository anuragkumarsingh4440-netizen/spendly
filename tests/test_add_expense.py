"""Step 7 — /expenses/add route tests.

Expected values are derived from the seeded temp DB; new rows are verified
through a raw connection rather than trusting the route's own queries.
"""

from datetime import date

import pytest

from database.db import CATEGORIES


def _row_count(raw_conn, user_id):
    return raw_conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def _latest_expense(raw_conn, user_id):
    """The most recently inserted expense row for a user (highest id)."""
    return raw_conn.execute(
        "SELECT amount, category, date, description FROM expenses "
        "WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def _post(client, **overrides):
    """Build a valid add-expense form, applying any field overrides."""
    form = {
        "amount": "12.50",
        "category": "Food",
        "date": "2026-06-15",
        "description": "Lunch",
    }
    form.update(overrides)
    return client.post("/expenses/add", data=form)


# --- GET ---------------------------------------------------------------- #

def test_get_requires_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_renders_form_with_categories_and_today(auth_client):
    resp = auth_client.get("/expenses/add")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # All form fields are present.
    assert 'name="amount"' in body
    assert 'name="category"' in body
    assert 'name="date"' in body
    assert 'name="description"' in body

    # Every category is offered.
    for category in CATEGORIES:
        assert category in body

    # The date input defaults to today.
    assert date.today().isoformat() in body


# --- POST: success paths ------------------------------------------------ #

def test_post_valid_inserts_row_and_redirects(auth_client, seed_user_id, raw_conn):
    before = _row_count(raw_conn, seed_user_id)
    resp = _post(auth_client, amount="42.75", category="Transport",
                 date="2026-06-09", description="Taxi")
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    assert _row_count(raw_conn, seed_user_id) == before + 1
    row = _latest_expense(raw_conn, seed_user_id)
    assert row["amount"] == 42.75
    assert row["category"] == "Transport"
    assert row["date"] == "2026-06-09"
    assert row["description"] == "Taxi"


def test_post_appears_on_profile(auth_client, seed_user_id, raw_conn):
    before_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]

    _post(auth_client, amount="99.00", category="Shopping",
          date="2026-06-11", description="Backpack")

    resp = auth_client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    after_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]

    assert after_total == before_total + 99.00
    assert ("%.2f" % after_total) in body
    assert "Backpack" in body


def test_post_empty_description_stored_as_null(auth_client, seed_user_id, raw_conn):
    _post(auth_client, description="")
    row = _latest_expense(raw_conn, seed_user_id)
    assert row["description"] is None


def test_post_normalises_unpadded_date(auth_client, seed_user_id, raw_conn):
    _post(auth_client, date="2026-6-8")
    row = _latest_expense(raw_conn, seed_user_id)
    assert row["date"] == "2026-06-08"


# --- POST: validation failures (no row written, form re-rendered) ------- #

@pytest.mark.parametrize("amount", ["", "abc"])
def test_post_invalid_amount_rejected(auth_client, seed_user_id, raw_conn, amount):
    before = _row_count(raw_conn, seed_user_id)
    resp = _post(auth_client, amount=amount)
    assert resp.status_code == 200
    assert "Please enter a valid amount." in resp.get_data(as_text=True)
    assert _row_count(raw_conn, seed_user_id) == before


@pytest.mark.parametrize("amount", ["0", "-5", "inf", "nan"])
def test_post_non_positive_amount_rejected(auth_client, seed_user_id, raw_conn, amount):
    before = _row_count(raw_conn, seed_user_id)
    resp = _post(auth_client, amount=amount)
    assert resp.status_code == 200
    assert "Amount must be greater than zero." in resp.get_data(as_text=True)
    assert _row_count(raw_conn, seed_user_id) == before


def test_post_bad_category_rejected(auth_client, seed_user_id, raw_conn):
    before = _row_count(raw_conn, seed_user_id)
    resp = _post(auth_client, category="Crypto")
    assert resp.status_code == 200
    assert "Please choose a valid category." in resp.get_data(as_text=True)
    assert _row_count(raw_conn, seed_user_id) == before


def test_post_malformed_date_rejected(auth_client, seed_user_id, raw_conn):
    before = _row_count(raw_conn, seed_user_id)
    resp = _post(auth_client, date="banana")
    assert resp.status_code == 200
    assert "Please enter a valid date." in resp.get_data(as_text=True)
    assert _row_count(raw_conn, seed_user_id) == before


def test_post_failure_preserves_submitted_values(auth_client):
    # Bad category so the amount survives to the re-rendered form.
    resp = _post(auth_client, amount="33.33", category="Crypto")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'value="33.33"' in body


# --- POST: auth ---------------------------------------------------------- #

def test_post_requires_login(client, seed_user_id, raw_conn):
    before = _row_count(raw_conn, seed_user_id)
    resp = _post(client)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _row_count(raw_conn, seed_user_id) == before
