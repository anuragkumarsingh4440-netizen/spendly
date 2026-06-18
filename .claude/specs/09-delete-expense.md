# Spec: Delete Expense

## Overview
Step 9 makes the `/expenses/<id>/delete` route functional so a logged-in user can
permanently remove one of their own expenses. Deletion is triggered from a small
per-row **Delete** button on `/profile` (next to the Step 8 Edit link); on submit,
the server verifies ownership, deletes the row from the `expenses` table, and
redirects back to `/profile`, where the summary stats, transaction history, and
category breakdown (Steps 5–6) immediately reflect the removal. As in Step 8, a
user may only delete their own expenses — a missing expense, or one owned by
another user, returns `404`.

The defining design rule for this step is that **delete is POST-only**. A
destructive action must never be reachable by a plain link or `GET` (which can be
triggered by prefetching, crawlers, or an accidental click), so the route accepts
`POST` only and the profile page submits it via a real `<form>`.

## Depends on
- Step 1: Database setup (`expenses` table + `get_db()` exist)
- Step 2: Registration / Step 3: Login (`session["user_id"]` is set on login)
- Step 5: Backend connection (`/profile` reads live data so removals appear)
- Step 8: Edit Expense (`get_expense_by_id` ownership helper; per-row actions and
  `id` already exposed on the profile transaction rows)

## Routes
| Method | Route | Behaviour |
| --- | --- | --- |
| POST | `/expenses/<int:id>/delete` | Verify ownership, delete the expense, redirect to `/profile` on success. `404` if the expense does not exist or is not owned by the current user. Login-protected. |

- The route requires an active session. Logged-out users are redirected to
  `/login` by the `@login_required` decorator.
- The route accepts **`POST` only**. A `GET` request returns `405 Method Not
  Allowed` (Flask's default, because only `POST` is registered).
- This replaces the current placeholder that returns the string
  "Delete expense — coming in Step 9".

## Database changes
No schema changes. A delete is a single `DELETE` against the existing `expenses`
table.

## Templates
- **Modify**: `templates/profile.html`
  - In the transactions table's existing "Actions" cell (added in Step 8), add a
    **Delete** control alongside the Edit link.
  - Delete must be a form, not a link:
    `<form method="POST" action="{{ url_for('delete_expense', id=txn.id) }}">`
    with a submit button (a small lucide `trash-2` icon + "Delete").
  - The form works without JavaScript. As a progressive enhancement, the button
    may carry `onsubmit="return confirm('Delete this expense?')"` so a stray
    click is recoverable — but the server never relies on it.
  - Extends `base.html`; uses CSS variables / shared classes — no inline styles.

## Files to change
- `app.py` — implement the `delete_expense(id)` view, replacing the placeholder.
- `templates/profile.html` — add the per-row Delete form.

## Files to create
- None. The ownership helper `get_expense_by_id` already exists from Step 8, and
  no new template is needed (deletion redirects straight back to `/profile`).

## Logic to implement (`app.py`)
### POST `/expenses/<id>/delete`
1. Load the expense with `get_expense_by_id(id, session["user_id"])`.
2. If it is `None`, `abort(404)` — covers both "no such expense" and "belongs to
   another user" without distinguishing the two.
3. Delete via `get_db()` using a **parameterised, ownership-scoped** statement:
   `DELETE FROM expenses WHERE id = ? AND user_id = ?`. `commit()`, then `close()`
   in a `finally`.
4. `redirect(url_for("profile"))`.

## New dependencies
None. Uses `abort` from Flask and the existing `get_db()` / `get_expense_by_id`.

## Rules for implementation
- Route is login-protected with `@login_required` and accepts **`POST` only**.
- **Ownership is mandatory**: both the existence check and the `DELETE` must be
  scoped by `user_id = session["user_id"]`. Never delete an expense by `id` alone.
- A missing expense or one owned by another user returns `404` (use `abort(404)`)
  — do not leak whether the id exists for someone else.
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`.
- Parameterised queries only — never string-format values into SQL.
- `user_id` is taken from the session, never from the form or URL.
- Delete is irreversible; there is no soft-delete column — the row is removed.
- Close every DB connection (`try/finally`).
- The profile Delete control is a `POST` form; never a `GET` link.
- Template extends `base.html`; no inline styles.

## Tests to write

### Route tests
File: `tests/test_delete_expense.py`

`POST /expenses/<id>/delete` — authenticated as seed user:
- Own expense → 302 redirect to `/profile`; the row no longer exists in
  `expenses`; the user's row count decreases by exactly one.
- The removal is reflected on `/profile` (total spent drops by that expense's
  amount; its description no longer appears in the response).
- Deleting one expense leaves the user's other expenses untouched.

`POST /expenses/<id>/delete` — ownership / auth:
- Another user's expense → `404`; that row is **not** deleted (still present).
- Non-existent id → `404`.
- Unauthenticated → redirects to `/login` (302); no row deleted.

Method / safety:
- `GET /expenses/<id>/delete` → `405` (and the row is **not** deleted), proving
  deletion cannot happen via a link/prefetch.

UI:
- `GET /profile` (authenticated) renders a `POST` delete form whose action is
  `/expenses/<id>/delete` for a seeded transaction (e.g. the response contains
  `action="…/expenses/<id>/delete"` with `method="post"`).

Derive expense ids and expected values from the seeded temp DB (reuse
`tests/conftest.py` fixtures: `client`, `auth_client`, `seed_user_id`,
`raw_conn`); create a second user + expense via `raw_conn` for the cross-user
case (mirroring `tests/test_edit_expense.py`).

## Definition of done
- [ ] `POST /expenses/<id>/delete` removes the current user's expense and
      redirects to `/profile`; logged-out users are redirected to `/login`.
- [ ] The deleted expense disappears from `/profile` and the stats/breakdown
      update (total and count drop accordingly).
- [ ] Deleting a non-existent expense, or one owned by another user, returns `404`
      and removes nothing.
- [ ] A `GET` to the delete route returns `405` and deletes nothing.
- [ ] The profile page shows a per-row Delete button that submits via `POST`
      (working without JavaScript), sitting alongside the Edit link.
- [ ] The `DELETE` is parameterised and scoped by `user_id`; the route is
      login-protected; no schema changes; no new dependencies.
