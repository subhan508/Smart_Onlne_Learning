"""
Unit tests for PostgreSQL Compatibility Layer in database/database.py
Verifies that the wrapper properly translates SQLite query semantics (? placeholders, lastrowid, DictRow)
to PostgreSQL equivalents.
"""

import pytest
from unittest.mock import MagicMock
from app import create_app
from database.database import (
    is_postgres,
    PostgresCursorWrapper,
    PostgresDBWrapper
)


def test_is_postgres_detection():
    """Test is_postgres properly detects PostgreSQL database URLs."""
    app = create_app()
    with app.app_context():
        # Default test app uses SQLite
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        assert not is_postgres()

        # When configured with PostgreSQL
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost:5432/testdb'
        assert is_postgres()

        # Legacy postgres:// scheme
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://user:pass@localhost:5432/testdb'
        assert is_postgres()


def test_postgres_cursor_wrapper():
    """Test PostgresCursorWrapper provides expected attributes and methods."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {'id': 42, 'name': 'Alice'}
    mock_cur.fetchall.return_value = [{'id': 42, 'name': 'Alice'}, {'id': 43, 'name': 'Bob'}]
    mock_cur.rowcount = 2

    wrapper = PostgresCursorWrapper(mock_cur, lastrowid=42)
    assert wrapper.lastrowid == 42
    assert wrapper.rowcount == 2
    assert wrapper.fetchone()['name'] == 'Alice'
    assert len(wrapper.fetchall()) == 2
    wrapper.close()
    mock_cur.close.assert_called_once()


def test_postgres_db_wrapper_placeholder_translation():
    """Test that PostgresDBWrapper converts '?' to '%s' and handles queries."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    wrapper = PostgresDBWrapper(mock_conn)

    # SELECT statement with ? placeholders
    wrapper.execute("SELECT * FROM users WHERE email = ? AND role = ?", ("test@example.com", "student"))
    mock_cur.execute.assert_called_once_with(
        "SELECT * FROM users WHERE email = %s AND role = %s",
        ("test@example.com", "student")
    )


def test_postgres_db_wrapper_insert_returning_id():
    """Test that INSERT statements have RETURNING id appended to populate lastrowid."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {'id': 99}
    mock_conn.cursor.return_value = mock_cur

    wrapper = PostgresDBWrapper(mock_conn)

    cursor_res = wrapper.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        ("Test User", "test@test.com")
    )

    # Verify query had RETURNING id appended
    executed_query = mock_cur.execute.call_args[0][0]
    assert "RETURNING id" in executed_query
    assert "%s" in executed_query
    assert "?" not in executed_query
    assert cursor_res.lastrowid == 99


def test_postgres_db_wrapper_commit_rollback():
    """Test commit, rollback, and close calls on underlying connection."""
    mock_conn = MagicMock()
    wrapper = PostgresDBWrapper(mock_conn)

    wrapper.commit()
    mock_conn.commit.assert_called_once()

    wrapper.rollback()
    mock_conn.rollback.assert_called_once()

    wrapper.close()
    mock_conn.close.assert_called_once()
