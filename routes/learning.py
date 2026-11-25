"""
Learning routes — Course browsing, enrollment, lesson viewing, quiz taking.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database.database import query_db, execute_db

learning_bp = Blueprint('learning', __name__)


@learning_bp.route('/courses')
@login_required
def courses():
    """Browse all published courses."""
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '')

    query = '''
        SELECT c.*, u.name as teacher_name,
               (SELECT COUNT(*) FROM lessons WHERE course_id = c.id) as lesson_count,
               (SELECT COUNT(DISTINCT e.student_id) FROM enrollments e WHERE e.course_id = c.id) as student_count
        FROM courses c
        JOIN users u ON c.teacher_id = u.id
        WHERE c.is_published = 1
    '''
    params = []

    if search:
        query += ' AND (c.title LIKE ? OR c.description LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    if category:
        query += ' AND c.category = ?'
        params.append(category)

    query += ' ORDER BY c.created_at DESC'

    all_courses = query_db(query, params)

    # Get distinct categories
    categories = query_db('SELECT DISTINCT category FROM courses WHERE is_published = 1 AND category IS NOT NULL')

    # Check which courses the student is enrolled in
    enrolled_ids = set()
    if current_user.role == 'student':
        enrolled = query_db('SELECT course_id FROM enrollments WHERE student_id = ?', [current_user.id])
        enrolled_ids = {row['course_id'] for row in enrolled}

    return render_template('courses.html', courses=all_courses,
                           categories=categories, enrolled_ids=enrolled_ids,
                           search=search, selected_category=category)


@learning_bp.route('/course/<int:course_id>')
@login_required
def course_detail(course_id):
    """View course details, lessons, and quizzes."""
    course = query_db('''
        SELECT c.*, u.name as teacher_name
        FROM courses c
        JOIN users u ON c.teacher_id = u.id
        WHERE c.id = ?
    ''', [course_id], one=True)

    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('learning.courses'))

    lessons = query_db(
        'SELECT * FROM lessons WHERE course_id = ? ORDER BY order_number',
        [course_id]
    )

    quizzes = query_db(
        'SELECT * FROM quizzes WHERE course_id = ? ORDER BY created_at',
        [course_id]
    )

    # Check enrollment
    is_enrolled = False
    progress = {}
    if current_user.role == 'student':
        enrollment = query_db(
            'SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?',
            [current_user.id, course_id], one=True
        )
        is_enrolled = enrollment is not None

        if is_enrolled:
            progress_rows = query_db(
                'SELECT lesson_id, is_completed FROM learning_progress WHERE student_id = ? AND course_id = ?',
                [current_user.id, course_id]
            )
            progress = {row['lesson_id']: row['is_completed'] for row in progress_rows}

    return render_template('course_detail.html', course=course, lessons=lessons,
                           quizzes=quizzes, is_enrolled=is_enrolled, progress=progress)


@learning_bp.route('/course/<int:course_id>/enroll', methods=['POST'])
@login_required
def enroll(course_id):
    """Enroll in a course."""
    if current_user.role != 'student':
        flash('Only students can enroll in courses.', 'warning')
        return redirect(url_for('learning.course_detail', course_id=course_id))

    existing = query_db(
        'SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?',
        [current_user.id, course_id], one=True
    )

    if existing:
        flash('You are already enrolled in this course.', 'info')
    else:
        execute_db(
            'INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)',
            (current_user.id, course_id)
        )
        flash('Successfully enrolled! Start learning now.', 'success')

    return redirect(url_for('learning.course_detail', course_id=course_id))


@learning_bp.route('/lesson/<int:lesson_id>')
@login_required
def lesson_view(lesson_id):
    """View a lesson — video, notes, webcam emotion detection."""
    lesson = query_db('SELECT * FROM lessons WHERE id = ?', [lesson_id], one=True)
    if not lesson:
        flash('Lesson not found.', 'danger')
        return redirect(url_for('learning.courses'))

    course = query_db('SELECT * FROM courses WHERE id = ?', [lesson['course_id']], one=True)

    # Get all lessons for navigation
    all_lessons = query_db(
        'SELECT id, title, order_number FROM lessons WHERE course_id = ? ORDER BY order_number',
        [lesson['course_id']]
    )

    # Find prev/next lessons
    prev_lesson = None
    next_lesson = None
    for i, l in enumerate(all_lessons):
        if l['id'] == lesson_id:
            if i > 0:
                prev_lesson = all_lessons[i - 1]
            if i < len(all_lessons) - 1:
                next_lesson = all_lessons[i + 1]
            break

    # Get quizzes associated with this lesson
    lesson_quizzes = query_db(
        'SELECT * FROM quizzes WHERE lesson_id = ? OR (course_id = ? AND lesson_id IS NULL)',
        [lesson_id, lesson['course_id']]
    )

    # Track progress
    if current_user.role == 'student':
        existing_progress = query_db(
            'SELECT id FROM learning_progress WHERE student_id = ? AND lesson_id = ?',
            [current_user.id, lesson_id], one=True
        )
        if not existing_progress:
            execute_db(
                'INSERT INTO learning_progress (student_id, lesson_id, course_id, is_completed) VALUES (?, ?, ?, 0)',
                (current_user.id, lesson_id, lesson['course_id'])
            )

    # Get recent emotions for this lesson
    recent_emotions = []
    if current_user.role == 'student':
        recent_emotions = query_db('''
            SELECT emotion, confidence, timestamp
            FROM emotion_logs
            WHERE student_id = ? AND lesson_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', [current_user.id, lesson_id])

    return render_template('lesson.html', lesson=lesson, course=course,
                           all_lessons=all_lessons, prev_lesson=prev_lesson,
                           next_lesson=next_lesson, lesson_quizzes=lesson_quizzes,
                           recent_emotions=recent_emotions)


@learning_bp.route('/lesson/<int:lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(lesson_id):
    """Mark a lesson as completed."""
    if current_user.role != 'student':
        flash('Only students can mark lessons complete.', 'warning')
        return redirect(url_for('learning.lesson_view', lesson_id=lesson_id))

    lesson = query_db('SELECT * FROM lessons WHERE id = ?', [lesson_id], one=True)
    if not lesson:
        flash('Lesson not found.', 'danger')
        return redirect(url_for('learning.courses'))

    # Update or insert progress
    existing = query_db(
        'SELECT id FROM learning_progress WHERE student_id = ? AND lesson_id = ?',
        [current_user.id, lesson_id], one=True
    )

    if existing:
        execute_db(
            'UPDATE learning_progress SET is_completed = 1 WHERE student_id = ? AND lesson_id = ?',
            (current_user.id, lesson_id)
        )
    else:
        execute_db(
            'INSERT INTO learning_progress (student_id, lesson_id, course_id, is_completed) VALUES (?, ?, ?, 1)',
            (current_user.id, lesson_id, lesson['course_id'])
        )

    flash('Lesson marked as complete!', 'success')
    return redirect(url_for('learning.lesson_view', lesson_id=lesson_id))


@learning_bp.route('/quiz/<int:quiz_id>')
@login_required
def take_quiz(quiz_id):
    """Display quiz questions."""
    quiz = query_db('SELECT * FROM quizzes WHERE id = ?', [quiz_id], one=True)
    if not quiz:
        flash('Quiz not found.', 'danger')
        return redirect(url_for('learning.courses'))

    course = query_db('SELECT * FROM courses WHERE id = ?', [quiz['course_id']], one=True)

    questions = query_db(
        'SELECT * FROM questions WHERE quiz_id = ? ORDER BY order_number',
        [quiz_id]
    )

    # Get options for each question
    questions_with_options = []
    for q in questions:
        options = query_db(
            'SELECT * FROM options WHERE question_id = ? ORDER BY id',
            [q['id']]
        )
        questions_with_options.append({
            'question': q,
            'options': options
        })

    # Previous attempts
    attempts = query_db('''
        SELECT * FROM quiz_attempts
        WHERE student_id = ? AND quiz_id = ?
        ORDER BY attempted_at DESC
    ''', [current_user.id, quiz_id])

    return render_template('quiz.html', quiz=quiz, course=course,
                           questions=questions_with_options, attempts=attempts)


@learning_bp.route('/quiz/<int:quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    """Submit quiz answers and calculate score."""
    if current_user.role != 'student':
        flash('Only students can submit quizzes.', 'warning')
        return redirect(url_for('learning.take_quiz', quiz_id=quiz_id))

    quiz = query_db('SELECT * FROM quizzes WHERE id = ?', [quiz_id], one=True)
    if not quiz:
        flash('Quiz not found.', 'danger')
        return redirect(url_for('learning.courses'))

    questions = query_db(
        'SELECT * FROM questions WHERE quiz_id = ? ORDER BY order_number',
        [quiz_id]
    )

    total_marks = len(questions)
    score = 0

    # Create attempt record
    attempt_id = execute_db(
        'INSERT INTO quiz_attempts (student_id, quiz_id, score, total_marks) VALUES (?, ?, 0, ?)',
        (current_user.id, quiz_id, total_marks)
    )

    results = []

    for q in questions:
        selected_option_id = request.form.get(f'question_{q["id"]}')
        is_correct = 0

        if selected_option_id:
            selected_option_id = int(selected_option_id)
            # Check if the selected option is correct
            option = query_db(
                'SELECT * FROM options WHERE id = ? AND question_id = ?',
                [selected_option_id, q['id']], one=True
            )
            if option and option['is_correct']:
                is_correct = 1
                score += 1

        # Record the answer
        execute_db(
            'INSERT INTO quiz_answers (attempt_id, question_id, selected_option_id, is_correct) VALUES (?, ?, ?, ?)',
            (attempt_id, q['id'], selected_option_id, is_correct)
        )

        # Get all options for result display
        options = query_db(
            'SELECT * FROM options WHERE question_id = ? ORDER BY id',
            [q['id']]
        )
        correct_option = next((o for o in options if o['is_correct']), None)

        results.append({
            'question': q,
            'options': options,
            'selected_id': selected_option_id,
            'is_correct': is_correct,
            'correct_option': correct_option
        })

    # Update score
    execute_db(
        'UPDATE quiz_attempts SET score = ? WHERE id = ?',
        (score, attempt_id)
    )

    return render_template('quiz_result.html', quiz=quiz, results=results,
                           score=score, total_marks=total_marks,
                           course_id=quiz['course_id'])
