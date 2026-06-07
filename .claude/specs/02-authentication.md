## 1. Overview

Add **user authentication** to Spendly: real registration and login backed by the
database layer from Step 1.

This step makes the existing `/register` and `/login` pages functional — creating users
with hashed passwords, verifying credentials, and starting a server-side **session** so
the app can remember who is logged in.

Logout (Step 3) and profile (Step 4) build directly on the session established here.

---

## 2. Depends on

- **Step 1 — Database Setup** (`database/db.py`: `get_db`, `init_db`, `seed_db`)
  - `users` table (id, name, email UNIQUE, password_hash, created_at) is already created.
  - Demo user `demo@spendly.com` / `demo123` is already seeded — used to test login.

---

## 3. Routes

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/register` | Render `register.html` (unchanged) |
| POST | `/register` | Validate input, create user, redirect to `/login` on success; re-render with `error` on failure |
| GET | `/login` | Render `login.html` (unchanged) |
| POST | `/login` | Verify credentials, set session, redirect to `/` on success; re-render with `error` on failure |

- `/logout` → remains a placeholder (Step 3)
- `/profile` → remains a placeholder (Step 4)
- No template changes required — `register.html` and `login.html` already render an
  `{{ error }}` block and POST the correct fields.

---

## 4. Session & Security

- Enable Flask sessions by setting `app.secret_key`.
  - Read from environment variable `SECRET_KEY`; fall back to a development default if unset.
- On successful login, store in `session`:
  - `session["user_id"]`   → the user's `id`
  - `session["user_name"]` → the user's `name` (for greeting/UI later)
- Sessions are signed cookies (Flask default) — never store the password or hash in the session.

---

## 5. Logic to Implement (`app.py`)

### A. `POST /register`
1. Read `name`, `email`, `password` from `request.form`; strip whitespace.
2. Validate (see §10). On any failure → re-render `register.html` with an `error` message
   (HTTP 200, form stays on page).
3. Hash the password with `generate_password_hash`.
4. Insert the user via `get_db()` using a **parameterized** query; `commit()`; `close()`.
5. Handle duplicate email: if the `UNIQUE` constraint raises `sqlite3.IntegrityError`,
   re-render with `error = "An account with this email already exists."`
6. On success → `redirect(url_for("login"))`.

### B. `POST /login`
1. Read `email`, `password` from `request.form`; strip whitespace.
2. Look up the user by email via `get_db()` (parameterized).
3. If no user, or `check_password_hash(user["password_hash"], password)` is False →
   re-render `login.html` with `error = "Invalid email or password."` (generic, no leak of
   which field was wrong).
4. On success → set `session["user_id"]` and `session["user_name"]`, then
   `redirect(url_for("landing"))`.

> Note: the post-login destination is the landing page (`/`) for now; a later step
> (dashboard / expense list) will change this redirect target.

---

## 6. Changes to `app.py`

- Update imports:
  - From `flask`: add `request`, `redirect`, `url_for`, `session`
  - From `database.db`: add `get_db` (in addition to existing `init_db`, `seed_db`)
  - From `werkzeug.security`: `generate_password_hash`, `check_password_hash`
- Set `app.secret_key` (from `SECRET_KEY` env var, dev fallback) right after `app = Flask(__name__)`.
- Replace the existing GET-only `/register` and `/login` routes with handlers that accept
  `methods=["GET", "POST"]`.
- Leave `init_db()` / `seed_db()` startup block and all other routes unchanged.

---

## 7. Files to Change

- `app.py` → secret key, imports, register + login POST logic

---

## 8. Files to Create

- None (templates and DB already exist)

---

## 9. Dependencies

- No new pip packages
- Use:
  - `flask` (`request`, `redirect`, `url_for`, `session`) — already installed
  - `werkzeug.security` (`generate_password_hash`, `check_password_hash`) — already installed
  - `database.db.get_db` from Step 1

---

## 10. Validation Rules

Registration (`POST /register`):
- `name`, `email`, `password` are all **required** (non-empty after `strip()`).
- `password` must be at least **8 characters** (matches the form's "Min. 8 characters" hint).
- `email` must contain a basic `@` with text on both sides (lightweight server-side check;
  the form already enforces `type="email"` client-side).
- Duplicate email → rejected via the `UNIQUE` constraint (see §13).

Login (`POST /login`):
- `email`, `password` are **required** (non-empty after `strip()`).

All validation failures re-render the same page with a human-readable `error` string.

---

## 11. Rules for Implementation

- **Parameterized queries only** — never use string formatting / f-strings in SQL.
- Always **hash** passwords with `generate_password_hash`; verify with `check_password_hash`.
- Never store plaintext passwords or password hashes in the session.
- Login errors must be **generic** ("Invalid email or password.") — do not reveal whether
  the email exists.
- Close every DB connection (use `try/finally` or close after use).
- Do not change the database schema or the Step 1 functions.
- Do not introduce new pip dependencies.
- `secret_key` must come from `SECRET_KEY` env var when present (dev fallback otherwise).

---

## 12. Expected Behavior

- Visiting `/register` or `/login` (GET) renders the existing forms.
- Submitting valid registration creates a new user (hashed password) and lands on `/login`.
- Submitting valid login sets a session and redirects to `/`.
- Logging in with the seeded demo account (`demo@spendly.com` / `demo123`) succeeds.
- After login, `session["user_id"]` is populated and persists across requests (cookie).
- Invalid input or bad credentials re-render the page with a clear error and **no** session.

---

## 13. Error Handling Expectations

- Missing/blank fields → re-render with a validation error; no DB write.
- Password shorter than 8 chars → re-render with an error; no DB write.
- Duplicate email → caught `sqlite3.IntegrityError` → friendly "already exists" error.
- Wrong email or wrong password on login → generic "Invalid email or password."
- No unhandled exception should reach the user for these expected cases.

---

## 14. Definition of Done

- [x] `app.secret_key` is configured; sessions work.
- [x] `POST /register` creates a user with a hashed password.
- [x] Duplicate email registration is rejected with a friendly error (no crash).
- [x] Short/blank-field registrations are rejected with a validation error.
- [x] `POST /login` verifies credentials with `check_password_hash`.
- [x] Successful login sets `session["user_id"]` and `session["user_name"]` and redirects to `/`.
- [x] Demo account (`demo@spendly.com` / `demo123`) can log in.
- [x] Bad credentials show a generic error and do not create a session.
- [x] All queries are parameterized; no schema changes; no new dependencies.
- [x] App starts and all existing routes still return 200.
