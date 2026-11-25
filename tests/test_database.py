"""
Tests for database operations — CRUD, relationships, data integrity.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.database import init_db, get_db, query_db, execute_db, close_db
from werkzeug.security import generate_password_hash, check_password_hash


@pytest.fixture
def app():
    test_db_path = os.path.join(os.path.dirname(__file__), 'test_db.db')
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    app = create_app()
    app.config['TESTING'] = True
    app.config['DATABASE'] = test_db_path

    with app.app_context():
        init_db(app)
        yield app

    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass


class TestUserCRUD:
    """Test user CRUD operations."""

    def test_create_user(self, app):
        with app.app_context():
            uid = execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Alice', 'alice@test.com', generate_password_hash('pass'), 'student')
            )
            assert uid > 0

    def test_read_user(self, app):
        with app.app_context():
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Bob', 'bob@test.com', generate_password_hash('pass'), 'teacher')
            )
            user = query_db('SELECT * FROM users WHERE email = ?', ['bob@test.com'], one=True)
            assert user is not None
            assert user['name'] == 'Bob'
            assert user['role'] == 'teacher'

    def test_update_user(self, app):
        with app.app_context():
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Carol', 'carol@test.com', generate_password_hash('pass'), 'student')
            )
            execute_db(
                'UPDATE users SET name = ? WHERE email = ?',
                ('Carol Updated', 'carol@test.com')
            )
            user = query_db('SELECT * FROM users WHERE email = ?', ['carol@test.com'], one=True)
            assert user['name'] == 'Carol Updated'

    def test_delete_user(self, app):
        with app.app_context():
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Dave', 'dave@test.com', generate_password_hash('pass'), 'student')
            )
            execute_db('DELETE FROM users WHERE email = ?', ['dave@test.com'])
            user = query_db('SELECT * FROM users WHERE email = ?', ['dave@test.com'], one=True)
            assert user is None

    def test_password_hash(self, app):
        with app.app_context():
            pw_hash = generate_password_hash('secret123')
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Eve', 'eve@test.com', pw_hash, 'student')
            )
            user = query_db('SELECT * FROM users WHERE email = ?', ['eve@test.com'], one=True)
            assert check_password_hash(user['password_hash'], 'secret123')
            assert not check_password_hash(user['password_hash'], 'wrong')

    def test_unique_email_constraint(self, app):
        with app.app_context():
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('User1', 'dup@test.com', generate_password_hash('pass'), 'student')
            )
            with pytest.raises(Exception):
                execute_db(
                    'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                    ('User2', 'dup@test.com', generate_password_hash('pass'), 'student')
                )


class TestCourseCRUD:
    """Test course CRUD operations."""

    def test_create_course(self, app):
        with app.app_context():
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Teacher', 'teach@test.com', generate_password_hash('pass'), 'teacher')
            )
            cid = execute_db(
                'INSERT INTO courses (title, description, teacher_id) VALUES (?, ?, 1)',
                ('Test Course', 'Description')
            )
            assert cid > 0

    def test_course_teacher_relationship(self, app):
        with app.app_context():
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Teacher', 'teach2@test.com', generate_password_hash('pass'), 'teacher')
            )
            execute_db(
                'INSERT INTO courses (title, description, teacher_id) VALUES (?, ?, 1)',
                ('Related Course', 'Desc')
            )
            course = query_db('''
                SELECT c.*, u.name as teacher_name
                FROM courses c JOIN users u ON c.teacher_id = u.id
                WHERE c.title = ?
            ''', ['Related Course'], one=True)
            assert course['teacher_name'] == 'Teacher'


class TestEmotionLogs:
    """Test emotion log operations."""

    def test_create_emotion_log(self, app):
        with app.app_context():
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Student', 'stu@test.com', generate_password_hash('pass'), 'student')
            )
            eid = execute_db(
                'INSERT INTO emotion_logs (student_id, emotion, confidence) VALUES (?, ?, ?)',
                (1, 'Happy', 0.85)
            )
            assert eid > 0

    def test_emotion_distribution_query(self, app):
        with app.app_context():
            execute_db(
                'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                ('Student', 'stu2@test.com', generate_password_hash('pass'), 'student')
            )
            for emotion in ['Happy', 'Happy', 'Sad', 'Confused', 'Happy']:
                execute_db(
                    'INSERT INTO emotion_logs (student_id, emotion, confidence) VALUES (?, ?, ?)',
                    (1, emotion, 0.7)
                )

            dist = query_db('''
                SELECT emotion, COUNT(*) as count
                FROM emotion_logs WHERE student_id = 1
                GROUP BY emotion ORDER BY count DESC
            ''')
            assert dist[0]['emotion'] == 'Happy'
            assert dist[0]['count'] == 3
