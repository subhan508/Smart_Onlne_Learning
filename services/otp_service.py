"""
OTP (One-Time Password) Service for SmartLearn.
Handles generation, hashing, rate-limiting, cooldowns, and validation for
6-digit authentication and verification codes.
"""

import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from database.database import query_db, execute_db
from services.email_service import send_otp_email


def generate_otp_code():
    """Generate a secure 6-digit numeric OTP."""
    # Guaranteed 6 digits between 100000 and 999999
    return f"{secrets.randbelow(900000) + 100000}"


def create_and_send_otp(email, user_id=None, otp_type="registration"):
    """
    Generate, persist, and dispatch a 6-digit OTP code to the recipient.
    Enforces a 60-second cooldown window to prevent flooding.

    Returns:
        tuple (success: bool, message: str, otp_code: str or None)
    """
    email = email.strip().lower()
    cooldown_seconds = current_app.config.get('OTP_COOLDOWN_SECONDS', 60)
    expiry_minutes = current_app.config.get('OTP_EXPIRY_MINUTES', 10)
    max_attempts = current_app.config.get('OTP_MAX_ATTEMPTS', 5)

    # 1. Check for cooldown from last generated OTP
    last_otp = query_db('''
        SELECT created_at FROM email_otps
        WHERE email = ? AND otp_type = ?
        ORDER BY created_at DESC LIMIT 1
    ''', [email, otp_type], one=True)

    if last_otp and last_otp['created_at']:
        # Parse created_at if returned as string
        created_at = last_otp['created_at']
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                created_at = None

        if created_at:
            elapsed = (datetime.utcnow() - created_at).total_seconds()
            if elapsed < cooldown_seconds:
                remaining = int(cooldown_seconds - elapsed)
                return False, f"Please wait {remaining} seconds before requesting another code.", None

    # 2. Invalidate older unused OTPs for this email and type
    execute_db('''
        UPDATE email_otps SET is_used = 1
        WHERE email = ? AND otp_type = ? AND is_used = 0
    ''', [email, otp_type])

    # 3. Generate new 6-digit code and expiration
    code = generate_otp_code()
    code_hash = generate_password_hash(code)
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=expiry_minutes)

    execute_db('''
        INSERT INTO email_otps (user_id, email, otp_code_hash, otp_type, expires_at, attempts, max_attempts, is_used, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?, 0, ?)
    ''', [user_id, email, code_hash, otp_type, expires_at, max_attempts, now])

    # 4. Dispatch Email
    send_otp_email(email, code, purpose=otp_type)

    return True, f"A 6-digit verification code has been sent to {email}.", code


def verify_otp_code(email, code, otp_type="registration"):
    """
    Validate a provided 6-digit OTP code against the database.
    Checks expiry, attempt limits, and cryptographic hash match.

    Returns:
        tuple (success: bool, message: str)
    """
    email = email.strip().lower()
    code = str(code).strip()

    otp_row = query_db('''
        SELECT * FROM email_otps
        WHERE email = ? AND otp_type = ? AND is_used = 0
        ORDER BY created_at DESC LIMIT 1
    ''', [email, otp_type], one=True)

    if not otp_row:
        return False, "No active verification code found. Please request a new code."

    # Check attempt limit
    attempts = otp_row['attempts']
    max_attempts = otp_row['max_attempts']
    if attempts >= max_attempts:
        execute_db('UPDATE email_otps SET is_used = 1 WHERE id = ?', [otp_row['id']])
        return False, "Maximum verification attempts exceeded. Please request a new code."

    # Check expiration
    expires_at = otp_row['expires_at']
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except Exception:
            pass

    if isinstance(expires_at, datetime) and datetime.utcnow() > expires_at:
        execute_db('UPDATE email_otps SET is_used = 1 WHERE id = ?', [otp_row['id']])
        return False, "This verification code has expired. Please request a new code."

    # Validate code hash
    if not check_password_hash(otp_row['otp_code_hash'], code):
        new_attempts = attempts + 1
        remaining = max_attempts - new_attempts
        execute_db('UPDATE email_otps SET attempts = ? WHERE id = ?', [new_attempts, otp_row['id']])
        if remaining <= 0:
            execute_db('UPDATE email_otps SET is_used = 1 WHERE id = ?', [otp_row['id']])
            return False, "Invalid code. Maximum attempts reached. Please request a new code."
        return False, f"Incorrect verification code. {remaining} attempt(s) remaining."

    # Code is valid - mark used
    execute_db('UPDATE email_otps SET is_used = 1 WHERE id = ?', [otp_row['id']])
    return True, "Code verified successfully."
