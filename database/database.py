"""
Database helper module for Smart Online Learning System.
Provides functions to connect, query, initialise, and migrate SQLite / PostgreSQL databases.
Seamlessly supports SQLite (local development and pytest) and PostgreSQL (Render cloud production).
"""

import os
import re
import sqlite3
from flask import g, current_app


POSTGRES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)",
    "CREATE INDEX IF NOT EXISTS idx_email_otps_email ON email_otps(email)",
    "CREATE INDEX IF NOT EXISTS idx_emotion_logs_student ON emotion_logs(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_emotion_logs_timestamp ON emotion_logs(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student ON quiz_attempts(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_id)",
    "CREATE INDEX IF NOT EXISTS idx_lessons_course ON lessons(course_id)",
    "CREATE INDEX IF NOT EXISTS idx_learning_progress_student ON learning_progress(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read)",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action, created_at)"
]


def is_postgres():
    """Check if the current application is configured to use PostgreSQL."""
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
    return uri.startswith(('postgresql://', 'postgres://', 'postgresql+'))


class DBRow(dict):
    """
    Row object supporting both dictionary key access and integer index access,
    mirroring the behavior of sqlite3.Row for PostgreSQL queries.
    """
    def __init__(self, mapping, values=None):
        super().__init__(mapping)
        self._values = tuple(values) if values is not None else tuple(mapping.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class PostgresCursorWrapper:
    """
    Wraps a database cursor to provide a sqlite3-compatible interface:
    - Dict-like and index-based row access (via DBRow or DictRow)
    - lastrowid property populated on INSERT statements
    - rowcount property
    - Standard fetchone(), fetchall(), close(), iteration
    """
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def _wrap(self, row):
        if row is None:
            return None
        if isinstance(row, DBRow):
            return row
        # If it's a psycopg2 DictRow, it already supports row['id'] and row[0]
        if hasattr(row, 'keys') and hasattr(row, '__getitem__'):
            try:
                _ = row[0]
                return row
            except (KeyError, TypeError):
                return DBRow(row)
        if hasattr(self._cursor, 'description') and self._cursor.description:
            cols = [col[0] if isinstance(col, tuple) else col.name for col in self._cursor.description]
            return DBRow(dict(zip(cols, row)), row)
        return row

    def fetchone(self):
        return self._wrap(self._cursor.fetchone())

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [self._wrap(r) for r in rows] if rows else []

    def close(self):
        self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __iter__(self):
        for row in self._cursor:
            yield self._wrap(row)


class PostgresDBWrapper:
    """
    Wraps a PostgreSQL connection (psycopg2 or psycopg) to provide a sqlite3.Connection-compatible interface:
    - Automatic translation of '?' parameter placeholders to '%s'
    - Automatic RETURNING id capture for INSERT statements so cursor.lastrowid works
    - commit(), rollback(), close()
    - executescript() for running multiple SQL statements
    """
    def __init__(self, conn, driver='psycopg2'):
        self._conn = conn
        self.driver = driver

    def execute(self, query, args=()):
        # Convert SQLite '?' placeholders to PostgreSQL '%s'
        pg_query = query.replace('?', '%s')
        args_tuple = tuple(args) if args is not None else ()

        if self.driver == 'psycopg2':
            import psycopg2.extras
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            cur = self._conn.cursor()

        # Check if INSERT statement without RETURNING clause
        is_insert = bool(re.search(r'^\s*INSERT\s+INTO\b', pg_query, re.IGNORECASE))
        has_returning = 'RETURNING' in pg_query.upper()

        if is_insert and not has_returning:
            # Append RETURNING id to capture lastrowid
            pg_query_with_returning = pg_query.rstrip().rstrip(';') + ' RETURNING id'
            try:
                cur.execute(pg_query_with_returning, args_tuple)
                row = cur.fetchone()
                lastrowid = None
                if row is not None:
                    if hasattr(row, 'keys') and 'id' in row.keys():
                        lastrowid = row['id']
                    elif isinstance(row, dict):
                        lastrowid = row.get('id')
                    elif isinstance(row, (tuple, list)):
                        lastrowid = row[0]
                    else:
                        try:
                            lastrowid = row[0]
                        except Exception:
                            lastrowid = None
                return PostgresCursorWrapper(cur, lastrowid=lastrowid)
            except Exception:
                # Fallback if table doesn't have an 'id' column
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                if self.driver == 'psycopg2':
                    import psycopg2.extras
                    cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                else:
                    cur = self._conn.cursor()
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
            raw_url = current_app.config['SQLALCHEMY_DATABASE_URI']
            # Convert SQLAlchemy dialect format (postgresql+psycopg2://) to libpq format (postgresql://)
            conn_url = re.sub(r'^postgresql\+[a-zA-Z0-9_]+://', 'postgresql://', raw_url)
            # Try psycopg2 first (standard production driver), fallback to psycopg (v3)
            try:
                import psycopg2
                import psycopg2.extras
                conn = psycopg2.connect(conn_url)
                g.db = PostgresDBWrapper(conn, driver='psycopg2')
            except ImportError:
                import psycopg
                conn = psycopg.connect(conn_url)
                g.db = PostgresDBWrapper(conn, driver='psycopg')
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
                else:
                    try:
                        db.execute("ALTER TABLE users ALTER COLUMN streak_days SET DEFAULT 0")
                        db.execute("UPDATE users SET streak_days = 0 WHERE streak_days IS NULL")
                    except Exception:
                        pass
                if 'last_active_date' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN last_active_date DATE DEFAULT NULL")
                if 'last_login' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP DEFAULT NULL")
                if 'is_active' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
                else:
                    try:
                        db.execute("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT 1")
                        db.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
                    except Exception:
                        pass

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

            cur = db.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'email_otps'
            """)
            otp_cols = {row['column_name'] for row in cur.fetchall()}
            if otp_cols:
                if 'attempts' in otp_cols:
                    try:
                        db.execute("ALTER TABLE email_otps ALTER COLUMN attempts SET DEFAULT 0")
                        db.execute("UPDATE email_otps SET attempts = 0 WHERE attempts IS NULL")
                    except Exception:
                        pass
                if 'max_attempts' in otp_cols:
                    try:
                        db.execute("ALTER TABLE email_otps ALTER COLUMN max_attempts SET DEFAULT 5")
                        db.execute("UPDATE email_otps SET max_attempts = 5 WHERE max_attempts IS NULL")
                    except Exception:
                        pass
                if 'is_used' in otp_cols:
                    try:
                        db.execute("ALTER TABLE email_otps ALTER COLUMN is_used SET DEFAULT 0")
                        db.execute("UPDATE email_otps SET is_used = 0 WHERE is_used IS NULL")
                    except Exception:
                        pass
                if 'otp_type' in otp_cols:
                    try:
                        db.execute("ALTER TABLE email_otps ALTER COLUMN otp_type SET DEFAULT 'registration'")
                    except Exception:
                        pass

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
                if 'is_active' not in user_cols:
                    db.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

            # Check courses table columns
            cur = db.execute("PRAGMA table_info(courses)")
            course_cols = {row['name'] for row in cur.fetchall()}
            if course_cols:
                if 'approval_status' not in course_cols:
                    db.execute("ALTER TABLE courses ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved'")
                if 'rejection_reason' not in course_cols:
                    db.execute("ALTER TABLE courses ADD COLUMN rejection_reason TEXT DEFAULT NULL")

            # Check email_otps table columns
            cur = db.execute("PRAGMA table_info(email_otps)")
            otp_cols = {row['name'] for row in cur.fetchall()}
            if otp_cols:
                if 'attempts' not in otp_cols:
                    db.execute("ALTER TABLE email_otps ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
                if 'max_attempts' not in otp_cols:
                    db.execute("ALTER TABLE email_otps ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 5")
                if 'is_used' not in otp_cols:
                    db.execute("ALTER TABLE email_otps ADD COLUMN is_used INTEGER NOT NULL DEFAULT 0")

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
    For PostgreSQL: uses SQLAlchemy models to ensure clean DDL with serial IDs,
    creates required indexes, and executes column migrations.
    For SQLite: executes schema.sql and runs column migrations.
    """
    if app is None:
        app = current_app._get_current_object()

    with app.app_context():
        if is_postgres():
            from database.models import db as sa_db
            sa_db.create_all()
            db = get_db()
            for idx_sql in POSTGRES_INDEXES:
                try:
                    db.execute(idx_sql)
                except Exception as e:
                    pass
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


def ensure_database_initialized(app):
    """
    Ensure all database tables exist and are properly migrated.
    Executed once during application startup in an app context.
    Safe, idempotent, and non-destructive:
    - Never drops existing tables or deletes existing data.
    - Creates missing tables with proper constraints and indexes.
    - Runs column migrations if upgrading from an older schema.
    - Automatically seeds initial accounts if the database is completely empty.
    """
    if app.config.get('TESTING'):
        # In test environments, test fixtures manage their own table lifecycle
        return

    with app.app_context():
        try:
            init_db(app)

            # Ensure essential courses and curriculum exist safely and idempotently
            try:
                course_check = query_db("SELECT COUNT(*) as cnt FROM courses", one=True)
                user_check = query_db("SELECT COUNT(*) as cnt FROM users", one=True)
                if not course_check or course_check['cnt'] == 0 or not user_check or user_check['cnt'] == 0:
                    print("[INFO] Restoring missing courses and curriculum...")
                    from database.seed import seed_all
                    seed_all(app)
                    print("[INFO] Courses and demonstration curriculum restored successfully.")
                else:
                    # Idempotent verification to ensure all core courses are published
                    from database.seed import seed_all
                    seed_all(app)
            except Exception as seed_err:
                print(f"[DB Warning] Course restoration check notice: {seed_err}")

            print("[INFO] Database initialization and schema verification complete.")
        except Exception as err:
            print(f"[DB Error] Failed to initialize database on startup: {err}")
            raise


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
