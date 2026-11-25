"""
Authentication routes — Register, Email OTP Verification, Login, Logout,
Forgot Password, and Account Status Management.
Includes role-based and approval-based access control decorators.
"""

from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database.database import query_db, execute_db
from utils.security import validate_password_strength, check_account_access
from services.otp_service import create_and_send_otp, verify_otp_code

auth_bp = Blueprint('auth', __name__)


# ---------------------------------------------------------------------------
# Role-based & Status-based access decorators
# ---------------------------------------------------------------------------

def role_required(*roles):
    """
    Decorator that restricts access to users with specified roles.
    Enforces that user account status MUST be 'approved'.
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            # Check approval status
            if getattr(current_user, 'status', 'approved') != 'approved':
                flash('Your account has not been approved for access.', 'warning')
                return redirect(url_for('auth.account_status'))

            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def student_required(f):
    """Allow only approved students."""
    return role_required('student')(f)


def teacher_required(f):
    """Allow only approved teachers."""
    return role_required('teacher')(f)


def admin_required(f):
    """Allow only approved admins."""
    return role_required('admin')(f)


# ---------------------------------------------------------------------------
# Registration & Verification Routes
# ---------------------------------------------------------------------------

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration — students and teachers can self-register (Admin role prohibited)."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        role = request.form.get('role', 'student')

        # --- Validation ---
        errors = []
        if not name or len(name) < 2:
            errors.append('Name must be at least 2 characters.')
        if not email or '@' not in email:
            errors.append('A valid email address is required.')

        # Strict security rule: Never allow Admin role selection in registration
        if role not in ('student', 'teacher'):
            errors.append('Invalid role selected. Only Students and Teachers can register.')

        # Password strength validation
        pwd_valid, pwd_err = validate_password_strength(password)
        if not pwd_valid:
            errors.append(pwd_err)

        if password != confirm:
            errors.append('Passwords do not match.')

        # Check duplicate email
        if not errors:
            existing = query_db('SELECT id, status FROM users WHERE email = ?', [email], one=True)
            if existing:
                errors.append('An account with this email already exists.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('register.html', name=name, email=email, role=role)

        # Create user in 'unverified' status with active flag (is_active=1)
        password_hash = generate_password_hash(password)
        user_id = execute_db(
            'INSERT INTO users (name, email, password_hash, role, status, is_active) VALUES (?, ?, ?, ?, ?, ?)',
            (name, email, password_hash, role, 'unverified', 1)
        )

        # Generate and dispatch 6-digit OTP code
        success, msg, _ = create_and_send_otp(email, user_id=user_id, otp_type='registration')
        session['verify_email'] = email

        if not success:
            flash(f'Account created, but email delivery failed: {msg}. Please check your email settings or click "Resend Code".', 'warning')
            return redirect(url_for('auth.verify_otp'))

        flash('Registration initiated! Please enter the 6-digit verification code sent to your email.', 'info')
        return redirect(url_for('auth.verify_otp'))

    return render_template('register.html')


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Verify email address using a 6-digit OTP code."""
    email = session.get('verify_email') or request.args.get('email', '').strip().lower()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower() or email
        code = request.form.get('otp', '').strip()

        if not email:
            flash('Session expired or email missing. Please register again.', 'danger')
            return redirect(url_for('auth.register'))

        if not code or len(code) != 6:
            flash('Please enter a valid 6-digit verification code.', 'danger')
            return render_template('verify_otp.html', email=email)

        success, msg = verify_otp_code(email, code, otp_type='registration')
        if not success:
            flash(msg, 'danger')
            return render_template('verify_otp.html', email=email)

        # Update account status to 'pending_approval'
        execute_db("UPDATE users SET status = 'pending_approval' WHERE email = ?", [email])
        session['status_email'] = email
        session.pop('verify_email', None)

        flash('Email verified successfully! Your account is now submitted for administrator approval.', 'success')
        return redirect(url_for('auth.account_status'))

    if not email:
        flash('Please provide an email to verify.', 'warning')
        return redirect(url_for('auth.register'))

    return render_template('verify_otp.html', email=email)


@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Resend a new 6-digit OTP with cooldown enforcement."""
    email = request.form.get('email', '').strip().lower() or session.get('verify_email') or session.get('reset_email')
    otp_type = request.form.get('otp_type', 'registration')

    if not email:
        return jsonify({'success': False, 'message': 'No email address provided.'}), 400

    success, msg, _ = create_and_send_otp(email, otp_type=otp_type)
    if not success:
        return jsonify({'success': False, 'message': msg}), 429

    return jsonify({'success': True, 'message': msg})


@auth_bp.route('/account-status')
def account_status():
    """Display the account's approval or review state."""
    email = session.get('status_email')
    if current_user.is_authenticated:
        email = current_user.email

    user_row = None
    if email:
        user_row = query_db('SELECT name, email, role, status, rejection_reason FROM users WHERE email = ?', [email], one=True)

    status = user_row['status'] if user_row else 'pending_approval'
    rejection_reason = user_row['rejection_reason'] if user_row else None
    user_name = user_row['name'] if user_row else 'Learner'

    return render_template(
        'account_status.html',
        status=status,
        user_name=user_name,
        email=email,
        rejection_reason=rejection_reason
    )


# ---------------------------------------------------------------------------
# Login & Logout
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login with comprehensive account status validation."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        user_row = query_db('SELECT * FROM users WHERE email = ?', [email], one=True)

        if user_row is None or not check_password_hash(user_row['password_hash'], password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html', email=email)

        # Validate account status (unverified, pending, rejected, suspended, approved)
        allowed, status, status_msg = check_account_access(user_row)

        if status == 'unverified':
            session['verify_email'] = email
            # Resend OTP if needed
            otp_sent, otp_msg, _ = create_and_send_otp(email, user_id=user_row['id'], otp_type='registration')
            if not otp_sent:
                flash(f'Your email is not verified yet. Delivery note: {otp_msg}', 'warning')
            else:
                flash('Your email is not verified yet. We have sent a verification code to your email.', 'warning')
            return redirect(url_for('auth.verify_otp'))

        if status == 'pending_approval':
            session['status_email'] = email
            flash('Your account registration is awaiting administrator approval.', 'info')
            return redirect(url_for('auth.account_status'))

        if status == 'rejected':
            session['status_email'] = email
            flash(status_msg, 'danger')
            return redirect(url_for('auth.account_status'))

        if status == 'suspended' or status == 'deactivated':
            flash(status_msg, 'danger')
            return render_template('login.html', email=email)

        if not allowed:
            flash(status_msg, 'danger')
            return render_template('login.html', email=email)

        # Update last login timestamp
        execute_db('UPDATE users SET last_login = ? WHERE id = ?', [datetime.utcnow(), user_row['id']])

        # Build User object for session management
        from flask import current_app
        user = current_app.User(user_row)
        login_user(user, remember=bool(remember))

        flash(f'Welcome back, {user.name}!', 'success')

        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('index'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ---------------------------------------------------------------------------
# Forgot Password & Reset via OTP
# ---------------------------------------------------------------------------

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request a password reset OTP code via email."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Please enter your account email address.', 'danger')
            return render_template('forgot_password.html')

        user = query_db('SELECT id, email FROM users WHERE email = ?', [email], one=True)
        if user:
            otp_sent, otp_msg, _ = create_and_send_otp(email, user_id=user['id'], otp_type='password_reset')
            if not otp_sent:
                flash(f'Failed to send password reset code: {otp_msg}', 'danger')
                return render_template('forgot_password.html')

        session['reset_email'] = email
        flash('If an account exists with this email, a password reset code has been sent.', 'info')
        return redirect(url_for('auth.reset_password'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Verify password reset OTP and set new strong password."""
    email = session.get('reset_email') or request.args.get('email', '').strip().lower()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower() or email
        code = request.form.get('otp', '').strip()
        new_password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        errors = []
        if not email:
            errors.append('Email is required.')
        if not code or len(code) != 6:
            errors.append('Please provide the 6-digit reset code.')

        valid_pwd, pwd_err = validate_password_strength(new_password)
        if not valid_pwd:
            errors.append(pwd_err)
        if new_password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('reset_password.html', email=email)

        # Validate OTP
        success, msg = verify_otp_code(email, code, otp_type='password_reset')
        if not success:
            flash(msg, 'danger')
            return render_template('reset_password.html', email=email)

        # Update password hash
        new_hash = generate_password_hash(new_password)
        execute_db('UPDATE users SET password_hash = ? WHERE email = ?', [new_hash, email])
        session.pop('reset_email', None)

        flash('Your password has been successfully reset! Please log in with your new credentials.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', email=email)
