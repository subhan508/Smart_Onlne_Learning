"""
Database helper module for Smart Online Learning System.
Provides functions to connect, query, initialise, and migrate SQLite / PostgreSQL databases.
Seamlessly supports SQLite (local development and pytest) and PostgreSQL (Render cloud production).
"""

import os
import re
import sqlite3
from flask import g, current_app


def is_postgres():
    """Check if the current application is configured to use PostgreSQL."""
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
    return uri.startswith('postgresql://') or uri.startswith('postgres://')


class PostgresCursorWrapper:
    """
    Wraps a psycopg2 cursor to provide a sqlite3-compatible interface:
    - Dict-like row access (via psycopg2.extras.DictCursor)
    - lastrowid property populated on INSERT statements
    - rowcount property
    - Standard fetchone(), fetchall(), close(), iteration
    """
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __iter__(self):
        return iter(self._cursor)


class PostgresDBWrapper:
    """
    Wraps a psycopg2 connection to provide a sqlite3.Connection-compatible interface:
    - Automatic translation of '?' parameter placeholders to '%s'
    - Automatic RETURNING id capture for INSERT statements so cursor.lastrowid works
    - commit(), rollback(), close()
    - executescript() for running multiple SQL statements
    """
    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, args=()):
        import psycopg2.extras

        # Convert SQLite '?' placeholders to psycopg2 '%s'
        pg_query = query.replace('?', '%s')
        args_tuple = tuple(args) if args is not None else ()

        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Check if INSERT statement without RETURNING clause
        is_insert = bool(re.search(r'^\s*INSERT\s+INTO\b', pg_query, re.IGNORECASE))
        has_returning = 'RETURNING' in pg_query.upper()

        if is_insert and not has_returning:
            # Append RETURNING id to capture lastrowid
            pg_query_with_returning = pg_query.rstrip().rstrip(';') + ' RETURNING id'
            try:
                cur.execute(pg_query_with_returning, args_tuple)
                row = cur.fetchone()
                lastrowid = row['id'] if row and 'id' in row.keys() else (row[0] if row else None)
                return PostgresCursorWrapper(cur, lastrowid=lastrowid)
            except Exception:
                # Fallback if table doesn't have an 'id' column
                self._conn.rollback()
                cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cur.execute(pg_query, args_tuple)
                return PostgresCursorWrapper(cur)
        else:
            cur.execute(pg_query, args_tuple)
            return PostgresCursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def executescript(self, script):
        cur = self._conn.cursor()
        cur.execute(script)
        self._conn.commit()
        cur.close()


def get_db():
    """
    Get a database connection for the current request.
    Stores the connection in Flask's 'g' object so it is reused
    within the same request and properly closed afterwards.
    Supports both SQLite and PostgreSQL automatically.
    """
    if 'db' not in g:
        if is_postgres():
            import psycopg2
            db_url = current_app.config['SQLALCHEMY_DATABASE_URI']
            conn = psycopg2.connect(db_url)
            g.db = PostgresDBWrapper(conn)
        else:
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
        if is_postgres():
            cur = db.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'users'
            """)
            user_cols = {row['column_name'] for row in cur.fetchall()}
            if user_cols:
                if 'status' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'approved'")
                if 'rejection_reason' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN rejection_reason TEXT DEFAULT NULL")
                if 'streak_days' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN streak_days INTEGER NOT NULL DEFAULT 0")
                if 'last_active_date' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN last_active_date DATE DEFAULT NULL")
                if 'last_login' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP DEFAULT NULL")

            cur = db.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'courses'
            """)
            course_cols = {row['column_name'] for row in cur.fetchall()}
            if course_cols:
                if 'approval_status' not in course_cols:
                    db.execute("ALTER TABLE courses ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'approved'")
                if 'rejection_reason' not in course_cols:
                    db.execute("ALTER TABLE courses ADD COLUMN rejection_reason TEXT DEFAULT NULL")

            db.commit()
        else:
            # SQLite migration check
            cur = db.execute("PRAGMA table_info(users)")
            user_cols = {row['name'] for row in cur.fetchall()}
            if user_cols:
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
            if course_cols:
                if 'approval_status' not in course_cols:
                    db.execute("ALTER TABLE courses ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved'")
                if 'rejection_reason' not in course_cols:
                    db.execute("ALTER TABLE courses ADD COLUMN rejection_reason TEXT DEFAULT NULL")

            db.commit()
    except Exception as err:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[DB Migration Warning] {err}")


def init_db(app=None):
    """
    Initialise the database by creating all tables and running column migrations.
    For PostgreSQL: uses SQLAlchemy models to ensure clean DDL with serial IDs.
    For SQLite: executes schema.sql.
    """
    if app is None:
        app = current_app._get_current_object()

    with app.app_context():
        if is_postgres():
            from database.models import db as sa_db
            sa_db.create_all()
            db = get_db()
            _migrate_existing_columns(db)
            db.commit()
            close_db()
        else:
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
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
    Works seamlessly on both SQLite and PostgreSQL.

    Args:
        query: SQL query string with ? placeholders.
        args: Tuple/list of arguments to bind.
        one: If True, return only the first row (or None).

    Returns:
        A list of row objects, or a single row if one=True.
    """
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """
    Execute an INSERT / UPDATE / DELETE query and commit.
    Works seamlessly on both SQLite and PostgreSQL.

    Args:
        query: SQL statement with ? placeholders.
        args: Tuple/list of arguments to bind.

    Returns:
        The lastrowid of the cursor (for INSERT) or rowcount.
    """
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    lastrowid = getattr(cur, 'lastrowid', None)
    cur.close()
    return lastrowid
