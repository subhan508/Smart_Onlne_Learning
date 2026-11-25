"""
Database helper module for Smart Online Learning System.
Provides functions to connect, query, initialise, and migrate SQLite / SQLAlchemy database.
"""

import sqlite3
import os
from flask import g, current_app


def get_db():
    """
    Get a database connection for the current request.
    Stores the connection in Flask's 'g' object so it is reused
    within the same request and properly closed afterwards.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        # Return rows as sqlite3.Row objects (dict-like access)
        g.db.row_factory = sqlite3.Row
        # Enable foreign key support
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    """Close the database connection at the end of a request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def _migrate_existing_columns(db):
    """Add new columns to existing tables if upgrading from a previous schema."""
    try:
        # Check users table columns
        cur = db.execute("PRAGMA table_info(users)")
        user_cols = {row['name'] for row in cur.fetchall()}
        if 'status' not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'approved'")
        if 'rejection_reason' not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN rejection_reason TEXT DEFAULT NULL")
        if 'streak_days' not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN streak_days INTEGER NOT NULL DEFAULT 0")
        if 'last_active_date' not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN last_active_date DATE DEFAULT NULL")
        if 'last_login' not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP DEFAULT NULL")

        # Check courses table columns
        cur = db.execute("PRAGMA table_info(courses)")
        course_cols = {row['name'] for row in cur.fetchall()}
        if 'approval_status' not in course_cols:
            db.execute("ALTER TABLE courses ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved'")
        if 'rejection_reason' not in course_cols:
            db.execute("ALTER TABLE courses ADD COLUMN rejection_reason TEXT DEFAULT NULL")

        db.commit()
    except Exception as err:
        print(f"[DB Migration Warning] {err}")


def init_db(app=None):
    """
    Initialise the database by executing the schema SQL file.
    Creates all tables if they do not exist, and runs column migrations.
    """
    if app is None:
        app = current_app._get_current_object()

    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')

    with app.app_context():
        db = get_db()
        _migrate_existing_columns(db)
        with open(schema_path, 'r') as f:
            db.executescript(f.read())
        _migrate_existing_columns(db)
        db.commit()
        close_db()


def query_db(query, args=(), one=False):
    """
    Execute a SELECT query and return results.

    Args:
        query: SQL query string with ? placeholders.
        args: Tuple of arguments to bind.
        one: If True, return only the first row (or None).

    Returns:
        A list of sqlite3.Row objects, or a single Row if one=True.
    """
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """
    Execute an INSERT / UPDATE / DELETE query and commit.

    Args:
        query: SQL statement with ? placeholders.
        args: Tuple of arguments to bind.

    Returns:
        The lastrowid of the cursor (useful for INSERT).
    """
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid
