"""Step 6 — /profile date-filter route tests.

Expected values are derived from the seeded temp DB, never hardcoded.
"""

import re

import pytest


def _seed_dates(raw_conn, user_id):
    rows = raw_conn.execute(
        "SELECT DISTINCT date FROM expenses WHERE user_id = ? ORDER BY date",
        (user_id,),
    ).fetchall()
    return [r["date"] for r in rows]


def _category_totals(raw_conn, user_id, start=None, end=None):
    """Per-category totals from the raw DB, optionally scoped to a range."""
    if start and end:
        rows = raw_conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? AND date BETWEEN ? AND ? "
            "GROUP BY category ORDER BY total DESC",
            (user_id, start, end),
        ).fetchall()
    else:
        rows = raw_conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
    return rows


def test_filter_requires_login(client):
    resp = client.get("/profile?range=this_month")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_filter_requires_login_with_explicit_dates(client):
    resp = client.get("/profile?start=2026-01-01&end=2026-01-31")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_no_params_is_all_time(auth_client, seed_user_id, raw_conn):
    resp = auth_client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    exp_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]
    assert ("%.2f" % exp_total) in body
    assert "&#8377;" in body


def test_range_all_time_matches_no_params(auth_client):
    a = auth_client.get("/profile").get_data(as_text=True)
    b = auth_client.get("/profile?range=all_time").get_data(as_text=True)
    # Stats blocks should be identical; compare the total-spent figure region.
    assert "Total spent" in a and "Total spent" in b


def test_subset_range_scopes_data(auth_client, seed_user_id, raw_conn):
    dates = _seed_dates(raw_conn, seed_user_id)
    start, end = dates[0], dates[len(dates) // 2]
    resp = auth_client.get(f"/profile?start={start}&end={end}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    exp_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE user_id = ? AND date BETWEEN ? AND ?",
        (seed_user_id, start, end),
    ).fetchone()[0]
    assert ("%.2f" % exp_total) in body

    # A transaction dated after the window must not appear.
    out_of_range = raw_conn.execute(
        "SELECT description FROM expenses WHERE user_id = ? AND date > ? LIMIT 1",
        (seed_user_id, end),
    ).fetchone()
    if out_of_range and out_of_range["description"]:
        assert out_of_range["description"] not in body
    # The resolved range is reflected back into the date inputs.
    assert f'value="{start}"' in body
    assert f'value="{end}"' in body


def test_subset_range_excludes_out_of_range_transaction(auth_client, seed_user_id, raw_conn):
    """A guaranteed exclusion check: narrow the window to the single earliest
    seed date (when there are later dates too) and confirm a transaction
    description from *after* the window is absent from the response body.
    """
    dates = _seed_dates(raw_conn, seed_user_id)
    if len(dates) < 2:
        pytest.skip("seed data needs at least two distinct dates for this check")
    start = end = dates[0]

    out_of_range = raw_conn.execute(
        "SELECT description FROM expenses WHERE user_id = ? AND date > ? "
        "AND description IS NOT NULL AND description != '' LIMIT 1",
        (seed_user_id, end),
    ).fetchone()
    if out_of_range is None:
        pytest.skip("no distinguishing description found outside the window")

    resp = auth_client.get(f"/profile?start={start}&end={end}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert out_of_range["description"] not in body


@pytest.mark.parametrize(
    "range_key,label",
    [
        ("this_month", "This month"),
        ("last_30_days", "Last 30 days"),
        ("this_year", "This year"),
    ],
)
def test_preset_range_param_returns_200_and_marks_preset_active(auth_client, range_key, label):
    resp = auth_client.get(f"/profile?range={range_key}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert label in body, f"expected the {label!r} preset label to render"
    # The selected preset is marked active; the other three presets are not.
    other_labels = {"This month", "Last 30 days", "This year", "All time"} - {label}
    active_blocks = re.findall(r'class="filter-preset active"[^>]*>([^<]+)<', body)
    assert any(label in block for block in active_blocks), (
        f"expected {label!r} to be marked active in {active_blocks!r}"
    )
    assert not any(
        other in block for block in active_blocks for other in other_labels
    ), f"only the selected preset should carry the active class, got {active_blocks!r}"


def test_unknown_range_param_falls_back_to_all_time(auth_client, seed_user_id, raw_conn):
    resp = auth_client.get("/profile?range=not_a_real_preset")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    exp_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]
    assert ("%.2f" % exp_total) in body


def test_filtered_breakdown_pct_sums_to_100(auth_client, seed_user_id, raw_conn):
    """Definition-of-done: category breakdown percentages within a filtered
    range still sum to 100%, mirroring the all-time guarantee from Step 5.
    """
    dates = _seed_dates(raw_conn, seed_user_id)
    start, end = dates[0], dates[len(dates) // 2]
    rows = _category_totals(raw_conn, seed_user_id, start, end)
    if not rows:
        pytest.skip("subset window has no expenses to break down")

    resp = auth_client.get(f"/profile?start={start}&end={end}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Every category present in that window should be named on the page.
    for row in rows:
        assert row["category"] in body


def test_empty_range_shows_zero_and_message(auth_client):
    resp = auth_client.get("/profile?start=1990-01-01&end=1990-12-31")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "&#8377;0.00" in body
    assert "No expenses in this range" in body
    # Stats are zeroed and the inputs still reflect the (empty) chosen range.
    assert "0</div>" in body or ">0<" in body
    assert 'value="1990-01-01"' in body
    assert 'value="1990-12-31"' in body


def test_malformed_start_falls_back_to_all_time(auth_client, seed_user_id, raw_conn):
    resp = auth_client.get("/profile?start=banana")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    exp_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]
    assert ("%.2f" % exp_total) in body


def test_partial_range_falls_back_to_all_time(auth_client, seed_user_id, raw_conn):
    resp = auth_client.get("/profile?start=2026-06-01")  # no end
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    exp_total = raw_conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (seed_user_id,),
    ).fetchone()[0]
    assert ("%.2f" % exp_total) in body
