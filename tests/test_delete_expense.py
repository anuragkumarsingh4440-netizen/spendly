"""Step 9 — /expenses/<id>/delete route tests.

Delete is POST-only and ownership-scoped: a user may only delete their own
expenses, a GET must never delete, and a missing/cross-user id returns 404.
Ids and expected values are derived from the seeded temp DB.
"""


def _an_expense(raw_conn, user_id):
    """An existing expense row (dict-like) owned by user_id."""
    return raw_conn.execute(
        "SELECT id, amount, category, date, description FROM expenses "
        "WHERE user_id = ? ORDER BY id LIMIT 1",
        (user_id,),
    ).fetchone()


def _exists(raw_conn, expense_id):
    return raw_conn.execute(
        "SELECT 1 FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone() is not None


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


# --- success ------------------------------------------------------------ #

def test_delete_own_expense_removes_row(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    before = _count(raw_conn, seed_user_id)

    resp = auth_client.post(f"/expenses/{row['id']}/delete")
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    assert not _exists(raw_conn, row["id"])
    assert _count(raw_conn, seed_user_id) == before - 1


def test_delete_reflected_on_profile(auth_client, seed_user_id, raw_conn):
    # Pick an expense with a distinctive description so we can assert absence.
    row = raw_conn.execute(
        "SELECT id, amount, description FROM expenses "
        "WHERE user_id = ? AND description IS NOT NULL AND description != '' "
        "ORDER BY id LIMIT 1",
        (seed_user_id,),
    ).fetchone()
    before_total = raw_conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ?", (seed_user_id,)
    ).fetchone()[0]

    auth_client.post(f"/expenses/{row['id']}/delete")

    after_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]
    assert after_total == before_total - row["amount"]

    body = auth_client.get("/profile").get_data(as_text=True)
    assert row["description"] not in body
    assert ("%.2f" % after_total) in body


def test_delete_leaves_other_expenses(auth_client, seed_user_id, raw_conn):
    rows = raw_conn.execute(
        "SELECT id FROM expenses WHERE user_id = ? ORDER BY id", (seed_user_id,)
    ).fetchall()
    assert len(rows) >= 2
    target, survivor = rows[0]["id"], rows[1]["id"]

    auth_client.post(f"/expenses/{target}/delete")

    assert not _exists(raw_conn, target)
    assert _exists(raw_conn, survivor)


# --- ownership / auth --------------------------------------------------- #

def test_delete_other_users_expense_404_and_kept(auth_client, raw_conn):
    _other_id, other_expense_id = _other_users_expense(raw_conn)
    resp = auth_client.post(f"/expenses/{other_expense_id}/delete")
    assert resp.status_code == 404
    assert _exists(raw_conn, other_expense_id)


def test_delete_missing_expense_404(auth_client):
    resp = auth_client.post("/expenses/999999/delete")
    assert resp.status_code == 404


def test_delete_requires_login(client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    resp = client.post(f"/expenses/{row['id']}/delete")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _exists(raw_conn, row["id"])  # nothing deleted


# --- method / safety ---------------------------------------------------- #

def test_get_delete_is_405_and_keeps_row(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    resp = auth_client.get(f"/expenses/{row['id']}/delete")
    assert resp.status_code == 405
    assert _exists(raw_conn, row["id"])  # a GET must never delete


# --- UI ----------------------------------------------------------------- #

def test_profile_renders_delete_form(auth_client, seed_user_id, raw_conn):
    row = _an_expense(raw_conn, seed_user_id)
    body = auth_client.get("/profile").get_data(as_text=True)
    assert f"/expenses/{row['id']}/delete" in body
    assert 'method="POST"' in body or 'method="post"' in body
