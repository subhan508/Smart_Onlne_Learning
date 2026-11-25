"""
Email Notification Service for SmartLearn.
Powered by Resend REST API (HTTPS).
Avoids blocked SMTP ports (25, 465, 587) on cloud platforms like Render.
"""

import json
import os
import urllib.error
import urllib.request
from flask import current_app


def _send_via_resend(api_key, from_email, to_email, subject, body_html, body_text=None):
    """
    Send an email via the Resend REST API using urllib.request (zero extra dependencies).
    """
    url = "https://api.resend.com/emails"
    payload = {
        "from": from_email,
        "to": [to_email] if isinstance(to_email, str) else to_email,
        "subject": subject,
        "html": body_html,
    }
    if body_text:
        payload["text"] = body_text

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SmartLearn/1.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = response.read().decode("utf-8")
            res_data = json.loads(res_body) if res_body else {}
            email_id = res_data.get("id", "ok")
            current_app.logger.info(f"[Resend] Email delivered to {to_email} (ID: {email_id})")
            return True, f"Email sent via Resend (ID: {email_id})"
    except urllib.error.HTTPError as e:
        error_msg = f"HTTP {e.code}: {e.reason}"
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
            if "message" in err_json:
                error_msg = f"{err_json['message']} (HTTP {e.code})"
        except Exception:
            pass
        current_app.logger.error(f"[Resend Error] Failed to send email to {to_email}: {error_msg}")
        return False, error_msg
    except Exception as e:
        current_app.logger.error(f"[Resend Error] Network exception sending to {to_email}: {e}")
        return False, str(e)


def send_email(to_email, subject, body_html, body_text=None):
    """
    Send an email via Resend HTTPS REST API.
    Simulates delivery safely in TESTING or local dev mode if RESEND_API_KEY is not configured.

    Returns:
        tuple (success: bool, message: str)
    """
    # 1. Automated test mode
    if current_app.config.get('TESTING'):
        return True, "Simulated email dispatch (test mode)"

    api_key = (current_app.config.get('RESEND_API_KEY') or '').strip()
    from_email = (
        current_app.config.get('EMAIL_FROM')
        or current_app.config.get('RESEND_FROM_EMAIL')
        or current_app.config.get('MAIL_DEFAULT_SENDER')
        or 'SmartLearn <onboarding@resend.dev>'
    ).strip()

    # If the sender is still the dummy default, use Resend's default onboarding address
    if not from_email or any(dummy in from_email for dummy in ('@smartlearn.com', '@example.com')):
        if not (current_app.config.get('EMAIL_FROM') or current_app.config.get('RESEND_FROM_EMAIL')):
            from_email = 'SmartLearn <onboarding@resend.dev>'

    # 2. Resend API Key is set -> Send via Resend HTTPS API
    if api_key:
        return _send_via_resend(
            api_key=api_key,
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text
        )

    # 3. No RESEND_API_KEY configured:
    # On Render / cloud production, outbound SMTP is blocked. Never try raw SMTP sockets that cause [Errno 101].
    is_cloud_or_prod = (
        current_app.config.get('ENV') == 'production'
        or os.environ.get('RENDER') == 'true'
        or os.environ.get('FLASK_ENV') == 'production'
        or not current_app.debug
    )

    if is_cloud_or_prod:
        err = (
            "Email delivery failed: RESEND_API_KEY is not configured. "
            "Outbound SMTP is blocked on Render. Please configure RESEND_API_KEY in the Render Dashboard."
        )
        current_app.logger.error(f"[Email Error] {err}")
        return False, err

    # 4. Local development mode without API key: log safely to console
    print(f"\n==================== [LOCAL DEV EMAIL DISPATCH] ====================")
    print(f"To:      {to_email}")
    print(f"From:    {from_email}")
    print(f"Subject: {subject}")
    print(f"Content:\n{body_text or body_html}")
    print(f"====================================================================\n")
    return True, "Simulated email dispatch (local dev mode: RESEND_API_KEY not configured)"


def send_otp_email(to_email, otp_code, purpose="registration"):
    """Send a 6-digit OTP verification email."""
    if purpose == "registration":
        subject = f"SmartLearn Verification Code: {otp_code}"
        action_desc = "verify your new SmartLearn account"
    else:
        subject = f"SmartLearn Password Reset Code: {otp_code}"
        action_desc = "reset your SmartLearn account password"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0f1117; color: #e2e8f0; margin: 0; padding: 20px; }}
            .container {{ max-width: 520px; margin: 0 auto; background: #1a1d29; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 32px; }}
            .logo {{ font-size: 24px; font-weight: bold; color: #6c63ff; text-align: center; margin-bottom: 24px; }}
            .otp-box {{ text-align: center; margin: 28px 0; }}
            .otp-code {{ font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #6c63ff; background: rgba(108,99,255,0.1); padding: 14px 24px; border-radius: 8px; display: inline-block; border: 1px dashed #6c63ff; }}
            .footer {{ font-size: 12px; color: #718096; text-align: center; margin-top: 32px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">SmartLearn Platform</div>
            <p>Hello,</p>
            <p>Your one-time verification code to {action_desc} is:</p>
            <div class="otp-box">
                <span class="otp-code">{otp_code}</span>
            </div>
            <p>This code is valid for <strong>10 minutes</strong>. Never share this code with anyone.</p>
            <p>If you did not request this verification, you can safely ignore this email.</p>
            <div class="footer">
                &copy; SmartLearn Platform. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    text = f"""
    SmartLearn Platform
    -------------------
    Your one-time verification code to {action_desc} is: {otp_code}

    This code is valid for 10 minutes. Never share this code with anyone.
    If you did not request this, please disregard this message.
    """

    return send_email(to_email, subject, html, text)


def send_account_approved_email(to_email, user_name):
    """Notify user that their account was approved by administrator."""
    subject = "SmartLearn: Your Account Has Been Approved!"
    base_url = current_app.config.get('APP_URL', 'http://localhost:5000').rstrip('/')
    login_url = f"{base_url}/login"
    html = f"""
    <div style="font-family: sans-serif; background-color: #0f1117; color: #e2e8f0; padding: 30px;">
        <div style="max-width: 500px; margin: auto; background: #1a1d29; border-radius: 10px; padding: 25px; border: 1px solid rgba(255,255,255,0.1);">
            <h2 style="color: #10b981; margin-top: 0;">Account Approved</h2>
            <p>Hello {user_name},</p>
            <p>Great news! Your registration request has been reviewed and approved by the SmartLearn administrator.</p>
            <p>You can now log in and access your courses and learning dashboard.</p>
            <p style="margin-top: 25px;"><a href="{login_url}" style="background: #6c63ff; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold;">Log In Now</a></p>
        </div>
    </div>
    """
    text = f"Hello {user_name},\nYour SmartLearn registration has been approved! You can now log in at: {login_url}"
    return send_email(to_email, subject, html, text)


def send_account_rejected_email(to_email, user_name, reason=None):
    """Notify user that their account was rejected by administrator."""
    subject = "SmartLearn: Registration Update"
    reason_text = f"<p><strong>Reason provided:</strong> {reason}</p>" if reason else ""
    html = f"""
    <div style="font-family: sans-serif; background-color: #0f1117; color: #e2e8f0; padding: 30px;">
        <div style="max-width: 500px; margin: auto; background: #1a1d29; border-radius: 10px; padding: 25px; border: 1px solid rgba(255,255,255,0.1);">
            <h2 style="color: #ef4444; margin-top: 0;">Registration Update</h2>
            <p>Hello {user_name},</p>
            <p>Thank you for your interest in SmartLearn. After reviewing your registration, your account request was not approved at this time.</p>
            {reason_text}
            <p>If you believe this was an error, please contact the administrator.</p>
        </div>
    </div>
    """
    text = f"Hello {user_name},\nYour SmartLearn registration was not approved. {f'Reason: {reason}' if reason else ''}"
    return send_email(to_email, subject, html, text)
