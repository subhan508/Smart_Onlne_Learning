"""
Email Notification Service for SmartLearn.
Supports:
1. Resend REST API (HTTP-based, recommended for cloud platforms like Render where outbound SMTP is blocked)
2. Standard SMTP (Gmail, SendGrid, Amazon SES) as fallback when RESEND_API_KEY is not set
3. Automatic safe console logging for development and test environments
"""

import json
import smtplib
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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
    Send an email via configured provider:
    1. Resend API (HTTP-based, recommended for cloud platforms like Render where SMTP ports are blocked).
    2. SMTP Server (Gmail, SendGrid, etc. if RESEND_API_KEY is not set).
    3. Console / Logger simulation (if in TESTING mode or no credentials are configured).

    Returns:
        tuple (success: bool, message: str)
    """
    # If running in testing mode, simulate delivery
    if current_app.config.get('TESTING'):
        return True, "Simulated email dispatch (test mode)"

    resend_api_key = (current_app.config.get('RESEND_API_KEY') or '').strip()

    # Priority 1: Resend HTTP API (avoids Render SMTP port blocks)
    if resend_api_key:
        from_sender = (current_app.config.get('RESEND_FROM_EMAIL') or '').strip()
        if not from_sender:
            configured_sender = (current_app.config.get('MAIL_DEFAULT_SENDER') or '').strip()
            # If sender is not the default dummy noreply@smartlearn.com, use it
            if configured_sender and not any(dummy in configured_sender for dummy in ('@smartlearn.com', '@example.com')):
                from_sender = configured_sender
            else:
                from_sender = 'SmartLearn <onboarding@resend.dev>'

        return _send_via_resend(
            api_key=resend_api_key,
            from_email=from_sender,
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text
        )

    # Priority 2: Standard SMTP Server Fallback
    server_host = current_app.config.get('MAIL_SERVER')
    server_port = current_app.config.get('MAIL_PORT', 587)
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    use_ssl = current_app.config.get('MAIL_USE_SSL', False)
    username = current_app.config.get('MAIL_USERNAME', '')
    password = current_app.config.get('MAIL_PASSWORD', '')
    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@smartlearn.com')

    if not username or not password or not server_host:
        print(f"\n==================== [DEVELOPMENT EMAIL DISPATCH] ====================")
        print(f"To:      {to_email}")
        print(f"Subject: {subject}")
        print(f"From:    {sender}")
        print(f"Content:\n{body_text or body_html}")
        print(f"======================================================================\n")
        return True, "Simulated email dispatch (dev mode: no email provider configured)"

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to_email

        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html'))

        if use_ssl:
            with smtplib.SMTP_SSL(server_host, server_port, timeout=10) as server:
                server.login(username, password)
                server.sendmail(sender, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(server_host, server_port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                server.login(username, password)
                server.sendmail(sender, [to_email], msg.as_string())

        return True, "Email sent successfully via SMTP."
    except Exception as e:
        current_app.logger.error(f"[Email Error] Failed to send email via SMTP to {to_email}: {e}")
        print(f"[Email Error] Failed to send email via SMTP to {to_email}: {e}")
        return False, str(e)


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
