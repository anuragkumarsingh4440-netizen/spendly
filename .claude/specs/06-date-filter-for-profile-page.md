# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the `/profile` page so users can scope every
data section — summary stats, recent transactions, and category breakdown — to a
chosen time window instead of always seeing all-time data. The filter is driven
by query-string parameters (`start` / `end`) on the existing `GET /profile`
route, plus a small set of quick-range presets (This month, Last 30 days, This
year, All time). When no range is supplied the page behaves exactly as it does
today (all-time data), so the change is backward compatible. The query helpers
from Step 5 are extended to accept an optional date range rather than being
replaced.

## Depends on
- Step 1: Database setup (`expenses.date` column exists, stored as `YYYY-MM-DD`)
- Step 4: Profile page static UI
- Step 5: Backend connection (`database/queries.py` helpers + live `/profile`)

## Routes
No new routes. The existing `GET /profile` route is modified to read optional
`start` and `end` query parameters:
- `GET /profile` — all-time data (unchanged default behaviour)
- `GET /profile?start=2026-06-01&end=2026-06-30` — data scoped to June 2026
- `GET /profile?range=this_month` — preset shortcut resolved server-side to a
  concrete start/end pair

## Database changes
No database changes. The `expenses` table already stores `date` as an ISO
`YYYY-MM-DD` string, which sorts and compares lexicographically.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar at the top of the page (inside the existing
    `profile-page` section, above the summary stats).
  - The bar contains: a "From" date input, a "To" date input, an Apply button,
    and preset links/buttons (This month · Last 30 days · This year · All time).
  - Use a plain `<form method="get" action="/profile">` so the filter works
    without JavaScript.
  - The active range is reflected back: the date inputs are pre-filled with the
    resolved `start`/`end`, and the matching preset is marked active.
  - When the selected range has no expenses, each section shows its existing
    empty state (no transactions / empty breakdown / zeroed stats) plus a short
    "No expenses in this range" message.
  - Amounts continue to render with the ₹ symbol.

## Files to change
- `app.py` — `profile()` reads/validates `start`, `end`, `range`, resolves
  presets, and passes the range to the query helpers and back to the template.
- `database/queries.py` — extend the three data helpers to accept an optional
  date range (see below).
- `templates/profile.html` — add the filter bar and active-state rendering.

## Files to create
- `database/date_filter.py` — pure date-range helpers (no Flask imports):
  - `resolve_range(range_key=None, start=None, end=None, today=None)` →
    `(start, end)` tuple of `YYYY-MM-DD` strings, or `(None, None)` for all-time.
    Preset keys: `this_month`, `last_30_days`, `this_year`, `all_time`.
  - `is_valid_date(value)` → `True` if `value` is a well-formed `YYYY-MM-DD`
    string, else `False`.

## Query helper changes (`database/queries.py`)
Each helper gains optional `start=None, end=None` parameters. When both are
`None` the helper behaves exactly as in Step 5 (all-time). When provided, an
inclusive `date BETWEEN ? AND ?` clause is added to the WHERE.
- `get_summary_stats(user_id, start=None, end=None)`
- `get_recent_transactions(user_id, limit=10, start=None, end=None)`
- `get_category_breakdown(user_id, start=None, end=None)`

`get_user_by_id` is unchanged — user info is not date-scoped.

## New dependencies
No new dependencies. Use Python's standard `datetime` module only.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`.
- Parameterised queries only — date bounds are passed as bound parameters, never
  string-formatted into SQL.
- Date filtering is **inclusive** of both `start` and `end`.
- Dates compare as `YYYY-MM-DD` strings; do not convert the stored column.
- All date parsing/validation lives in `database/date_filter.py`, not in the
  route or the SQL layer.
- Invalid or partial input must fail safe to all-time data, never raise:
  - If only one of `start`/`end` is supplied, ignore it and use all-time.
  - If either date is malformed (`is_valid_date` is `False`), use all-time.
  - If `start > end`, swap them rather than returning an empty result.
- An unknown `range` key resolves to `all_time`.
- Presets are resolved against "today" so they stay correct over time; pass
  `today` explicitly into `resolve_range` so it is testable.
  - `this_month` → first day of the current month … today
  - `last_30_days` → 29 days ago … today (30 inclusive days)
  - `this_year` → Jan 1 of the current year … today
  - `all_time` → `(None, None)`
- An explicit `start`/`end` pair takes precedence over a `range` preset when
  both are present.
- Use CSS variables — never hardcode hex values; no inline styles.
- All templates extend `base.html`.
- Currency must always display as ₹ — never £ or $.

## Tests to write

### Unit tests — date helpers
File: `tests/test_date_filter.py`

| Function | Input | Expected output |
|---|---|---|
| `is_valid_date` | `"2026-06-17"` | `True` |
| `is_valid_date` | `"2026-13-01"` / `"06/17/2026"` / `""` / `None` | `False` |
| `resolve_range` | `range_key="all_time"` | `(None, None)` |
| `resolve_range` | `range_key="this_month", today=2026-06-17` | `("2026-06-01", "2026-06-17")` |
| `resolve_range` | `range_key="last_30_days", today=2026-06-17` | `("2026-05-19", "2026-06-17")` |
| `resolve_range` | `range_key="this_year", today=2026-06-17` | `("2026-01-01", "2026-06-17")` |
| `resolve_range` | valid `start`+`end` | that `(start, end)` pair |
| `resolve_range` | `start > end` | swapped `(end, start)` |
| `resolve_range` | only `start` given | `(None, None)` |
| `resolve_range` | malformed `start` | `(None, None)` |
| `resolve_range` | unknown `range_key` | `(None, None)` |
| `resolve_range` | both preset and explicit dates | explicit dates win |

### Unit tests — scoped query helpers
File: `tests/test_date_filter_queries.py`

| Function | Input | Expected output |
|---|---|---|
| `get_summary_stats` | range covering all seed expenses | same totals as all-time |
| `get_summary_stats` | range covering a subset | totals/count for that subset only |
| `get_summary_stats` | range with no expenses | `{"total_spent": 0, "transaction_count": 0, "top_category": "—"}` |
| `get_recent_transactions` | subset range | only expenses whose `date` is in range, newest first |
| `get_recent_transactions` | range with no expenses | empty list |
| `get_category_breakdown` | subset range | per-category totals for that range only; `pct` sums to 100 |
| `get_category_breakdown` | range with no expenses | empty list |
| all three | `start=None, end=None` | identical results to Step 5 (no regression) |

### Route tests
File: `tests/test_profile_date_filter.py`

`GET /profile` — unauthenticated:
- Redirects to `/login` (302) regardless of query params.

`GET /profile` — authenticated as seed user:
- No params → 200, all-time totals (₹346.24, 8 transactions) — unchanged.
- `?range=all_time` → identical to no params.
- A narrow `?start=&end=` range covering a known subset → totals reflect only
  that subset; transaction rows outside the range are absent from the response.
- A range with no expenses → 200, ₹0.00 total, 0 transactions, empty breakdown,
  "No expenses in this range" message present.
- Malformed `?start=banana` → 200, falls back to all-time totals (no error).
- Only `?start=` with no `end` → 200, falls back to all-time totals.
- Date inputs in the returned HTML are pre-filled with the resolved range.

## Definition of done
- [ ] The profile page shows a filter bar with From/To inputs, an Apply button,
      and the four presets (This month · Last 30 days · This year · All time).
- [ ] Selecting a date range reloads `/profile` with `start`/`end` in the URL
      and scopes summary stats, transactions, and category breakdown to that
      range.
- [ ] Preset buttons load the correct concrete range and are marked active.
- [ ] The filter works with JavaScript disabled (plain GET form submit).
- [ ] Visiting `/profile` with no params still shows all-time data exactly as in
      Step 5 (₹346.24, 8 transactions, top category "Bills").
- [ ] A range with no expenses shows zeroed stats, empty transaction/breakdown
      states, and a "No expenses in this range" message — no errors.
- [ ] Malformed, partial, or unknown filter input falls back to all-time data
      rather than raising.
- [ ] Category breakdown percentages within a filtered range still sum to 100 %.
- [ ] All amounts on the page display the ₹ symbol.
