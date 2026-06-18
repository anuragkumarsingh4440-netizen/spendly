# Spec: Add Expense

## Overview
Step 7 makes the `/expenses/add` route functional so a logged-in user can record
a new transaction. The page renders a form (amount, category, date, optional
description); on submit, the server validates the input, inserts a row into the
`expenses` table scoped to the current user, and redirects to `/profile` where the
new expense immediately shows up in the summary stats, transaction history, and
category breakdown built in Steps 5–6. On any validation failure the form is
re-rendered with an error message and the user's submitted values preserved, so
nothing is retyped. The route is login-protected and writes are parameterised.

## Depends on
- Step 1: Database setup (`expenses` table + `get_db()` exist)
- Step 2: Registration / Step 3: Login (`session["user_id"]` is set on login)
- Step 4: Profile page static UI
- Step 5: Backend connection (`/profile` reads live data so the new row appears)

## Routes
| Method | Route | Behaviour |
| --- | --- | --- |
| GET | `/expenses/add` | Render `add_expense.html` with the category list and today's date pre-filled. Login-protected. |
| POST | `/expenses/add` | Validate the form, insert the expense for the current user, redirect to `/profile` on success; re-render with `error` (HTTP 200) on failure. Login-protected. |

- Both methods require an active session. Logged-out users are redirected to
  `/login` by the `@login_required` decorator.

## Database changes
No schema changes. The `expenses` table already has all required columns:
`user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Use existing**: `templates/add_expense.html` (already created in Step 4).
  - Fields: `amount` (number), `category` (`<select>`), `date` (date input,
    defaults to today), `description` (text, optional).
  - Renders an `{{ error }}` block when validation fails.
  - When re-rendering after an error, the form is pre-filled from an `expense`
    dict of the submitted values (amount, category, date, description).
  - Extends `base.html`; uses CSS variables / shared form classes — no inline
    styles. Currency is displayed as ₹ everywhere it appears.

## Files to change
- `app.py` — implement the `add_expense()` view (GET render + POST handling).

## Files to create
- None. Template and DB layer already exist.

## Form fields & validation
Read from `request.form`, stripped of surrounding whitespace. All failures
re-render `add_expense.html` with a human-readable `error` and **no** DB write.

| Field | Rule | Error message |
| --- | --- | --- |
| `amount` | Required; must parse as a float | "Please enter a valid amount." |
| `amount` | Must be finite and greater than zero (reject `nan`/`inf`/`<= 0`) | "Amount must be greater than zero." |
| `category` | Must be one of the server-side `CATEGORIES` list (don't trust the form) | "Please choose a valid category." |
| `date` | Required; must parse as `YYYY-MM-DD`; normalised to zero-padded ISO | "Please enter a valid date." |
| `description` | Optional; empty string is stored as `NULL` | — |

`CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment",
"Shopping", "Other"]` — the same fixed list seeded in Step 1.

## Logic to implement (`app.py`)
### GET `/expenses/add`
1. Render `add_expense.html` with `categories=CATEGORIES`,
   `today=date.today().isoformat()`, and `expense=None`.

### POST `/expenses/add`
1. Read and strip `amount`, `category`, `date`, `description` from `request.form`.
2. Validate in order (amount → category → date) per the table above. On the
   first failure, re-render with the error and the submitted values preserved.
3. Parse `amount` with `float()`, then guard with `math.isfinite()` and `> 0`.
4. Reject any `category` not in `CATEGORIES`.
5. Parse `date` with `datetime.strptime(date_str, "%Y-%m-%d")` and re-emit as
   `.date().isoformat()` so `"2026-6-8"` is normalised to `"2026-06-08"`.
6. Insert via `get_db()` using a **parameterised** query:
   `INSERT INTO expenses (user_id, amount, category, date, description)
   VALUES (?, ?, ?, ?, ?)` — `user_id` comes from `session["user_id"]`, and an
   empty description is stored as `None`. `commit()`, then `close()` in a
   `finally`.
7. `redirect(url_for("profile"))` on success.

## New dependencies
None. Uses `math`, `datetime`/`date` (stdlib) and the existing `get_db()`.

## Rules for implementation
- Route is login-protected with `@login_required`.
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`.
- Parameterised queries only — never string-format values into SQL.
- `user_id` is taken from the session, never from the form (a user can only add
  expenses for themselves).
- `category` is validated against the server-side list, not trusted from the
  client.
- `amount` must be finite and strictly positive; `float()` alone accepts
  `nan`/`inf`, so guard with `math.isfinite()`.
- `date` is normalised to zero-padded `YYYY-MM-DD` so it matches the storage and
  comparison format used by Steps 5–6.
- Empty `description` is stored as `NULL`, not `""`.
- On validation failure, re-render (HTTP 200) with the submitted values intact —
  do not redirect and do not lose input.
- Close every DB connection (`try/finally`).
- Template extends `base.html`; no inline styles; currency shows as ₹.

## Tests to write

### Route tests
File: `tests/test_add_expense.py`

`GET /expenses/add`:
- Unauthenticated → redirects to `/login` (302).
- Authenticated → 200; response contains the amount/category/date fields and all
  seven category options; the date input defaults to today.

`POST /expenses/add` — authenticated:
- Valid submission → 302 redirect to `/profile`; a new row exists in `expenses`
  with the correct `user_id`, `amount`, `category`, normalised `date`, and
  `description`.
- The new expense is reflected on `/profile` (transaction count increases by one;
  total spent increases by the amount).
- Empty `description` → stored as `NULL`.
- Non-padded date `"2026-6-8"` → stored as `"2026-06-08"`.
- Missing/blank `amount` → 200, "Please enter a valid amount.", no row inserted.
- `amount` = `"abc"` → 200, "Please enter a valid amount.", no row inserted.
- `amount` = `"0"` / `"-5"` / `"inf"` / `"nan"` → 200, "Amount must be greater
  than zero.", no row inserted.
- `category` not in the list (e.g. `"Crypto"`) → 200, "Please choose a valid
  category.", no row inserted.
- Malformed `date` (e.g. `"banana"`) → 200, "Please enter a valid date.", no row
  inserted.
- On any validation failure, the response re-renders the form with the submitted
  values pre-filled.

`POST /expenses/add` — unauthenticated:
- Redirects to `/login` (302); no row inserted.

## Definition of done
- [ ] `GET /expenses/add` renders the form with the seven categories and today's
      date pre-filled; logged-out users are redirected to `/login`.
- [ ] A valid `POST` inserts one `expenses` row for the logged-in user and
      redirects to `/profile`.
- [ ] The newly added expense appears on `/profile` (counts, total, transaction
      list, and category breakdown all update).
- [ ] Invalid amount (non-numeric, zero, negative, `inf`/`nan`) is rejected with a
      clear error and no DB write.
- [ ] An unknown category is rejected server-side with a clear error and no DB
      write.
- [ ] A malformed date is rejected; a valid non-padded date is normalised to
      `YYYY-MM-DD`.
- [ ] Empty description is stored as `NULL`.
- [ ] Validation failures re-render the form with submitted values preserved.
- [ ] All writes are parameterised; the route is login-protected; no schema
      changes; no new dependencies.
