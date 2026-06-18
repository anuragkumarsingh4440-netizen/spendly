"""Step 8 — /expenses/<id>/edit route + get_expense_by_id tests.

Ownership is the central concern: a user may only read/update their own
expenses. Expected values and ids are derived from the seeded temp DB.
"""

import re

import pytest

from database.queries import get_expense_by_id


# --- helpers ------------------------------------------------------------ #

def _an_expense(raw_conn, user_id):
    """An existing expense row (dict-like) owned by user_id."""
    return raw_conn.execute(
        "SELECT id, amount, category, date, description FROM expenses "
        "WHERE user_id = ? ORDER BY id LIMIT 1",
        (user_id,),
    ).fetchone()


def _row(raw_conn, expense_id):
    return raw_conn.execute(
        "SELECT id, user_id, amount, category, date, description "
        "FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()


def _count(raw_conn, user_id):
    return raw_conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def _other_users_expense(raw_conn):
    """Create a second user with one expense; return (user_id, expense_id)."""
    cur = raw_conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Other User", "other@spendly.com", "x"),
    )
    raw_conn.commit()
    other_id = cur.lastrowid
    cur2 = raw_conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (other_id, 77.00, "Food", "2026-06-01", "Other lunch"),
    )
    raw_conn.commit()
    return other_id, cur2.lastrowid


def _form_from(row, **overrides):
    """Build a complete valid edit form from an existing row, applying changes."""
    form = {
        "amount": str(row["amount"]),
        "category": row["category"],
        "date": row["date"],
        "description": row["description"] or "",
    }
    form.update(overrides)
    return form


# --- unit: get_expense_by_id ------------------------------------------- #

def test_get_expense_by_id_owned(seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    result = get_expense_by_id(row["id"], seed_user_id)
    assert result is not None
    assert set(result.keys()) == {"id", "amount", "category", "date", "description"}
    assert result["id"] == row["id"]
    assert result["category"] == row["category"]


def test_get_expense_by_id_other_user_returns_none(seed_user_id, raw_conn):
    _other_id, other_expense_id = _other_users_expense(raw_conn)
    # Seed user must not be able to read another user's expense.
    assert get_expense_by_id(other_expense_id, seed_user_id) is None


def test_get_expense_by_id_missing_returns_none(seed_user_id):
    assert get_expense_by_id(999999, seed_user_id) is None


# --- GET /expenses/<id>/edit ------------------------------------------- #

def test_get_requires_login(client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    resp = client.get(f"/expenses/{row['id']}/edit")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_renders_prefilled_form(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    resp = auth_client.get(f"/expenses/{row['id']}/edit")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert f'value="{row["amount"]}"' in body
    assert f'value="{row["date"]}"' in body
    # The expense's category option is the selected one.
    assert re.search(rf'value="{re.escape(row["category"])}"\s+selected', body)
    if row["description"]:
        assert row["description"] in body


def test_get_other_users_expense_404(auth_client, raw_conn):
    _other_id, other_expense_id = _other_users_expense(raw_conn)
    resp = auth_client.get(f"/expenses/{other_expense_id}/edit")
    assert resp.status_code == 404


def test_get_missing_expense_404(auth_client):
    resp = auth_client.get("/expenses/999999/edit")
    assert resp.status_code == 404


# --- POST /expenses/<id>/edit: success --------------------------------- #

def test_post_valid_updates_in_place(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    before_count = _count(raw_conn, seed_user_id)

    resp = auth_client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, amount="123.45", category="Health"),
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    after = _row(raw_conn, row["id"])
    assert after["amount"] == 123.45
    assert after["category"] == "Health"
    assert after["user_id"] == seed_user_id          # ownership unchanged
    assert _count(raw_conn, seed_user_id) == before_count  # no new row


def test_post_change_reflected_on_profile(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    before_total = raw_conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ?", (seed_user_id,)
    ).fetchone()[0]
    new_amount = row["amount"] + 100.00

    auth_client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, amount=str(new_amount)),
    )

    after_total = raw_conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ?", (seed_user_id,)
    ).fetchone()[0]
    assert after_total == before_total + 100.00

    body = auth_client.get("/profile").get_data(as_text=True)
    assert ("%.2f" % after_total) in body


def test_post_clear_description_stores_null(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    auth_client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, description=""),
    )
    assert _row(raw_conn, row["id"])["description"] is None


def test_post_normalises_unpadded_date(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    auth_client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, date="2026-6-8"),
    )
    assert _row(raw_conn, row["id"])["date"] == "2026-06-08"


# --- POST: validation failures (row unchanged) ------------------------- #

@pytest.mark.parametrize("amount,message", [
    ("", "Please enter a valid amount."),
    ("abc", "Please enter a valid amount."),
    ("0", "Amount must be greater than zero."),
    ("-5", "Amount must be greater than zero."),
    ("inf", "Amount must be greater than zero."),
    ("nan", "Amount must be greater than zero."),
])
def test_post_invalid_amount_rejected(auth_client, seed_user_id, raw_conn, amount, message):
    row = _an_expense(raw_conn, seed_user_id)
    before = dict(_row(raw_conn, row["id"]))
    resp = auth_client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, amount=amount),
    )
    assert resp.status_code == 200
    assert message in resp.get_data(as_text=True)
    assert dict(_row(raw_conn, row["id"])) == before


def test_post_bad_category_rejected(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    before = dict(_row(raw_conn, row["id"]))
    resp = auth_client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, category="Crypto"),
    )
    assert resp.status_code == 200
    assert "Please choose a valid category." in resp.get_data(as_text=True)
    assert dict(_row(raw_conn, row["id"])) == before


def test_post_malformed_date_rejected(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    before = dict(_row(raw_conn, row["id"]))
    resp = auth_client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, date="banana"),
    )
    assert resp.status_code == 200
    assert "Please enter a valid date." in resp.get_data(as_text=True)
    assert dict(_row(raw_conn, row["id"])) == before


def test_post_failure_preserves_submitted_values(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    resp = auth_client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, amount="55.55", category="Crypto"),
    )
    assert resp.status_code == 200
    assert 'value="55.55"' in resp.get_data(as_text=True)


# --- POST: ownership / auth -------------------------------------------- #

def test_post_other_users_expense_404_and_unchanged(auth_client, raw_conn):
    _other_id, other_expense_id = _other_users_expense(raw_conn)
    before = dict(_row(raw_conn, other_expense_id))
    resp = auth_client.post(
        f"/expenses/{other_expense_id}/edit",
        data={"amount": "999.99", "category": "Shopping",
              "date": "2026-06-02", "description": "hijack"},
    )
    assert resp.status_code == 404
    assert dict(_row(raw_conn, other_expense_id)) == before


def test_post_requires_login(client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    before = dict(_row(raw_conn, row["id"]))
    resp = client.post(
        f"/expenses/{row['id']}/edit",
        data=_form_from(row, amount="1.00"),
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert dict(_row(raw_conn, row["id"])) == before
