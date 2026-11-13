"""
SQLite connection management and transaction helpers.

Connections are opened in autocommit mode (isolation_level=None) and every
multi-statement write is wrapped in `transaction()`, which issues
BEGIN IMMEDIATE so that concurrent writers are serialised by SQLite and queue
processing can never assign the same complaint twice.
"""
import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")


def connect(path):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


@contextmanager
def transaction(conn):
    """Run a block atomically. Nested calls join the outer transaction."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def create_schema(conn):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        conn.executescript(fh.read())


def is_initialized(conn):
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name IN "
        "('users','administrators','campus_zones','routing_table','complaints',"
        "'complaint_history','waiting_queue','audit_logs')"
    ).fetchone()
    if row["n"] < 8:
        return False
    return conn.execute("SELECT COUNT(*) AS n FROM campus_zones").fetchone()["n"] > 0


def row_to_dict(row):
    return dict(row) if row is not None else None


# ---------------------------------------------------------------- Flask glue
def get_db():
    from flask import current_app, g
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    from flask import g
    db = g.pop("db", None)
    if db is not None:
        db.close()
