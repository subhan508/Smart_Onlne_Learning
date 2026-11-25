"""
Admin routes — User management, system statistics, course oversight.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database.database import query_db, execute_db

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator: only allow admins."""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Access denied. Administrators only.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard — system-wide statistics."""
    # User counts by role
    user_stats = query_db('''
        SELECT role, COUNT(*) as count FROM users GROUP BY role
    ''')
    user_counts = {row['role']: row['count'] for row in user_stats}

    total_users = sum(user_counts.values())
    total_students = user_counts.get('student', 0)
    total_teachers = user_counts.get('teacher', 0)
    total_admins = user_counts.get('admin', 0)

    # Course stats
    total_courses = query_db('SELECT COUNT(*) as cnt FROM courses', one=True)['cnt']
    total_lessons = query_db('SELECT COUNT(*) as cnt FROM lessons', one=True)['cnt']
    total_quizzes = query_db('SELECT COUNT(*) as cnt FROM quizzes', one=True)['cnt']
    total_enrollments = query_db('SELECT COUNT(*) as cnt FROM enrollments', one=True)['cnt']

    # Emotion stats
    total_emotion_logs = query_db('SELECT COUNT(*) as cnt FROM emotion_logs', one=True)['cnt']
    emotion_dist = query_db('''
        SELECT emotion, COUNT(*) as count FROM emotion_logs GROUP BY emotion ORDER BY count DESC
    ''')

    # Recent users
    recent_users = query_db('''
        SELECT * FROM users ORDER BY created_at DESC LIMIT 5
    ''')

    # Recent quiz attempts
    recent_attempts = query_db('''
        SELECT qa.*, u.name as student_name, q.title as quiz_title
        FROM quiz_attempts qa
        JOIN users u ON qa.student_id = u.id
        JOIN quizzes q ON qa.quiz_id = q.id
        ORDER BY qa.attempted_at DESC
        LIMIT 5
    ''')

    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           total_students=total_students,
                           total_teachers=total_teachers,
                           total_admins=total_admins,
                           total_courses=total_courses,
                           total_lessons=total_lessons,
                           total_quizzes=total_quizzes,
                           total_enrollments=total_enrollments,
                           total_emotion_logs=total_emotion_logs,
                           emotion_dist=emotion_dist,
                           recent_users=recent_users,
                           recent_attempts=recent_attempts)


@admin_bp.route('/users')
@admin_required
def manage_users():
    """List and manage all users."""
    role_filter = request.args.get('role', '')
    search = request.args.get('search', '').strip()

    query = 'SELECT * FROM users WHERE 1=1'
    params = []

    if role_filter:
        query += ' AND role = ?'
        params.append(role_filter)

    if search:
        query += ' AND (name LIKE ? OR email LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    query += ' ORDER BY created_at DESC'
    users = query_db(query, params)

    return render_template('admin_users.html', users=users,
                           role_filter=role_filter, search=search)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    """Activate or deactivate a user."""
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.manage_users'))

    if user['id'] == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('admin.manage_users'))

    new_status = 0 if user['is_active'] else 1
    execute_db('UPDATE users SET is_active = ? WHERE id = ?', [new_status, user_id])

    action = 'activated' if new_status else 'deactivated'
    flash(f'User "{user["name"]}" has been {action}.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user."""
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.manage_users'))

    if user['id'] == current_user.id:
        flash('You cannot delete your own account.', 'warning')
        return redirect(url_for('admin.manage_users'))

    execute_db('DELETE FROM users WHERE id = ?', [user_id])
    flash(f'User "{user["name"]}" has been deleted.', 'info')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/courses')
@admin_required
def manage_courses():
    """List and manage all courses."""
    courses = query_db('''
        SELECT c.*, u.name as teacher_name,
               (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id) as student_count,
               (SELECT COUNT(*) FROM lessons WHERE course_id = c.id) as lesson_count
        FROM courses c
        JOIN users u ON c.teacher_id = u.id
        ORDER BY c.created_at DESC
    ''')

    return render_template('admin_courses.html', courses=courses)


@admin_bp.route('/courses/<int:course_id>/toggle', methods=['POST'])
@admin_required
def toggle_course(course_id):
    """Publish or unpublish a course."""
    course = query_db('SELECT * FROM courses WHERE id = ?', [course_id], one=True)
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('admin.manage_courses'))

    new_status = 0 if course['is_published'] else 1
    execute_db('UPDATE courses SET is_published = ? WHERE id = ?', [new_status, course_id])

    action = 'published' if new_status else 'unpublished'
    flash(f'Course "{course["title"]}" has been {action}.', 'success')
    return redirect(url_for('admin.manage_courses'))


@admin_bp.route('/courses/<int:course_id>/delete', methods=['POST'])
@admin_required
def delete_course(course_id):
    """Delete a course."""
    course = query_db('SELECT * FROM courses WHERE id = ?', [course_id], one=True)
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('admin.manage_courses'))

    execute_db('DELETE FROM courses WHERE id = ?', [course_id])
    flash(f'Course "{course["title"]}" has been deleted.', 'info')
    return redirect(url_for('admin.manage_courses'))
