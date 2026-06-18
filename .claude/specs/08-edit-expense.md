# Spec: Edit Expense

## Overview
Step 8 makes the `/expenses/<id>/edit` route functional so a logged-in user can
update an expense they previously recorded. The page renders the same four-field
form as Add Expense (amount, category, date, optional description), pre-filled
with the expense's current values. On submit, the server validates the input,
**updates** the existing row in the `expenses` table, and redirects to `/profile`
where the change is immediately reflected in the summary stats, transaction
history, and category breakdown (Steps 5–6). The defining new concern versus Step
7 is **ownership**: a user may only view or edit their own expenses — any attempt
to edit a non-existent expense, or one belonging to another user, returns `404`.

## Depends on
- Step 1: Database setup (`expenses` table + `get_db()` exist)
- Step 2: Registration / Step 3: Login (`session["user_id"]` is set on login)
- Step 5: Backend connection (`/profile` reads live data so edits appear)
- Step 7: Add Expense (validation logic + form template to mirror)

## Routes
| Method | Route | Behaviour |
| --- | --- | --- |
| GET | `/expenses/<int:id>/edit` | Render the edit form pre-filled with the expense's current values. `404` if the expense does not exist or is not owned by the current user. Login-protected. |
| POST | `/expenses/<int:id>/edit` | Validate the form, update the expense, redirect to `/profile` on success; re-render with `error` (HTTP 200) on failure. Same ownership `404` rule. Login-protected. |

- Both methods require an active session. Logged-out users are redirected to
  `/login` by the `@login_required` decorator.
- The route replaces the current placeholder that returns the string
  "Edit expense — coming in Step 8".

## Database changes
No schema changes. Edits reuse the existing `expenses` columns (`amount`,
`category`, `date`, `description`). `user_id` and `created_at` are never changed
by an edit.

## Templates
- **Create**: `templates/edit_expense.html`
  - Mirrors `templates/add_expense.html` (same field set, classes, and
    `{{ error }}` block) so the look is consistent.
  - Differences from the add form:
    - Title/subtitle reflect editing (e.g. "Edit expense").
    - `<form method="POST" action="{{ url_for('edit_expense', id=expense.id) }}">`.
    - All four fields are pre-filled from the `expense` dict (amount, category,
      date, description); the matching category `<option>` is `selected`.
    - Submit button reads "Save changes".
  - Extends `base.html`; uses CSS variables / shared form classes — no inline
    styles. Currency is displayed as ₹.

## Files to change
- `app.py` — implement the `edit_expense(id)` view (GET render + POST handling),
  replacing the placeholder.

## Files to create
- `templates/edit_expense.html` — the pre-filled edit form (see above).
- `database/queries.py` — add `get_expense_by_id(expense_id, user_id)` (see below).

## Query helper (`database/queries.py`)
Add one ownership-scoped read helper alongside the existing Step 5/6 helpers:
- `get_expense_by_id(expense_id, user_id)` →
  dict with `id`, `amount`, `category`, `date`, `description` for an expense that
  belongs to `user_id`, or `None` if no such expense exists for that user.
  - Single parameterised query: `SELECT ... FROM expenses WHERE id = ? AND
    user_id = ?`. The `user_id` predicate is what enforces ownership — never look
    up by `id` alone.
  - Opens its own connection via `get_db()` and closes it before returning, like
    the other helpers in this module.

## Form fields & validation
Identical rules to Step 7 (Add Expense). Read from `request.form`, stripped. All
failures re-render `edit_expense.html` with a human-readable `error` and **no** DB
write.

| Field | Rule | Error message |
| --- | --- | --- |
| `amount` | Required; must parse as a float | "Please enter a valid amount." |
| `amount` | Must be finite and greater than zero (reject `nan`/`inf`/`<= 0`) | "Amount must be greater than zero." |
| `category` | Must be one of the server-side `CATEGORIES` list | "Please choose a valid category." |
| `date` | Required; must parse as `YYYY-MM-DD`; normalised to zero-padded ISO | "Please enter a valid date." |
| `description` | Optional; empty string is stored as `NULL` | — |

## Logic to implement (`app.py`)
### Shared (both methods)
1. Load the expense with `get_expense_by_id(id, session["user_id"])`.
2. If it is `None`, `abort(404)` — this covers both "no such expense" and
   "belongs to another user" without distinguishing the two.

### GET `/expenses/<id>/edit`
3. Render `edit_expense.html` with `categories=CATEGORIES` and `expense=<row>`
   (the pre-filled values).

### POST `/expenses/<id>/edit`
3. Read and strip `amount`, `category`, `date`, `description` from `request.form`.
4. Validate in order (amount → category → date) per the table above. On the first
   failure, re-render with the error and the submitted values preserved (keep the
   expense `id` available so the form action still targets this expense).
5. Parse/normalise exactly as in Step 7 (`float` + `math.isfinite` + `> 0`;
   `datetime.strptime(date_str, "%Y-%m-%d").date().isoformat()`).
6. Update via `get_db()` using a **parameterised, ownership-scoped** statement:
   `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ?
   WHERE id = ? AND user_id = ?` — empty description becomes `None`. `commit()`,
   then `close()` in a `finally`.
7. `redirect(url_for("profile"))` on success.

## New dependencies
None. Uses `math`, `datetime`/`date` (stdlib), `abort` from Flask, and the
existing `get_db()`.

## Rules for implementation
- Route is login-protected with `@login_required`.
- **Ownership is mandatory**: both the load and the `UPDATE` must be scoped by
  `user_id = session["user_id"]`. Never read or write an expense by `id` alone.
- A missing expense or one owned by another user returns `404` (use `abort(404)`)
  — do not leak whether the id exists.
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`.
- Parameterised queries only — never string-format values into SQL.
- `user_id` is taken from the session, never from the form or URL.
- Same field-validation rules and normalisation as Step 7 (reuse the logic;
  factor a shared validator if it reduces duplication).
- Empty `description` is stored as `NULL`, not `""`.
- On validation failure, re-render (HTTP 200) with the submitted values intact —
  do not redirect and do not lose input.
- Close every DB connection (`try/finally`).
- Template extends `base.html`; no inline styles; currency shows as ₹.

## Tests to write

### Unit tests — query helper
File: `tests/test_edit_expense.py` (or a shared queries test module)

| Function | Input | Expected output |
|---|---|---|
| `get_expense_by_id` | valid `expense_id` owned by `user_id` | dict with `id`, `amount`, `category`, `date`, `description` |
| `get_expense_by_id` | `expense_id` owned by a **different** user | `None` |
| `get_expense_by_id` | non-existent `expense_id` | `None` |

### Route tests
File: `tests/test_edit_expense.py`

`GET /expenses/<id>/edit`:
- Unauthenticated → redirects to `/login` (302).
- Authenticated, own expense → 200; form is pre-filled with the expense's current
  amount, category (selected `<option>`), date, and description.
- Authenticated, another user's expense → `404`.
- Authenticated, non-existent id → `404`.

`POST /expenses/<id>/edit` — authenticated, own expense:
- Valid change → 302 to `/profile`; the row is updated in place (same `id`,
  `user_id` and `created_at` unchanged; row count unchanged); new values persist.
- The edit is reflected on `/profile` (e.g. total spent changes by the delta).
- Clearing the description → stored as `NULL`.
- Non-padded date `"2026-6-8"` → stored as `"2026-06-08"`.
- Invalid amount (`""`, `"abc"`) → 200, "Please enter a valid amount.", row
  unchanged.
- Non-positive / non-finite amount (`"0"`, `"-5"`, `"inf"`, `"nan"`) → 200,
  "Amount must be greater than zero.", row unchanged.
- Bad category (`"Crypto"`) → 200, "Please choose a valid category.", row
  unchanged.
- Malformed date (`"banana"`) → 200, "Please enter a valid date.", row unchanged.
- Validation failure re-renders the form with submitted values pre-filled.

`POST /expenses/<id>/edit` — ownership / auth:
- Another user's expense → `404`; that row is **not** modified.
- Unauthenticated → redirects to `/login` (302); no row modified.

## Definition of done
- [ ] `GET /expenses/<id>/edit` renders the form pre-filled with the expense's
      current values; logged-out users are redirected to `/login`.
- [ ] A valid `POST` updates the existing row in place (no new row, `id` and
      `user_id` unchanged) and redirects to `/profile`.
- [ ] The edited values are reflected on `/profile` (stats, history, breakdown).
- [ ] Editing a non-existent expense, or one owned by another user, returns `404`
      and modifies nothing.
- [ ] Invalid amount, unknown category, or malformed date is rejected with a clear
      error and no DB write; a valid non-padded date is normalised.
- [ ] Clearing the description stores `NULL`.
- [ ] Validation failures re-render the form with submitted values preserved.
- [ ] All reads and writes are parameterised and scoped by `user_id`; the route is
      login-protected; no schema changes; no new dependencies.
