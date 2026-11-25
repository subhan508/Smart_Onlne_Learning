"""
Student routes — Dashboard, enrolled courses, performance, analytics.
"""

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from database.database import query_db

student_bp = Blueprint('student', __name__)


def student_required(f):
    """Decorator: only allow students."""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'student':
            flash('Access denied. Students only.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


@student_bp.route('/dashboard')
@student_required
def dashboard():
    """Student dashboard — overview of courses, progress, emotions, quizzes."""
    student_id = current_user.id

    # Enrolled courses with progress
    enrolled_courses = query_db('''
        SELECT c.*, e.enrolled_at,
               u.name as teacher_name,
               (SELECT COUNT(*) FROM lessons WHERE course_id = c.id) as total_lessons,
               (SELECT COUNT(*) FROM learning_progress
                WHERE student_id = ? AND course_id = c.id AND is_completed = 1) as completed_lessons
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        JOIN users u ON c.teacher_id = u.id
        WHERE e.student_id = ?
        ORDER BY e.enrolled_at DESC
    ''', [student_id, student_id])

    # Recent quiz scores
    recent_quizzes = query_db('''
        SELECT qa.*, q.title as quiz_title, c.title as course_title
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        JOIN courses c ON q.course_id = c.id
        WHERE qa.student_id = ?
        ORDER BY qa.attempted_at DESC
        LIMIT 5
    ''', [student_id])

    # Emotion statistics
    emotion_stats = query_db('''
        SELECT emotion, COUNT(*) as count
        FROM emotion_logs
        WHERE student_id = ?
        GROUP BY emotion
        ORDER BY count DESC
    ''', [student_id])

    # Recent emotions
    recent_emotions = query_db('''
        SELECT emotion, confidence, timestamp
        FROM emotion_logs
        WHERE student_id = ?
        ORDER BY timestamp DESC
        LIMIT 10
    ''', [student_id])

    # Recent recommendations
    recent_recs = query_db('''
        SELECT r.*, c.title as course_title
        FROM recommendations r
        LEFT JOIN courses c ON r.course_id = c.id
        WHERE r.student_id = ? AND r.is_dismissed = 0
        ORDER BY r.created_at DESC
        LIMIT 5
    ''', [student_id])

    # Overall stats
    total_enrolled = len(enrolled_courses)
    total_quizzes = query_db(
        'SELECT COUNT(*) as cnt FROM quiz_attempts WHERE student_id = ?',
        [student_id], one=True
    )['cnt']
    avg_score = query_db('''
        SELECT COALESCE(AVG(CASE WHEN total_marks > 0 THEN (score * 100.0 / total_marks) ELSE 0 END), 0) as avg
        FROM quiz_attempts WHERE student_id = ?
    ''', [student_id], one=True)['avg']

    return render_template('student_dashboard.html',
                           enrolled_courses=enrolled_courses,
                           recent_quizzes=recent_quizzes,
                           emotion_stats=emotion_stats,
                           recent_emotions=recent_emotions,
                           recent_recs=recent_recs,
                           total_enrolled=total_enrolled,
                           total_quizzes=total_quizzes,
                           avg_score=round(avg_score, 1))


@student_bp.route('/analytics')
@student_required
def analytics():
    """Detailed emotion and learning analytics for the student."""
    student_id = current_user.id

    # Emotion distribution
    emotion_dist = query_db('''
        SELECT emotion, COUNT(*) as count,
               AVG(confidence) as avg_confidence
        FROM emotion_logs
        WHERE student_id = ?
        GROUP BY emotion
        ORDER BY count DESC
    ''', [student_id])

    # Emotion timeline (last 50 entries)
    emotion_timeline = query_db('''
        SELECT emotion, confidence, timestamp,
               c.title as course_title
        FROM emotion_logs el
        LEFT JOIN courses c ON el.course_id = c.id
        WHERE el.student_id = ?
        ORDER BY el.timestamp DESC
        LIMIT 50
    ''', [student_id])

    # Quiz performance over time
    quiz_history = query_db('''
        SELECT qa.score, qa.total_marks, qa.attempted_at,
               q.title as quiz_title, c.title as course_title
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        JOIN courses c ON q.course_id = c.id
        WHERE qa.student_id = ?
        ORDER BY qa.attempted_at DESC
        LIMIT 20
    ''', [student_id])

    return render_template('student_analytics.html',
                           emotion_dist=emotion_dist,
                           emotion_timeline=emotion_timeline,
                           quiz_history=quiz_history)
