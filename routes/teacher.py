"""
Teacher routes — Dashboard, course management, student analytics.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database.database import query_db, execute_db

teacher_bp = Blueprint('teacher', __name__)


def teacher_required(f):
    """Decorator: only allow teachers."""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'teacher':
            flash('Access denied. Teachers only.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


@teacher_bp.route('/dashboard')
@teacher_required
def dashboard():
    """Teacher dashboard — overview of courses, students, emotions."""
    teacher_id = current_user.id

    # My courses
    courses = query_db('''
        SELECT c.*,
               (SELECT COUNT(DISTINCT e.student_id) FROM enrollments e WHERE e.course_id = c.id) as student_count,
               (SELECT COUNT(*) FROM lessons WHERE course_id = c.id) as lesson_count,
               (SELECT COUNT(*) FROM quizzes WHERE course_id = c.id) as quiz_count
        FROM courses c
        WHERE c.teacher_id = ?
        ORDER BY c.created_at DESC
    ''', [teacher_id])

    # Total students across all my courses
    total_students = query_db('''
        SELECT COUNT(DISTINCT e.student_id) as cnt
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE c.teacher_id = ?
    ''', [teacher_id], one=True)['cnt']

    # Emotion distribution across my students
    emotion_stats = query_db('''
        SELECT el.emotion, COUNT(*) as count
        FROM emotion_logs el
        JOIN courses c ON el.course_id = c.id
        WHERE c.teacher_id = ?
        GROUP BY el.emotion
        ORDER BY count DESC
    ''', [teacher_id])

    # Students needing attention (high confusion/boredom rate)
    at_risk_students = query_db('''
        SELECT u.id, u.name, u.email,
               COUNT(CASE WHEN el.emotion IN ('Confused', 'Bored', 'Sad') THEN 1 END) as neg_count,
               COUNT(*) as total_count
        FROM emotion_logs el
        JOIN users u ON el.student_id = u.id
        JOIN courses c ON el.course_id = c.id
        WHERE c.teacher_id = ?
        GROUP BY u.id
        HAVING neg_count > 0
        ORDER BY (neg_count * 1.0 / total_count) DESC
        LIMIT 10
    ''', [teacher_id])

    # Recent quiz performance
    recent_attempts = query_db('''
        SELECT qa.score, qa.total_marks, qa.attempted_at,
               u.name as student_name,
               q.title as quiz_title,
               c.title as course_title
        FROM quiz_attempts qa
        JOIN users u ON qa.student_id = u.id
        JOIN quizzes q ON qa.quiz_id = q.id
        JOIN courses c ON q.course_id = c.id
        WHERE c.teacher_id = ?
        ORDER BY qa.attempted_at DESC
        LIMIT 10
    ''', [teacher_id])

    # All enrolled students across teacher's courses (with their course names)
    enrolled_students = query_db('''
        SELECT u.id, u.name, u.email, u.created_at,
               GROUP_CONCAT(c.title, ', ') as course_names,
               COUNT(DISTINCT e.course_id) as course_count,
               (SELECT COUNT(*) FROM emotion_logs el
                JOIN courses c2 ON el.course_id = c2.id
                WHERE el.student_id = u.id AND c2.teacher_id = ?) as emotion_count
        FROM users u
        JOIN enrollments e ON u.id = e.student_id
        JOIN courses c ON e.course_id = c.id
        WHERE c.teacher_id = ? AND u.role = 'student'
        GROUP BY u.id
        ORDER BY u.name
    ''', [teacher_id, teacher_id])

    # All registered students on the platform (to allow teachers to see and enroll newly added students)
    all_students = query_db('''
        SELECT u.id, u.name, u.email, u.created_at, u.is_active,
               (SELECT COUNT(*) FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                WHERE e.student_id = u.id AND c.teacher_id = ?) as my_course_count,
               (SELECT GROUP_CONCAT(c.title, ', ') FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                WHERE e.student_id = u.id AND c.teacher_id = ?) as my_course_names
        FROM users u
        WHERE u.role = 'student'
        ORDER BY u.name ASC
    ''', [teacher_id, teacher_id])

    return render_template('teacher_dashboard.html',
                           courses=courses,
                           total_students=total_students,
                           total_courses=len(courses),
                           total_platform_students=len(all_students),
                           emotion_stats=emotion_stats,
                           at_risk_students=at_risk_students,
                           recent_attempts=recent_attempts,
                           enrolled_students=enrolled_students,
                           all_students=all_students)


@teacher_bp.route('/students/enroll', methods=['POST'])
@teacher_required
def enroll_student():
    """Enroll any student into one of this teacher's courses."""
    student_id = request.form.get('student_id', type=int)
    course_id = request.form.get('course_id', type=int)

    if not student_id or not course_id:
        flash('Please select both a student and a course.', 'warning')
        return redirect(url_for('teacher.dashboard'))

    # Verify course belongs to this teacher
    course = query_db('SELECT id, title FROM courses WHERE id = ? AND teacher_id = ?',
                      [course_id, current_user.id], one=True)
    if not course:
        flash('Course not found or does not belong to you.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    # Verify user is a student
    student = query_db('SELECT id, name FROM users WHERE id = ? AND role = "student"',
                       [student_id], one=True)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    # Check existing enrollment
    existing = query_db('SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?',
                        [student_id, course_id], one=True)
    if existing:
        flash(f'{student["name"]} is already enrolled in "{course["title"]}".', 'info')
    else:
        execute_db('INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)',
                   (student_id, course_id))
        flash(f'Successfully enrolled {student["name"]} into "{course["title"]}".', 'success')

    return redirect(url_for('teacher.dashboard'))


@teacher_bp.route('/courses')
@teacher_required
def my_courses():
    """List all courses by this teacher."""
    courses = query_db('''
        SELECT c.*,
               (SELECT COUNT(DISTINCT e.student_id) FROM enrollments e WHERE e.course_id = c.id) as student_count,
               (SELECT COUNT(*) FROM lessons WHERE course_id = c.id) as lesson_count
        FROM courses c
        WHERE c.teacher_id = ?
        ORDER BY c.created_at DESC
    ''', [current_user.id])

    return render_template('teacher_courses.html', courses=courses)


@teacher_bp.route('/course/new', methods=['GET', 'POST'])
@teacher_required
def create_course():
    """Create a new course."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'General').strip()

        if not title:
            flash('Course title is required.', 'danger')
            return render_template('teacher_course_form.html', course=None)

        course_id = execute_db(
            'INSERT INTO courses (title, description, teacher_id, category, is_published) VALUES (?, ?, ?, ?, 1)',
            (title, description, current_user.id, category)
        )
        flash(f'Course "{title}" created successfully!', 'success')
        return redirect(url_for('teacher.edit_course', course_id=course_id))

    return render_template('teacher_course_form.html', course=None)


@teacher_bp.route('/course/<int:course_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_course(course_id):
    """Edit an existing course."""
    course = query_db('SELECT * FROM courses WHERE id = ? AND teacher_id = ?',
                      [course_id, current_user.id], one=True)
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'General').strip()

        if not title:
            flash('Course title is required.', 'danger')
            return render_template('teacher_course_form.html', course=course)

        execute_db(
            'UPDATE courses SET title = ?, description = ?, category = ? WHERE id = ?',
            (title, description, category, course_id)
        )
        flash('Course updated successfully.', 'success')
        return redirect(url_for('teacher.edit_course', course_id=course_id))

    # Get lessons for this course
    lessons = query_db(
        'SELECT * FROM lessons WHERE course_id = ? ORDER BY order_number',
        [course_id]
    )

    # Get quizzes for this course
    quizzes = query_db(
        'SELECT * FROM quizzes WHERE course_id = ? ORDER BY created_at',
        [course_id]
    )

    return render_template('teacher_course_form.html',
                           course=course, lessons=lessons, quizzes=quizzes)


@teacher_bp.route('/course/<int:course_id>/delete', methods=['POST'])
@teacher_required
def delete_course(course_id):
    """Delete a course."""
    course = query_db('SELECT * FROM courses WHERE id = ? AND teacher_id = ?',
                      [course_id, current_user.id], one=True)
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    execute_db('DELETE FROM courses WHERE id = ?', [course_id])
    flash(f'Course "{course["title"]}" deleted.', 'info')
    return redirect(url_for('teacher.my_courses'))


@teacher_bp.route('/course/<int:course_id>/lesson/new', methods=['GET', 'POST'])
@teacher_required
def add_lesson(course_id):
    """Add a lesson to a course."""
    course = query_db('SELECT * FROM courses WHERE id = ? AND teacher_id = ?',
                      [course_id, current_user.id], one=True)
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        video_url = request.form.get('video_url', '').strip()
        notes = request.form.get('notes', '').strip()

        if not title:
            flash('Lesson title is required.', 'danger')
            return render_template('teacher_lesson_form.html', course=course, lesson=None)

        # Get next order number
        max_order = query_db(
            'SELECT COALESCE(MAX(order_number), 0) as mx FROM lessons WHERE course_id = ?',
            [course_id], one=True
        )['mx']

        execute_db(
            'INSERT INTO lessons (course_id, title, description, video_url, notes, order_number) VALUES (?, ?, ?, ?, ?, ?)',
            (course_id, title, description, video_url, notes, max_order + 1)
        )
        flash(f'Lesson "{title}" added.', 'success')
        return redirect(url_for('teacher.edit_course', course_id=course_id))

    return render_template('teacher_lesson_form.html', course=course, lesson=None)


@teacher_bp.route('/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_lesson(lesson_id):
    """Edit a lesson."""
    lesson = query_db('SELECT * FROM lessons WHERE id = ?', [lesson_id], one=True)
    if not lesson:
        flash('Lesson not found.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    course = query_db('SELECT * FROM courses WHERE id = ? AND teacher_id = ?',
                      [lesson['course_id'], current_user.id], one=True)
    if not course:
        flash('Access denied.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        video_url = request.form.get('video_url', '').strip()
        notes = request.form.get('notes', '').strip()

        if not title:
            flash('Lesson title is required.', 'danger')
            return render_template('teacher_lesson_form.html', course=course, lesson=lesson)

        execute_db(
            'UPDATE lessons SET title = ?, description = ?, video_url = ?, notes = ? WHERE id = ?',
            (title, description, video_url, notes, lesson_id)
        )
        flash('Lesson updated.', 'success')
        return redirect(url_for('teacher.edit_course', course_id=course['id']))

    return render_template('teacher_lesson_form.html', course=course, lesson=lesson)


@teacher_bp.route('/lesson/<int:lesson_id>/delete', methods=['POST'])
@teacher_required
def delete_lesson(lesson_id):
    """Delete a lesson."""
    lesson = query_db('SELECT * FROM lessons WHERE id = ?', [lesson_id], one=True)
    if not lesson:
        flash('Lesson not found.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    course = query_db('SELECT * FROM courses WHERE id = ? AND teacher_id = ?',
                      [lesson['course_id'], current_user.id], one=True)
    if not course:
        flash('Access denied.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    execute_db('DELETE FROM lessons WHERE id = ?', [lesson_id])
    flash('Lesson deleted.', 'info')
    return redirect(url_for('teacher.edit_course', course_id=course['id']))


@teacher_bp.route('/course/<int:course_id>/quiz/new', methods=['GET', 'POST'])
@teacher_required
def create_quiz(course_id):
    """Create a new quiz for a course."""
    course = query_db('SELECT * FROM courses WHERE id = ? AND teacher_id = ?',
                      [course_id, current_user.id], one=True)
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    lessons = query_db('SELECT * FROM lessons WHERE course_id = ? ORDER BY order_number', [course_id])

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        lesson_id = request.form.get('lesson_id')
        lesson_id = int(lesson_id) if lesson_id else None

        if not title:
            flash('Quiz title is required.', 'danger')
            return render_template('teacher_quiz_form.html', course=course,
                                   lessons=lessons, quiz=None, questions=[])

        quiz_id = execute_db(
            'INSERT INTO quizzes (course_id, lesson_id, title, description) VALUES (?, ?, ?, ?)',
            (course_id, lesson_id, title, description)
        )

        # Parse questions from form
        q_index = 1
        while True:
            q_text = request.form.get(f'question_{q_index}', '').strip()
            if not q_text:
                break

            q_id = execute_db(
                'INSERT INTO questions (quiz_id, question_text, order_number) VALUES (?, ?, ?)',
                (quiz_id, q_text, q_index)
            )

            # Parse options
            correct_opt = request.form.get(f'correct_{q_index}')
            for opt_idx in range(1, 5):
                opt_text = request.form.get(f'option_{q_index}_{opt_idx}', '').strip()
                if opt_text:
                    is_correct = 1 if correct_opt == str(opt_idx) else 0
                    execute_db(
                        'INSERT INTO options (question_id, option_text, is_correct) VALUES (?, ?, ?)',
                        (q_id, opt_text, is_correct)
                    )

            q_index += 1

        flash(f'Quiz "{title}" created with {q_index - 1} questions.', 'success')
        return redirect(url_for('teacher.edit_course', course_id=course_id))

    return render_template('teacher_quiz_form.html', course=course,
                           lessons=lessons, quiz=None, questions=[])


@teacher_bp.route('/quiz/<int:quiz_id>/delete', methods=['POST'])
@teacher_required
def delete_quiz(quiz_id):
    """Delete a quiz."""
    quiz = query_db('SELECT * FROM quizzes WHERE id = ?', [quiz_id], one=True)
    if not quiz:
        flash('Quiz not found.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    course = query_db('SELECT * FROM courses WHERE id = ? AND teacher_id = ?',
                      [quiz['course_id'], current_user.id], one=True)
    if not course:
        flash('Access denied.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    execute_db('DELETE FROM quizzes WHERE id = ?', [quiz_id])
    flash('Quiz deleted.', 'info')
    return redirect(url_for('teacher.edit_course', course_id=course['id']))


@teacher_bp.route('/student/<int:student_id>/analytics')
@teacher_required
def student_analytics(student_id):
    """View detailed analytics for a specific student."""
    student = query_db('SELECT * FROM users WHERE id = ? AND role = ?',
                       [student_id, 'student'], one=True)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    # Verify teacher has courses this student is enrolled in
    shared_courses = query_db('''
        SELECT c.* FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        WHERE c.teacher_id = ? AND e.student_id = ?
    ''', [current_user.id, student_id])

    if not shared_courses:
        flash('This student is not enrolled in any of your courses.', 'warning')
        return redirect(url_for('teacher.dashboard'))

    # Emotion data
    emotion_stats = query_db('''
        SELECT el.emotion, COUNT(*) as count, AVG(el.confidence) as avg_conf
        FROM emotion_logs el
        JOIN courses c ON el.course_id = c.id
        WHERE el.student_id = ? AND c.teacher_id = ?
        GROUP BY el.emotion
        ORDER BY count DESC
    ''', [student_id, current_user.id])

    # Quiz performance
    quiz_history = query_db('''
        SELECT qa.*, q.title as quiz_title, c.title as course_title
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        JOIN courses c ON q.course_id = c.id
        WHERE qa.student_id = ? AND c.teacher_id = ?
        ORDER BY qa.attempted_at DESC
    ''', [student_id, current_user.id])

    # Emotion timeline
    emotion_timeline = query_db('''
        SELECT el.emotion, el.confidence, el.timestamp, c.title as course_title
        FROM emotion_logs el
        JOIN courses c ON el.course_id = c.id
        WHERE el.student_id = ? AND c.teacher_id = ?
        ORDER BY el.timestamp DESC
        LIMIT 50
    ''', [student_id, current_user.id])

    return render_template('student_performance.html',
                           student=student,
                           shared_courses=shared_courses,
                           emotion_stats=emotion_stats,
                           quiz_history=quiz_history,
                           emotion_timeline=emotion_timeline)
