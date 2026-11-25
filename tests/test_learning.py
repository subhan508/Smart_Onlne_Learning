"""
Tests for learning features — Course viewing, quiz submission, score calculation.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.database import init_db, get_db, execute_db, query_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """Create application for testing with seeded data."""
    test_db_path = os.path.join(os.path.dirname(__file__), 'test_learning.db')
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    app = create_app()
    app.config['TESTING'] = True
    app.config['DATABASE'] = test_db_path

    with app.app_context():
        init_db(app)

        db = get_db()
        # Create a teacher
        db.execute(
            'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
            ('Teacher', 'teacher@test.com', generate_password_hash('pass123'), 'teacher')
        )
        # Create a student
        db.execute(
            'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
            ('Student', 'student@test.com', generate_password_hash('pass123'), 'student')
        )
        # Create a course
        db.execute(
            'INSERT INTO courses (title, description, teacher_id, is_published) VALUES (?, ?, 1, 1)',
            ('Test Course', 'A test course')
        )
        # Create a lesson
        db.execute(
            'INSERT INTO lessons (course_id, title, notes, order_number) VALUES (1, ?, ?, 1)',
            ('Test Lesson', 'Lesson notes content')
        )
        # Create a quiz
        db.execute(
            'INSERT INTO quizzes (course_id, lesson_id, title) VALUES (1, 1, ?)',
            ('Test Quiz',)
        )
        # Create questions and options
        db.execute(
            'INSERT INTO questions (quiz_id, question_text, order_number) VALUES (1, ?, 1)',
            ('What is 2+2?',)
        )
        db.execute('INSERT INTO options (question_id, option_text, is_correct) VALUES (1, ?, 0)', ('3',))
        db.execute('INSERT INTO options (question_id, option_text, is_correct) VALUES (1, ?, 1)', ('4',))
        db.execute('INSERT INTO options (question_id, option_text, is_correct) VALUES (1, ?, 0)', ('5',))

        # Enroll student
        db.execute('INSERT INTO enrollments (student_id, course_id) VALUES (2, 1)')

        db.commit()
        from database.database import close_db
        close_db()

        yield app

    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass


@pytest.fixture
def client(app):
    return app.test_client()


def login_student(client):
    client.post('/login', data={'email': 'student@test.com', 'password': 'pass123'})


def login_teacher(client):
    client.post('/login', data={'email': 'teacher@test.com', 'password': 'pass123'})


class TestCourseViewing:
    """Test course browsing and viewing."""

    def test_courses_page_loads(self, client):
        login_student(client)
        response = client.get('/learn/courses')
        assert response.status_code == 200
        assert b'Test Course' in response.data

    def test_course_detail_loads(self, client):
        login_student(client)
        response = client.get('/learn/course/1')
        assert response.status_code == 200
        assert b'Test Course' in response.data
        assert b'Test Lesson' in response.data

    def test_lesson_view_loads(self, client):
        login_student(client)
        response = client.get('/learn/lesson/1')
        assert response.status_code == 200
        assert b'Test Lesson' in response.data


class TestQuizSystem:
    """Test quiz taking and scoring."""

    def test_quiz_page_loads(self, client):
        login_student(client)
        response = client.get('/learn/quiz/1')
        assert response.status_code == 200
        assert b'Test Quiz' in response.data
        assert b'What is 2+2?' in response.data

    def test_quiz_submit_correct(self, client, app):
        login_student(client)

        with app.app_context():
            # Find the correct option ID (option_text = '4')
            correct = query_db(
                'SELECT id FROM options WHERE question_id = 1 AND is_correct = 1', one=True
            )

        response = client.post('/learn/quiz/1/submit', data={
            'question_1': str(correct['id'])
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'1/1' in response.data  # Score should be 1/1

    def test_quiz_submit_incorrect(self, client, app):
        login_student(client)

        with app.app_context():
            wrong = query_db(
                'SELECT id FROM options WHERE question_id = 1 AND is_correct = 0', one=True
            )

        response = client.post('/learn/quiz/1/submit', data={
            'question_1': str(wrong['id'])
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'0/1' in response.data  # Score should be 0/1


class TestCourseManagement:
    """Test teacher course management."""

    def test_teacher_create_course(self, client):
        login_teacher(client)
        response = client.post('/teacher/course/new', data={
            'title': 'New Course',
            'description': 'A new course',
            'category': 'Testing'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'New Course' in response.data

    def test_teacher_add_lesson(self, client):
        login_teacher(client)
        response = client.post('/teacher/course/1/lesson/new', data={
            'title': 'New Lesson',
            'description': 'Lesson desc',
            'video_url': '',
            'notes': 'Some notes'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Lesson' in response.data


class TestEnrollment:
    """Test course enrollment."""

    def test_enroll_in_course(self, client, app):
        login_student(client)

        # Create a new course for enrollment test
        with app.app_context():
            execute_db(
                'INSERT INTO courses (title, description, teacher_id, is_published) VALUES (?, ?, 1, 1)',
                ('Enroll Course', 'Test enrollment')
            )

        response = client.post('/learn/course/2/enroll', follow_redirects=True)
        assert response.status_code == 200
        assert b'enrolled' in response.data.lower() or b'Enroll Course' in response.data
