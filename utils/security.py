"""
Security and validation utilities for SmartLearn.
Includes password strength validation, account access gating, and input sanitization.
"""

import re


def validate_password_strength(password):
    """
    Enforces production-grade password strength rules:
    - Minimum 8 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one number (0-9)
    - At least one special symbol (!@#$%^&*()_+-=[]{}|;:,.<>?)
    
    Returns:
        tuple (is_valid: bool, error_message: str or None)
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit (0-9)."

    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=[\]\\/]', password):
        return False, "Password must contain at least one special character (!@#$%^&*...)."

    return True, None


def check_account_access(user_dict_or_obj):
    """
    Verifies that a user has approved access to login and view application dashboards.
    Supports sqlite3.Row, dict, SQLAlchemy Model, or custom User classes.

    States:
        - 'unverified': must complete email OTP verification.
        - 'pending_approval': waiting for admin review.
        - 'rejected': rejected by admin.
        - 'suspended': account suspended.
        - 'approved': full access granted.

    Returns:
        tuple (allowed: bool, status: str, message: str)
    """
    if not user_dict_or_obj:
        return False, "not_found", "User account not found."

    def _get(field, default=None):
        # 1. Try dict-like / sqlite3.Row access
        if hasattr(user_dict_or_obj, '__getitem__'):
            try:
                val = user_dict_or_obj[field]
                if val is not None:
                    return val
            except (KeyError, IndexError, TypeError):
                pass
        # 2. Try object attribute access
        if hasattr(user_dict_or_obj, field):
            val = getattr(user_dict_or_obj, field)
            if val is not None:
                return val
        return default

    status = _get('status', 'approved')
    is_active = _get('is_active', 1)
    rejection_reason = _get('rejection_reason', None)

    if not bool(is_active):
        return False, "deactivated", "Your account has been deactivated. Please contact an administrator."

    if status == 'unverified':
        return False, "unverified", "Please verify your email address to activate your account."

    if status == 'pending_approval':
        return False, "pending_approval", "Your account is currently awaiting administrator review and approval."

    if status == 'rejected':
        msg = f"Your registration was rejected. Reason: {rejection_reason}" if rejection_reason else "Your registration request was rejected by an administrator."
        return False, "rejected", msg

    if status == 'suspended':
        return False, "suspended", "Your account has been suspended. Please contact support."

    if status == 'approved':
        return True, "approved", "Access granted."

    return False, "unknown", "Account status unrecognized."
