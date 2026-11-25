"""
Comprehensive unit and integration tests for Phase 1 Authentication & Verification:
- Registration validation & Admin role rejection
- Password strength validation
- OTP generation, dispatch, hashing, attempts limit, and expiration
- Transition from unverified -> pending_approval
- Gating for unverified, pending, rejected, and suspended accounts
- Forgot password & reset via email OTP
"""

import os
import pytest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app import create_app
from database.database import init_db, query_db, execute_db
from utils.security import validate_password_strength
from services.otp_service import create_and_send_otp, verify_otp_code


@pytest.fixture
def app():
    test_db_path = os.path.join(os.path.dirname(__file__), 'test_auth_phase1.db')
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    app = create_app()
    app.config['TESTING'] = True
    app.config['DATABASE'] = test_db_path
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key-123'
    app.config['OTP_COOLDOWN_SECONDS'] = 60

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
    return app.test_client()


class TestPasswordStrength:
    """Test password strength validation logic."""

    def test_short_password(self):
        valid, msg = validate_password_strength('Ab1!')
        assert not valid
        assert 'at least 8 characters' in msg

    def test_missing_uppercase(self):
        valid, msg = validate_password_strength('password123!')
        assert not valid
        assert 'uppercase' in msg

    def test_missing_lowercase(self):
        valid, msg = validate_password_strength('PASSWORD123!')
        assert not valid
        assert 'lowercase' in msg

    def test_missing_digit(self):
        valid, msg = validate_password_strength('Password!@#')
        assert not valid
        assert 'digit' in msg

    def test_missing_special_char(self):
        valid, msg = validate_password_strength('Password123')
        assert not valid
        assert 'special character' in msg

    def test_valid_strong_password(self):
        valid, msg = validate_password_strength('SecureP@ssw0rd!')
        assert valid
        assert msg is None


class TestRegistrationPhase1:
    """Test registration, admin prohibition, and initial unverified status."""

    def test_registration_prohibits_admin_role(self, app, client):
        response = client.post('/register', data={
            'name': 'Hacker Admin',
            'email': 'hacker@admin.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'admin'
        }, follow_redirects=True)
        assert b'Only Students and Teachers can register' in response.data or b'Invalid role' in response.data
        with app.app_context():
            user = query_db('SELECT id FROM users WHERE email = ?', ['hacker@admin.com'], one=True)
            assert user is None

    def test_student_registration_creates_unverified_and_generates_otp(self, app, client):
        response = client.post('/register', data={
            'name': 'Alice Student',
            'email': 'alice@student.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'student'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Verify Your Email' in response.data

        with app.app_context():
            user = query_db('SELECT * FROM users WHERE email = ?', ['alice@student.com'], one=True)
            assert user is not None
            assert user['status'] == 'unverified'

            otp_row = query_db('SELECT * FROM email_otps WHERE email = ?', ['alice@student.com'], one=True)
            assert otp_row is not None
            assert otp_row['is_used'] == 0


class TestOTPVerification:
    """Test OTP verification, attempts limit, and expiration."""

    def test_verify_valid_otp(self, app, client):
        with app.app_context():
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Bob', 'bob@test.com', 'hash', 'student', 'unverified')")
            _, _, code = create_and_send_otp('bob@test.com', otp_type='registration')

        with client.session_transaction() as sess:
            sess['verify_email'] = 'bob@test.com'

        response = client.post('/verify-otp', data={'otp': code, 'email': 'bob@test.com'}, follow_redirects=True)
        assert response.status_code == 200
        assert b'Email verified successfully' in response.data
        assert b'Pending Administrator Approval' in response.data

        with app.app_context():
            user = query_db('SELECT status FROM users WHERE email = ?', ['bob@test.com'], one=True)
            assert user['status'] == 'pending_approval'

    def test_verify_wrong_otp_decrements_attempts(self, app, client):
        with app.app_context():
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Charlie', 'charlie@test.com', 'hash', 'student', 'unverified')")
            create_and_send_otp('charlie@test.com', otp_type='registration')

        with client.session_transaction() as sess:
            sess['verify_email'] = 'charlie@test.com'

        response = client.post('/verify-otp', data={'otp': '000000', 'email': 'charlie@test.com'}, follow_redirects=True)
        assert b'Incorrect verification code' in response.data

        with app.app_context():
            otp_row = query_db('SELECT attempts FROM email_otps WHERE email = ?', ['charlie@test.com'], one=True)
            assert otp_row['attempts'] == 1

    def test_verify_expired_otp(self, app, client):
        with app.app_context():
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Dave', 'dave@test.com', 'hash', 'student', 'unverified')")
            create_and_send_otp('dave@test.com', otp_type='registration')
            past_time = datetime.utcnow() - timedelta(minutes=20)
            execute_db('UPDATE email_otps SET expires_at = ? WHERE email = ?', [past_time, 'dave@test.com'])

        with client.session_transaction() as sess:
            sess['verify_email'] = 'dave@test.com'

        response = client.post('/verify-otp', data={'otp': '123456', 'email': 'dave@test.com'}, follow_redirects=True)
        assert b'expired' in response.data.lower()

    def test_resend_otp_cooldown(self, app, client):
        with app.app_context():
            create_and_send_otp('eve@test.com', otp_type='registration')

        response = client.post('/resend-otp', data={'email': 'eve@test.com', 'otp_type': 'registration'})
        assert response.status_code == 429
        data = response.get_json()
        assert not data['success']
        assert 'wait' in data['message'].lower()


class TestAccountAccessGating:
    """Test that only approved accounts can log in and access protected views."""

    def test_unverified_account_redirected_to_verify_otp(self, app, client):
        with app.app_context():
            pwd_hash = generate_password_hash('StrongP@ss123!')
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Frank', 'frank@test.com', ?, 'student', 'unverified')", [pwd_hash])

        response = client.post('/login', data={'email': 'frank@test.com', 'password': 'StrongP@ss123!'}, follow_redirects=True)
        assert b'Verify Your Email' in response.data

    def test_pending_approval_account_shown_status(self, app, client):
        with app.app_context():
            pwd_hash = generate_password_hash('StrongP@ss123!')
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Grace', 'grace@test.com', ?, 'student', 'pending_approval')", [pwd_hash])

        response = client.post('/login', data={'email': 'grace@test.com', 'password': 'StrongP@ss123!'}, follow_redirects=True)
        assert b'Registration Under Review' in response.data
        assert b'Pending Administrator Approval' in response.data

    def test_rejected_account_shown_reason(self, app, client):
        with app.app_context():
            pwd_hash = generate_password_hash('StrongP@ss123!')
            execute_db("INSERT INTO users (name, email, password_hash, role, status, rejection_reason) VALUES ('Harry', 'harry@test.com', ?, 'student', 'rejected', 'Invalid credentials provided')", [pwd_hash])

        response = client.post('/login', data={'email': 'harry@test.com', 'password': 'StrongP@ss123!'}, follow_redirects=True)
        assert b'Registration Rejected' in response.data
        assert b'Invalid credentials provided' in response.data

    def test_approved_account_logs_in_successfully(self, app, client):
        with app.app_context():
            pwd_hash = generate_password_hash('StrongP@ss123!')
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Ivy', 'ivy@test.com', ?, 'student', 'approved')", [pwd_hash])

        response = client.post('/login', data={'email': 'ivy@test.com', 'password': 'StrongP@ss123!'}, follow_redirects=True)
        assert response.status_code == 200
        assert b'Welcome back, Ivy!' in response.data


class TestForgotPasswordFlow:
    """Test forgot password and reset with OTP."""

    def test_forgot_password_generates_otp(self, app, client):
        with app.app_context():
            pwd_hash = generate_password_hash('OldP@ssw0rd1!')
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Jack', 'jack@test.com', ?, 'student', 'approved')", [pwd_hash])

        response = client.post('/forgot-password', data={'email': 'jack@test.com'}, follow_redirects=True)
        assert b'New Password' in response.data

        with app.app_context():
            otp_row = query_db("SELECT * FROM email_otps WHERE email = 'jack@test.com' AND otp_type = 'password_reset'", one=True)
            assert otp_row is not None

    def test_reset_password_updates_password(self, app, client):
        with app.app_context():
            pwd_hash = generate_password_hash('OldP@ssw0rd1!')
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Kelly', 'kelly@test.com', ?, 'student', 'approved')", [pwd_hash])
            _, _, code = create_and_send_otp('kelly@test.com', otp_type='password_reset')

        with client.session_transaction() as sess:
            sess['reset_email'] = 'kelly@test.com'

        response = client.post('/reset-password', data={
            'email': 'kelly@test.com',
            'otp': code,
            'password': 'BrandNewP@ss123!',
            'confirm_password': 'BrandNewP@ss123!'
        }, follow_redirects=True)

        assert b'Your password has been successfully reset' in response.data

        # Verify login works with new password
        login_resp = client.post('/login', data={'email': 'kelly@test.com', 'password': 'BrandNewP@ss123!'}, follow_redirects=True)
        assert b'Welcome back, Kelly!' in login_resp.data


class TestResendEmailService:
    """Verify Resend HTTP email dispatch, header formation, and error handling."""

    def test_resend_api_dispatch_success(self, app):
        from unittest.mock import patch, MagicMock
        from services.email_service import _send_via_resend

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"id": "msg_12345"}'
        mock_resp.__enter__.return_value = mock_resp

        with app.app_context(), patch('urllib.request.urlopen', return_value=mock_resp) as mock_urlopen:
            success, msg = _send_via_resend(
                api_key="re_test_key",
                from_email="SmartLearn <onboarding@resend.dev>",
                to_email="student@example.com",
                subject="Test Subject",
                body_html="<p>Test</p>",
                body_text="Test"
            )

            assert success is True
            assert "msg_12345" in msg
            assert mock_urlopen.called
            call_req = mock_urlopen.call_args[0][0]
            assert call_req.get_full_url() == "https://api.resend.com/emails"
            assert call_req.headers['Authorization'] == "Bearer re_test_key"

    def test_resend_api_dispatch_http_error(self, app):
        from unittest.mock import patch
        from services.email_service import _send_via_resend
        import urllib.error
        import io

        err_stream = io.BytesIO(b'{"message": "API key invalid", "name": "validation_error"}')
        http_err = urllib.error.HTTPError("https://api.resend.com/emails", 401, "Unauthorized", {}, err_stream)

        with app.app_context(), patch('urllib.request.urlopen', side_effect=http_err):
            success, msg = _send_via_resend(
                api_key="re_invalid_key",
                from_email="onboarding@resend.dev",
                to_email="student@example.com",
                subject="Test",
                body_html="<p>Hi</p>"
            )

            assert success is False
            assert "API key invalid" in msg
            assert "401" in msg

    def test_resend_api_dispatch_403_testing_mode_error(self, app):
        from unittest.mock import patch
        from services.email_service import _send_via_resend
        import urllib.error
        import io

        err_stream = io.BytesIO(b'{"message": "You can only send testing emails to your own email address. To send to other addresses, please verify your domain.", "name": "validation_error"}')
        http_err = urllib.error.HTTPError("https://api.resend.com/emails", 403, "Forbidden", {}, err_stream)

        with app.app_context(), patch('urllib.request.urlopen', side_effect=http_err):
            success, msg = _send_via_resend(
                api_key="re_sandbox_key",
                from_email="onboarding@resend.dev",
                to_email="external_student@example.com",
                subject="Test",
                body_html="<p>Hi</p>"
            )

            assert success is False
            assert "verify your domain" in msg
            assert "403" in msg

    def test_send_email_uses_resend_when_configured(self, app):
        from unittest.mock import patch
        from services.email_service import send_email

        with app.app_context():
            app.config['TESTING'] = False
            app.config['RESEND_API_KEY'] = 're_live_key'
            app.config['EMAIL_FROM'] = 'SmartLearn <noreply@domain.com>'

            with patch('services.email_service._send_via_resend', return_value=(True, "Sent via Resend")) as mock_send:
                success, msg = send_email("user@test.com", "Subject", "<p>Hello</p>")
                assert success is True
                mock_send.assert_called_once_with(
                    api_key="re_live_key",
                    from_email="SmartLearn <noreply@domain.com>",
                    to_email="user@test.com",
                    subject="Subject",
                    body_html="<p>Hello</p>",
                    body_text=None
                )

    def test_send_email_fails_fast_in_production_when_resend_key_missing(self, app, monkeypatch):
        from services.email_service import send_email

        with app.app_context():
            app.config['TESTING'] = False
            app.config['RESEND_API_KEY'] = ''
            monkeypatch.setenv('RENDER', 'true')

            success, msg = send_email("user@test.com", "Subject", "<p>Hello</p>")
            assert success is False
            assert "RESEND_API_KEY is not configured" in msg
            assert "Render Dashboard" in msg


class TestSecureDemoMode:
    """Verify temporary secure demo mode OTP bypass and strict access gating."""

    def test_demo_mode_disabled_by_default(self, app, client):
        """When DEMO_MODE is False (default), demo account goes through normal OTP flow."""
        app.config['DEMO_MODE'] = False
        app.config['DEMO_ACCOUNT_EMAIL'] = 'demo@smartlearn.com'

        response = client.post('/register', data={
            'name': 'Demo User',
            'email': 'demo@smartlearn.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'student'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Verify Your Email' in response.data
        with app.app_context():
            user = query_db("SELECT status FROM users WHERE email = 'demo@smartlearn.com'", one=True)
            assert user['status'] == 'unverified'

    def test_demo_mode_active_bypasses_otp_for_designated_account_only(self, app, client):
        """When DEMO_MODE is True, designated demo account registers and logs in immediately."""
        app.config['DEMO_MODE'] = True
        app.config['DEMO_ACCOUNT_EMAIL'] = 'demo@smartlearn.com'

        # 1. Designated demo account registers -> auto-approved and logged in
        response = client.post('/register', data={
            'name': 'Demo User',
            'email': 'demo@smartlearn.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'student'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Demo mode active' in response.data
        with app.app_context():
            user = query_db("SELECT status FROM users WHERE email = 'demo@smartlearn.com'", one=True)
            assert user['status'] == 'approved'

        # Log out before testing arbitrary account registration
        client.get('/logout')

        # 2. Arbitrary account STILL requires normal OTP verification!
        other_response = client.post('/register', data={
            'name': 'Other User',
            'email': 'other@example.com',
            'password': 'StrongP@ss123!',
            'confirm_password': 'StrongP@ss123!',
            'role': 'student'
        }, follow_redirects=True)

        assert other_response.status_code == 200
        assert b'Verify Your Email' in other_response.data
        with app.app_context():
            other = query_db("SELECT status FROM users WHERE email = 'other@example.com'", one=True)
            assert other['status'] == 'unverified'

    def test_demo_mode_login_requires_valid_password(self, app, client):
        """Demo mode still enforces strict password authentication."""
        app.config['DEMO_MODE'] = True
        app.config['DEMO_ACCOUNT_EMAIL'] = 'demo@smartlearn.com'

        with app.app_context():
            pwd_hash = generate_password_hash('CorrectP@ss123!')
            execute_db("INSERT INTO users (name, email, password_hash, role, status) VALUES ('Demo', 'demo@smartlearn.com', ?, 'student', 'unverified')", [pwd_hash])

        # Wrong password fails
        bad_login = client.post('/login', data={'email': 'demo@smartlearn.com', 'password': 'WrongPassword!'}, follow_redirects=True)
        assert b'Invalid email or password' in bad_login.data

        # Correct password succeeds and grants access
        good_login = client.post('/login', data={'email': 'demo@smartlearn.com', 'password': 'CorrectP@ss123!'}, follow_redirects=True)
        assert b'Demo mode active: Logged in' in good_login.data


