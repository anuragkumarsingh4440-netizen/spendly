## 1. Overview

Implement the **Profile page** — a protected page showing the logged-in user's account
details and a quick summary of their spending.

This is the first **login-protected** page, so it also introduces a reusable
`login_required` decorator that later steps (expense CRUD) will use.

---

## 2. Depends on

- **Step 1 — Database Setup** (`users`, `expenses`, `get_db`)
- **Step 2 — Authentication** (`session["user_id"]`)
- **Step 3 — Logout** (navbar `current_user`, session handling)

---

## 3. Routes

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/profile` | If not logged in → redirect to `/login`. Else render `profile.html` with the user's details + spending summary. |

- All other routes unchanged.

---

## 4. Access Control

- Add a reusable **`login_required`** decorator:
  - If `session` has no `user_id` → `redirect(url_for("login"))`.
  - Otherwise call the wrapped view normally.
  - Use `functools.wraps` to preserve the view's name (Flask needs unique endpoints).
- Apply it to `/profile`.

---

## 5. Data Shown on the Profile

Fetch with parameterized queries scoped to the current `session["user_id"]`:

- **User details:** `name`, `email`, `created_at` (shown as "Member since").
- **Spending summary:**
  - `total_count` — number of expenses (`COUNT(*)`)
  - `total_amount` — sum of all expense amounts (`SUM(amount)`, treat `NULL` as `0`)
  - `month_amount` — sum of amounts for the **current month** (`date LIKE 'YYYY-MM-%'`)

---

## 6. Changes to `app.py`

- Import `functools` (or `from functools import wraps`).
- Define the `login_required` decorator.
- Replace the `/profile` placeholder with a real handler that:
  - is decorated with `@login_required`,
  - loads the user row and the three summary numbers via `get_db()` (parameterized, closed in `finally`),
  - renders `profile.html` passing `user` and the summary values.

---

## 7. Files to Create

- `templates/profile.html` — extends `base.html`; reuse existing `auth-*` / `btn-*`
  classes for visual consistency. Show user details + the three summary stats, and a
  **Logout** action (link to `url_for('logout')`).

---

## 8. Files to Change

- `app.py` → `login_required` decorator + real `/profile` route

---

## 9. Dependencies

- No new pip packages
- Use `functools` (stdlib), `flask` (`session`, `redirect`, `url_for`, `render_template`),
  `database.db.get_db`

---

## 10. Rules for Implementation

- **Parameterized queries only**; never string-format SQL.
- Scope every query to `session["user_id"]` — a user must only see their own data.
- Handle `SUM(...)` returning `NULL` (no rows) → display `0`.
- Close the DB connection in a `finally` block.
- No DB/schema changes; no new dependencies.
- `login_required` must use `functools.wraps`.

---

## 11. Expected Behavior

- Guest visiting `/profile` is redirected to `/login`.
- Logged-in user sees their name, email, member-since date, and spending summary.
- The demo user shows `total_count = 8` and a non-zero `total_amount`.
- Numbers are scoped to the logged-in user only.

---

## 12. Error Handling Expectations

- No active session → clean redirect to `/login` (no error).
- A user with zero expenses sees `0` totals, not a crash.

---

## 13. Definition of Done

- [x] `login_required` decorator exists and uses `functools.wraps`.
- [x] Guest `GET /profile` → 302 redirect to `/login`.
- [x] Logged-in `GET /profile` → 200 and shows name + email + member-since.
- [x] Profile shows total count, total amount, and current-month amount for that user.
- [x] Demo user profile shows 8 transactions and the correct total.
- [x] Queries are parameterized and scoped to `session["user_id"]`.
- [x] `templates/profile.html` created; all existing routes still return 200.
