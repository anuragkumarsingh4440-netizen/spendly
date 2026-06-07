## 1. Overview

Implement **logout** for Spendly and make the navbar reflect authentication state.

Currently `/logout` is a placeholder string. This step clears the user's session so they
are signed out, and updates the shared navbar so a logged-in user sees their name + a
**Logout** link (instead of "Sign in / Get started").

---

## 2. Depends on

- **Step 1 — Database Setup**
- **Step 2 — Authentication** (`session["user_id"]`, `session["user_name"]` are set on login)

---

## 3. Routes

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/logout` | Clear the session, then redirect to `/` (landing) |

- All other routes unchanged.

---

## 4. Session Behavior

- `/logout` removes **all** session data (`session.clear()`), ending the signed-in state.
- After logout, protected/identity-aware UI reverts to the logged-out view.
- Visiting `/logout` while already logged out is harmless (no error) — it just redirects.

---

## 5. Template Context (so the navbar knows who is logged in)

- Expose the current user to **all** templates via a Flask **context processor** so each
  template does not have to pass it manually.
  - Provide `current_user`: a dict like `{"id": ..., "name": ...}` when logged in, else `None`.
  - Read it from `session` (`user_id`, `user_name`).

---

## 6. Changes to `app.py`

- Implement the `/logout` route: `session.clear()` → `redirect(url_for("landing"))`.
- Add a context processor (e.g. `inject_current_user`) returning `current_user` from the
  session for use in templates.
- Remove the `/logout` placeholder string.
- Leave all other routes and the startup block unchanged.

---

## 7. Changes to `templates/base.html`

- In the navbar `.nav-links`, branch on `current_user`:
  - **Logged in:** show a greeting (e.g. `Hi, {{ current_user.name }}`) and a
    **Logout** link → `url_for('logout')`.
  - **Logged out:** keep the existing **Sign in** + **Get started** links.

---

## 8. Files to Change

- `app.py` → `/logout` route + context processor
- `templates/base.html` → conditional navbar

---

## 9. Files to Create

- None

---

## 10. Dependencies

- No new pip packages
- Use `flask` (`session`, `redirect`, `url_for`) — already imported

---

## 11. Rules for Implementation

- Use `session.clear()` (not manual per-key deletes) so no stale keys remain.
- The context processor must not crash when no one is logged in (return `None`).
- No database changes; no new dependencies.
- Keep `/logout` idempotent and safe to hit when already logged out.

---

## 12. Expected Behavior

- A logged-in user sees their name + **Logout** in the navbar on every page.
- Clicking **Logout** clears the session and lands on `/`, now showing the logged-out navbar.
- Guests (not logged in) see the original **Sign in / Get started** navbar.

---

## 13. Error Handling Expectations

- `/logout` never errors, even with no active session — it always redirects to `/`.
- Templates render fine whether `current_user` is set or `None`.

---

## 14. Definition of Done

- [x] `/logout` clears the session and redirects to `/`.
- [x] Hitting `/logout` while logged out redirects without error.
- [x] A context processor exposes `current_user` (dict when logged in, else `None`) to all templates.
- [x] Navbar shows name + Logout when logged in.
- [x] Navbar shows Sign in / Get started when logged out.
- [x] After logout, a fresh request shows the logged-out navbar (session truly cleared).
- [x] No DB changes; no new dependencies; all existing routes still return 200.
