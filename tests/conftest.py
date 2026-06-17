"""Shared fixtures for the backend-connection tests.

Each test runs against an isolated temp SQLite DB. We monkeypatch
``database.db.DB_PATH`` to a tmp file; ``get_db()`` reads that global at call
time, so both the query helpers and the Flask route hit the temp DB.
"""

import sqlite3

import pytest

import database.db as db_module
import app as app_module


@pytest.fixture
def db_path(monkeypatch, tmp_path):
    """Point the data layer at a fresh temp DB seeded with the demo data."""
    path = tmp_path / "test_spendly.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(path))
    db_module.init_db()
    db_module.seed_db()
    return str(path)


@pytest.fixture
def raw_conn(db_path):
    """Raw connection to the temp DB for computing expected values in tests."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def seed_user_id(raw_conn):
    """The id of the seeded demo user."""
    row = raw_conn.execute(
        "SELECT id FROM users WHERE email = 'demo@spendly.com'"
    ).fetchone()
    return row["id"]


@pytest.fixture
def empty_user_id(raw_conn):
    """A freshly created user that has no expenses."""
    cur = raw_conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Empty User", "empty@spendly.com", "x"),
    )
    raw_conn.commit()
    return cur.lastrowid


@pytest.fixture
def client(db_path):
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    return app_module.app.test_client()


@pytest.fixture
def auth_client(client, seed_user_id):
    """Test client with the seed user logged in."""
    with client.session_transaction() as sess:
        sess["user_id"] = seed_user_id
        sess["user_name"] = "Demo User"
    return client
