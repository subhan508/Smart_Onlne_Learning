"""
Tests for authentication — Registration, Login, Logout, Role Permissions.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.database import init_db, get_db, execute_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """Create application for testing."""
    test_db_path = os.path.join(os.path.dirname(__file__), 'test_auth.db')
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    app = create_app()
    app.config['TESTING'] = True
    app.config['DATABASE'] = test_db_path
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        init_db(app)

    yield app

    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestRegistration:
    """Test user registration."""

    def test_register_page_loads(self, client):
        response = client.get('/register')
        assert response.status_code == 200
        assert b'Create Account' in response.data

    def test_register_student(self, client):
        response = client.post('/register', data={
            'name': 'Test Student',
            'email': 'test@student.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'student'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Verify Your Email' in response.data

    def test_register_teacher(self, client):
        response = client.post('/register', data={
            'name': 'Test Teacher',
            'email': 'test@teacher.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'teacher'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Verify Your Email' in response.data

    def test_register_duplicate_email(self, client):
        client.post('/register', data={
            'name': 'User One',
            'email': 'dup@test.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'student'
        })
        response = client.post('/register', data={
            'name': 'User Two',
            'email': 'dup@test.com',
            'password': 'StrongP@ss456!',
            'confirm_password': 'StrongP@ss456!',
            'role': 'student'
        }, follow_redirects=True)
        assert b'already exists' in response.data

    def test_register_password_mismatch(self, client):
        response = client.post('/register', data={
            'name': 'Test User',
            'email': 'mismatch@test.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'DifferentP@ss123!',
            'role': 'student'
        }, follow_redirects=True)
        assert b'Passwords do not match' in response.data

    def test_register_short_password(self, client):
        response = client.post('/register', data={
            'name': 'Test User',
            'email': 'short@test.com',
            'password': '123',
            'confirm_password': '123',
            'role': 'student'
        }, follow_redirects=True)
        assert b'at least 8 characters' in response.data

    def test_register_invalid_role(self, client):
        response = client.post('/register', data={
            'name': 'Test User',
            'email': 'invalid@test.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'admin'
        }, follow_redirects=True)
        assert b'Invalid role' in response.data or b'Only Students and Teachers can register' in response.data


class TestLogin:
    """Test user login."""

    def _create_approved_user(self, app, email='test@user.com', password='StrongP@ss123!', role='student'):
        with app.app_context():
            pwd_hash = generate_password_hash(password)
            execute_db(
                "INSERT INTO users (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, 'approved')",
                ('Test User', email, pwd_hash, role)
            )

    def test_login_page_loads(self, client):
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Welcome Back' in response.data

    def test_login_success(self, app, client):
        self._create_approved_user(app)
        response = client.post('/login', data={
            'email': 'test@user.com',
            'password': 'StrongP@ss123!'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Welcome back' in response.data

    def test_login_wrong_password(self, app, client):
        self._create_approved_user(app)
        response = client.post('/login', data={
            'email': 'test@user.com',
            'password': 'WrongPassword123!'
        }, follow_redirects=True)
        assert b'Invalid email or password' in response.data

    def test_login_nonexistent_user(self, client):
        response = client.post('/login', data={
            'email': 'noone@test.com',
            'password': 'StrongP@ss123!'
        }, follow_redirects=True)
        assert b'Invalid email or password' in response.data


class TestLogout:
    """Test user logout."""

    def test_logout(self, app, client):
        with app.app_context():
            pwd_hash = generate_password_hash('StrongP@ss123!')
            execute_db(
                "INSERT INTO users (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, 'approved')",
                ('Test User', 'logout@test.com', pwd_hash, 'student')
            )
        client.post('/login', data={
            'email': 'logout@test.com',
            'password': 'StrongP@ss123!'
        })

        response = client.get('/logout', follow_redirects=True)
        assert response.status_code == 200
        assert b'logged out' in response.data


class TestRolePermissions:
    """Test role-based access control."""

    def _login_as(self, app, client, email, role='student'):
        with app.app_context():
            pwd_hash = generate_password_hash('StrongP@ss123!')
            execute_db(
                "INSERT INTO users (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, 'approved')",
                (f'User {role}', email, pwd_hash, role)
            )
        client.post('/login', data={
            'email': email,
            'password': 'StrongP@ss123!'
        })

    def test_student_cannot_access_teacher_dashboard(self, app, client):
        self._login_as(app, client, 'student@perm.com', role='student')
        response = client.get('/teacher/dashboard', follow_redirects=True)
        assert b'Access denied' in response.data or response.status_code == 302

    def test_student_cannot_access_admin_dashboard(self, app, client):
        self._login_as(app, client, 'student@perm2.com', role='student')
        response = client.get('/admin/dashboard', follow_redirects=True)
        assert b'Access denied' in response.data or response.status_code == 302

    def test_teacher_cannot_access_admin_dashboard(self, app, client):
        self._login_as(app, client, 'teacher@perm.com', role='teacher')
        response = client.get('/admin/dashboard', follow_redirects=True)
        assert b'Access denied' in response.data or response.status_code == 302

    def test_unauthenticated_redirect(self, client):
        response = client.get('/student/dashboard', follow_redirects=True)
        assert b'Please log in' in response.data or b'login' in response.data.lower()
