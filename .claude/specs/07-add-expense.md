## 1. Overview

Implement the **Add Expense** feature — the first write operation in the expense CRUD
flow. A logged-in user gets a form to record a new expense (amount, category, date,
optional description); on submit the expense is inserted for **their** account and they
are returned to a page that reflects the new total.

This replaces the `/expenses/add` placeholder ("Add expense — coming in Step 7").

---

## 2. Depends on

- **Step 1 — Database Setup** (`expenses` table, `get_db`, fixed category list)
- **Step 2 — Authentication** (`session["user_id"]`)
- **Step 4 — Profile** (`login_required` decorator; post-add redirect target)

---

## 3. Routes

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/expenses/add` | If not logged in → redirect to `/login`. Else render `add_expense.html` with an empty form (date defaulting to today). |
| POST | `/expenses/add` | Validate input. On success → insert the expense for `session["user_id"]`, then `redirect(url_for("profile"))`. On failure → re-render `add_expense.html` with an `error` and the submitted values preserved. |

- Both methods are guarded by `@login_required`.
- `/expenses/<id>/edit` and `/expenses/<id>/delete` remain placeholders (Steps 8–9).

> Note: the post-add destination is `/profile` for now (it shows the updated totals).
> A later expense-list / dashboard step may change this redirect target.

---

## 4. Access Control

- Apply the existing **`login_required`** decorator to `add_expense`.
- The inserted row's `user_id` always comes from `session["user_id"]` — never from the
  form — so a user can only create expenses for themselves.

---

## 5. Form Fields

Rendered by `add_expense.html`, POSTed to `/expenses/add`:

- **amount** — number input (`step="0.01"`, `min="0.01"`); required.
- **category** — `<select>` populated from the fixed category list (see §10); required.
- **date** — date input (`type="date"`), defaulting to today (`YYYY-MM-DD`); required.
- **description** — text input; optional.

---

## 6. Logic to Implement (`app.py`)

### A. `GET /expenses/add`
1. Render `add_expense.html`, passing the `categories` list and `today` (`date.today().isoformat()`)
   so the template can pre-select the date and build the category dropdown.

### B. `POST /expenses/add`
1. Read `amount`, `category`, `date`, `description` from `request.form`; strip whitespace.
2. Validate (see §10). On any failure → re-render `add_expense.html` with an `error`
   message, the `categories` list, and the **previously submitted values** (HTTP 200).
3. Convert `amount` to `float`.
4. Insert via `get_db()` using a **parameterized** query:
   `INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)`
   — `user_id` from the session; `description` stored as `NULL` when blank.
5. `commit()`, then `close()` in a `finally` block.
6. On success → `redirect(url_for("profile"))`.

---

## 7. Changes to `app.py`

- Replace the GET-only `/expenses/add` placeholder with a `methods=["GET", "POST"]`
  handler decorated with `@login_required`.
- Define the fixed `CATEGORIES` list (module-level constant) and pass it to the template.
- Reuse the already-imported `date`, `request`, `redirect`, `url_for`, `render_template`,
  `session`, and `get_db` — no new imports needed.
- Leave the edit/delete placeholders and all other routes unchanged.

---

## 8. Files to Create

- `templates/add_expense.html` — extends `base.html`; reuse existing `auth-*` / `btn-*`
  / form classes for visual consistency. Renders the four fields, the `{{ error }}` block,
  preserves submitted values on re-render, and POSTs to `url_for('add_expense')`.

---

## 9. Files to Change

- `app.py` → real `/expenses/add` GET+POST handler + `CATEGORIES` constant

---

## 10. Validation Rules

- **amount** — required; must parse as a `float` and be **greater than 0**. Reject blank,
  non-numeric, zero, and negative values.
- **category** — required; must be one of the fixed categories (reject anything not in the
  list, so a tampered form can't insert arbitrary values).
- **date** — required; must match `YYYY-MM-DD` format.
- **description** — optional; stored as `NULL` if empty after `strip()`.

Fixed category list (from Step 1):

- Food
- Transport
- Bills
- Health
- Entertainment
- Shopping
- Other

All validation failures re-render the form with a human-readable `error` and the user's
input intact.

---

## 11. Dependencies

- No new pip packages
- Use `flask` (`request`, `redirect`, `url_for`, `render_template`, `session`),
  `datetime.date`, and `database.db.get_db` — all already imported.

---

## 12. Rules for Implementation

- **Parameterized queries only**; never string-format SQL.
- `user_id` comes from `session["user_id"]`, never from the form.
- Validate the category against the server-side list — don't trust the dropdown.
- Store `amount` as `REAL` (float); store empty `description` as `NULL`.
- Dates stored in **YYYY-MM-DD** format.
- Close the DB connection in a `finally` block.
- No DB/schema changes; no new dependencies.

---

## 13. Expected Behavior

- Guest visiting `/expenses/add` (GET or POST) is redirected to `/login`.
- Logged-in user sees a form with the date pre-filled to today and the category dropdown.
- Submitting a valid expense inserts one row scoped to that user and redirects to `/profile`,
  where the count and totals reflect the new expense.
- The demo user's `total_count` goes from 8 → 9 after one successful add.
- Invalid input re-renders the form with an error and the entered values preserved — no DB write.

---

## 14. Error Handling Expectations

- No active session → clean redirect to `/login` (no error).
- Blank/missing required field → re-render with a validation error; no DB write.
- Non-numeric, zero, or negative amount → re-render with an error; no DB write.
- Category not in the fixed list → re-render with an error; no DB write.
- No unhandled exception should reach the user for these expected cases.

---

## 15. Definition of Done

- [ ] `/expenses/add` accepts `GET` and `POST` and is decorated with `@login_required`.
- [ ] Guest `GET`/`POST /expenses/add` → 302 redirect to `/login`.
- [ ] Logged-in `GET` renders the form with today's date and the category dropdown.
- [ ] Valid `POST` inserts one expense scoped to `session["user_id"]` and redirects to `/profile`.
- [ ] After one add, the demo user's profile shows 9 transactions and the updated total.
- [ ] Blank, non-numeric, zero/negative amount, or invalid category re-renders with an error and no DB write.
- [ ] Submitted values are preserved on re-render.
- [ ] Empty description is stored as `NULL`.
- [ ] All queries are parameterized; no schema changes; no new dependencies.
- [ ] `templates/add_expense.html` created; all existing routes still return 200.
