"""
Unit tests for PostgreSQL Compatibility & Driver Configuration in SmartLearn.
Verifies:
1. normalize_database_url converts Render PostgreSQL URLs to 'postgresql+psycopg2://'
   so SQLAlchemy explicitly uses the installed psycopg2-binary driver.
2. PostgreSQL driver (psycopg2) availability and SQLAlchemy integration.
3. DBRow and PostgresCursorWrapper support both dict keys and numeric indexing.
4. PostgresDBWrapper properly translates '?' to '%s' and handles RETURNING id.
5. User model works seamlessly with returned PostgreSQL dict rows.
"""

import pytest
from unittest.mock import MagicMock
from app import create_app
from config import normalize_database_url
from database.database import (
    is_postgres,
    DBRow,
    PostgresCursorWrapper,
    PostgresDBWrapper
)


def test_normalize_database_url_cases():
    """Verify normalize_database_url maps to postgresql+psycopg2:// and handles edge cases."""
    fallback = "sqlite:///smart_learn.db"

    # None, empty, whitespace fall back to SQLite cleanly
    assert normalize_database_url(None, "smart_learn.db") == fallback
    assert normalize_database_url("", "smart_learn.db") == fallback
    assert normalize_database_url("   ", "smart_learn.db") == fallback
    assert normalize_database_url('""', "smart_learn.db") == fallback
    assert normalize_database_url("''", "smart_learn.db") == fallback

    # Legacy Render/Railway postgres:// is converted to postgresql+psycopg2://
    raw_legacy = "postgres://user:secret@dpg-1234.render.com:5432/smartlearn"
    expected = "postgresql+psycopg2://user:secret@dpg-1234.render.com:5432/smartlearn"
    assert normalize_database_url(raw_legacy, "smart_learn.db") == expected

    # Quoted URLs are stripped properly
    quoted_legacy = '"postgres://user:secret@dpg-1234.render.com:5432/smartlearn"'
    assert normalize_database_url(quoted_legacy, "smart_learn.db") == expected

    single_quoted = "'postgresql://user:secret@dpg-1234.render.com:5432/smartlearn'"
    assert normalize_database_url(single_quoted, "smart_learn.db") == expected

    # Valid PostgreSQL URL is mapped to postgresql+psycopg2://
    clean_pg = "postgresql://user:secret@localhost:5432/smartlearn"
    assert normalize_database_url(clean_pg, "smart_learn.db") == "postgresql+psycopg2://user:secret@localhost:5432/smartlearn"


def test_normalize_database_url_invalid_raises_helpful_error():
    """Verify that an invalid database URL string raises a descriptive ValueError."""
    with pytest.raises(ValueError) as excinfo:
        normalize_database_url("this-is-not-a-valid-database-url", "smart_learn.db")

    error_msg = str(excinfo.value)
    assert "Invalid DATABASE_URL configuration" in error_msg
    assert "this-is-not-a-valid-database-url" in error_msg
    assert "postgresql://user:password@host:port/database" in error_msg


def test_psycopg2_driver_and_sqlalchemy_dialect():
    """Verify psycopg2 is resolved by SQLAlchemy when using postgresql+psycopg2://."""
    import psycopg2
    import sqlalchemy
    from sqlalchemy.engine import make_url

    assert hasattr(psycopg2, 'connect')
    assert hasattr(psycopg2, '__version__')

    url = make_url('postgresql+psycopg2://user:pass@localhost:5432/dbname')
    assert url.get_driver_name() == 'psycopg2'

    # Engine creation should succeed with driver 'psycopg2' without No module named 'psycopg'
    engine = sqlalchemy.create_engine('postgresql+psycopg2://user:pass@localhost:5432/dbname')
    assert engine.dialect.name == 'postgresql'
    assert engine.dialect.driver == 'psycopg2'


def test_is_postgres_detection():
    """Test is_postgres properly detects PostgreSQL database URLs."""
    app = create_app()
    with app.app_context():
        # Default test app uses SQLite
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        assert not is_postgres()

        # Standard PostgreSQL
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost:5432/testdb'
        assert is_postgres()

        # Legacy postgres:// scheme
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://user:pass@localhost:5432/testdb'
        assert is_postgres()

        # Driver-explicit URL
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://user:pass@localhost:5432/testdb'
        assert is_postgres()


def test_db_row_dual_access():
    """Verify DBRow supports both dict key and numeric index access."""
    row = DBRow({'id': 1, 'email': 'student@smartlearn.com', 'role': 'student'})
    assert row['id'] == 1
    assert row[0] == 1
    assert row['email'] == 'student@smartlearn.com'
    assert row[1] == 'student@smartlearn.com'
    assert row['role'] == 'student'
    assert row[2] == 'student'
    assert list(row.keys()) == ['id', 'email', 'role']
    assert 'email' in row.keys()


def test_user_model_with_db_row():
    """Verify Flask-Login User model correctly instantiates from a PostgreSQL row."""
    app = create_app()
    User = app.User

    fake_row = DBRow({
        'id': 42,
        'name': 'Sarah Connor',
        'email': 'sarah@smartlearn.com',
        'password_hash': 'hash123',
        'role': 'teacher',
        'status': 'approved',
        'rejection_reason': None,
        'is_active': 1
    })

    user = User(fake_row)
    assert user.id == 42
    assert user.name == 'Sarah Connor'
    assert user.email == 'sarah@smartlearn.com'
    assert user.role == 'teacher'
    assert user.status == 'approved'
    assert user.is_active is True
    assert user.is_approved is True
    assert user.get_id() == '42'


def test_postgres_cursor_wrapper():
    """Test PostgresCursorWrapper wraps tuples/dicts into DBRows and exposes cursor API."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {'id': 42, 'name': 'Alice'}
    mock_cur.fetchall.return_value = [{'id': 42, 'name': 'Alice'}, {'id': 43, 'name': 'Bob'}]
    mock_cur.rowcount = 2

    wrapper = PostgresCursorWrapper(mock_cur, lastrowid=42)
    assert wrapper.lastrowid == 42
    assert wrapper.rowcount == 2
    row = wrapper.fetchone()
    assert row['name'] == 'Alice'
    assert row[1] == 'Alice'
    rows = wrapper.fetchall()
    assert len(rows) == 2
    assert rows[1]['name'] == 'Bob'
    wrapper.close()
    mock_cur.close.assert_called_once()


def test_postgres_db_wrapper_placeholder_translation():
    """Test that PostgresDBWrapper converts '?' to '%s'."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    wrapper = PostgresDBWrapper(mock_conn, driver='psycopg2')

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

    wrapper = PostgresDBWrapper(mock_conn, driver='psycopg2')

    cursor_res = wrapper.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        ("Test User", "test@test.com")
    )

    executed_query = mock_cur.execute.call_args[0][0]
    assert "RETURNING id" in executed_query
    assert "%s" in executed_query
    assert "?" not in executed_query
    assert cursor_res.lastrowid == 99


def test_postgres_db_wrapper_commit_rollback():
    """Test commit, rollback, and close calls on underlying connection."""
    mock_conn = MagicMock()
    wrapper = PostgresDBWrapper(mock_conn, driver='psycopg2')

    wrapper.commit()
    mock_conn.commit.assert_called_once()

    wrapper.rollback()
    mock_conn.rollback.assert_called_once()

    wrapper.close()
    mock_conn.close.assert_called_once()


def test_ensure_database_initialized_idempotent(tmp_path):
    """Verify ensure_database_initialized creates tables and is safely idempotent."""
    db_file = str(tmp_path / "test_init.db")
    app = create_app()
    app.config['DATABASE'] = db_file
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_file}"
    app.config['TESTING'] = False

    from database.database import ensure_database_initialized, query_db

    ensure_database_initialized(app)
    with app.app_context():
        users = query_db("SELECT COUNT(*) as cnt FROM users", one=True)
        assert users is not None
        assert users['cnt'] > 0
        first_count = users['cnt']

    # Second run to test idempotency
    ensure_database_initialized(app)
    with app.app_context():
        users2 = query_db("SELECT COUNT(*) as cnt FROM users", one=True)
        assert users2['cnt'] == first_count


def test_user_schema_server_defaults_and_registration(tmp_path):
    """Verify User and EmailOTP models have server_defaults set and registration generates valid OTP record."""
    from database.models import User, EmailOTP
    from database.database import query_db, init_db

    # Verify SQLAlchemy model column has server_default
    is_active_col = User.__table__.columns['is_active']
    assert is_active_col.server_default is not None
    assert str(is_active_col.server_default.arg) == '1'

    attempts_col = EmailOTP.__table__.columns['attempts']
    assert attempts_col.server_default is not None
    assert str(attempts_col.server_default.arg) == '0'

    db_file = str(tmp_path / "test_reg.db")
    app = create_app()
    app.config['DATABASE'] = db_file
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_file}"
    app.config['TESTING'] = True

    with app.app_context():
        init_db(app)

    test_client = app.test_client()

    # Register a new user
    response = test_client.post('/register', data={
        'name': 'Active Test User',
        'email': 'activetest@example.com',
        'password': 'SecurePassword123!',
        'confirm_password': 'SecurePassword123!',
        'role': 'student'
    }, follow_redirects=True)
    assert response.status_code == 200

    # Query directly from DB to verify is_active value in table
    with app.app_context():
        user = query_db("SELECT * FROM users WHERE email = ?", ['activetest@example.com'], one=True)
        assert user is not None
        assert user['is_active'] == 1
        assert user['status'] == 'unverified'

        # Verify OTP was inserted with attempts=0 and correct values
        otp = query_db("SELECT * FROM email_otps WHERE email = ?", ['activetest@example.com'], one=True)
        assert otp is not None
        assert otp['attempts'] == 0
        assert otp['max_attempts'] == 5
        assert otp['is_used'] == 0
        assert otp['otp_type'] == 'registration'


def test_learning_progress_server_default_and_lesson_flow(tmp_path):
    """Verify learning_progress and schema server_defaults and lesson view tracking."""
    from database.models import LearningProgress, Course, Recommendation
    from database.database import query_db, init_db

    # Verify SQLAlchemy model column has server_default
    lp_col = LearningProgress.__table__.columns['is_completed']
    assert lp_col.server_default is not None
    assert str(lp_col.server_default.arg) == '0'

    course_appr_col = Course.__table__.columns['approval_status']
    assert course_appr_col.server_default is not None
    assert str(course_appr_col.server_default.arg) == 'approved'

    rec_col = Recommendation.__table__.columns['is_dismissed']
    assert rec_col.server_default is not None
    assert str(rec_col.server_default.arg) == '0'

    db_file = str(tmp_path / "test_flow.db")
    app = create_app()
    app.config['DATABASE'] = db_file
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_file}"
    app.config['TESTING'] = True
    app.config['DEMO_MODE'] = True

    with app.app_context():
        init_db(app)
        from database.seed import seed_all
        seed_all(app)

    client = app.test_client()

    # 1. Login demo account
    login_res = client.post('/login', data={'email': 'demo@smartlearn.com', 'password': 'Demo1234!'}, follow_redirects=True)
    assert login_res.status_code == 200

    # 2. Courses catalog
    courses_res = client.get('/learn/courses')
    assert courses_res.status_code == 200
    assert b'Introduction to Python Programming' in courses_res.data

    # 3. Course detail
    course_detail_res = client.get('/learn/course/1')
    assert course_detail_res.status_code == 200
    assert b'Start Learning' in course_detail_res.data

    # 4. Lesson view (verifies is_completed=0 progress creation without NotNullViolation)
    lesson_res = client.get('/learn/lesson/1')
    assert lesson_res.status_code == 200
    assert b'webcamVideo' in lesson_res.data
    assert b'emotionLabel' in lesson_res.data
    assert b'confidenceValue' in lesson_res.data

    with app.app_context():
        lp = query_db('SELECT * FROM learning_progress WHERE lesson_id = 1', one=True)
        assert lp is not None
        assert lp['is_completed'] == 0

    # 5. Mark lesson complete
    complete_res = client.post('/learn/lesson/1/complete', follow_redirects=True)
    assert complete_res.status_code == 200

    with app.app_context():
        lp_after = query_db('SELECT * FROM learning_progress WHERE lesson_id = 1', one=True)
        assert lp_after is not None
        assert lp_after['is_completed'] == 1


def test_detect_emotion_api_endpoint(tmp_path):
    """Verify emotion detection endpoint returns prediction, confidence, and stores logs."""
    import base64
    import cv2
    import numpy as np
    from database.database import query_db, init_db

    db_file = str(tmp_path / "test_emotion_api.db")
    app = create_app()
    app.config['DATABASE'] = db_file
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_file}"
    app.config['TESTING'] = True
    app.config['DEMO_MODE'] = True

    with app.app_context():
        init_db(app)
        from database.seed import seed_all
        seed_all(app)

    client = app.test_client()

    # Login demo student
    client.post('/login', data={'email': 'demo@smartlearn.com', 'password': 'Demo1234!'}, follow_redirects=True)

    # Synthetic face frame
    img = np.full((240, 320, 3), 128, dtype=np.uint8)
    cv2.ellipse(img, (160, 120), (50, 70), 0, 0, 360, (200, 200, 200), -1)
    cv2.circle(img, (140, 100), 8, (50, 50, 50), -1)
    cv2.circle(img, (180, 100), 8, (50, 50, 50), -1)
    cv2.ellipse(img, (160, 150), (25, 10), 0, 0, 180, (50, 50, 50), 3)

    _, buffer = cv2.imencode('.jpg', img)
    b64_str = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')

    res = client.post('/api/detect_emotion', json={
        'image': b64_str,
        'course_id': 1,
        'lesson_id': 1
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'emotion' in data
    assert 'confidence' in data
    assert 'recommendation' in data
    assert 'engagement' in data

    with app.app_context():
        log = query_db('SELECT * FROM emotion_logs WHERE lesson_id = 1', one=True)
        assert log is not None
        assert log['emotion'] == data['emotion']




