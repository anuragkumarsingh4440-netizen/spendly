"""Step 5 — backend connection tests.

Expected values are computed dynamically from the seeded temp DB (raw SQL), so
the tests stay correct regardless of what ``seed_db()`` contains.
"""

from datetime import datetime

from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# --------------------------------------------------------------------- #
# get_user_by_id                                                        #
# --------------------------------------------------------------------- #

def test_get_user_by_id_valid(seed_user_id, raw_conn):
    expected = raw_conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (seed_user_id,)
    ).fetchone()
    result = get_user_by_id(seed_user_id)
    assert result["name"] == expected["name"]
    assert result["email"] == expected["email"]
    expected_since = datetime.strptime(
        expected["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")
    assert result["member_since"] == expected_since


def test_get_user_by_id_missing(db_path):
    assert get_user_by_id(999999) is None


# --------------------------------------------------------------------- #
# get_summary_stats                                                     #
# --------------------------------------------------------------------- #

def test_get_summary_stats_with_expenses(seed_user_id, raw_conn):
    exp_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]
    exp_count = raw_conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (seed_user_id,)
    ).fetchone()[0]
    exp_top = raw_conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (seed_user_id,),
    ).fetchone()[0]

    stats = get_summary_stats(seed_user_id)
    assert stats["total_spent"] == exp_total
    assert stats["transaction_count"] == exp_count
    assert stats["top_category"] == exp_top


def test_get_summary_stats_no_expenses(empty_user_id):
    assert get_summary_stats(empty_user_id) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


# --------------------------------------------------------------------- #
# get_recent_transactions                                               #
# --------------------------------------------------------------------- #

def test_get_recent_transactions_order_and_keys(seed_user_id):
    txns = get_recent_transactions(seed_user_id)
    assert len(txns) > 0
    for t in txns:
        assert set(t.keys()) == {"id", "date", "description", "category", "amount"}
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)  # newest first


def test_get_recent_transactions_empty(empty_user_id):
    assert get_recent_transactions(empty_user_id) == []


# --------------------------------------------------------------------- #
# get_category_breakdown                                                #
# --------------------------------------------------------------------- #

def test_get_category_breakdown(seed_user_id):
    breakdown = get_category_breakdown(seed_user_id)
    amounts = [item["amount"] for item in breakdown]
    assert amounts == sorted(amounts, reverse=True)  # ordered by amount desc
    assert all(isinstance(item["pct"], int) for item in breakdown)
    assert sum(item["pct"] for item in breakdown) == 100


def test_get_category_breakdown_empty(empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


# --------------------------------------------------------------------- #
# GET /profile route                                                    #
# --------------------------------------------------------------------- #

def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated(auth_client, seed_user_id, raw_conn):
    resp = auth_client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    user = raw_conn.execute(
        "SELECT name, email FROM users WHERE id = ?", (seed_user_id,)
    ).fetchone()
    assert user["name"] in body
    assert user["email"] in body
    assert "&#8377;" in body  # rupee symbol entity

    exp_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]
    assert ("%.2f" % exp_total) in body

    exp_top = raw_conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (seed_user_id,),
    ).fetchone()[0]
    assert exp_top in body
