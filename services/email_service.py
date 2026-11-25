"""
Email Notification Service for SmartLearn.
Supports standard SMTP (Gmail, SendGrid, Mailgun, Amazon SES) with automatic
safe console/logger fallback in development and testing environments.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def send_email(to_email, subject, body_html, body_text=None):
    """
    Send an email via configured SMTP server.
    If SMTP credentials are not configured (local dev/test), logs to console safely.

    Returns:
        tuple (success: bool, message: str)
    """
    server_host = current_app.config.get('MAIL_SERVER')
    server_port = current_app.config.get('MAIL_PORT', 587)
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    use_ssl = current_app.config.get('MAIL_USE_SSL', False)
    username = current_app.config.get('MAIL_USERNAME', '')
    password = current_app.config.get('MAIL_PASSWORD', '')
    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@smartlearn.com')

    # If running in testing mode or credentials are not configured, simulate delivery
    if current_app.config.get('TESTING') or not username or not password:
        print(f"\n==================== [DEVELOPMENT EMAIL DISPATCH] ====================")
        print(f"To:      {to_email}")
        print(f"Subject: {subject}")
        print(f"From:    {sender}")
        print(f"Content:\n{body_text or body_html}")
        print(f"======================================================================\n")
        return True, "Simulated email dispatch (dev mode)"

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

        return True, "Email sent successfully."
    except Exception as e:
        print(f"[Email Error] Failed to send email to {to_email}: {e}")
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
    html = f"""
    <div style="font-family: sans-serif; background-color: #0f1117; color: #e2e8f0; padding: 30px;">
        <div style="max-width: 500px; margin: auto; background: #1a1d29; border-radius: 10px; padding: 25px; border: 1px solid rgba(255,255,255,0.1);">
            <h2 style="color: #10b981; margin-top: 0;">Account Approved</h2>
            <p>Hello {user_name},</p>
            <p>Great news! Your registration request has been reviewed and approved by the SmartLearn administrator.</p>
            <p>You can now log in and access your courses and learning dashboard.</p>
            <p style="margin-top: 25px;"><a href="http://localhost:5001/login" style="background: #6c63ff; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold;">Log In Now</a></p>
        </div>
    </div>
    """
    text = f"Hello {user_name},\nYour SmartLearn registration has been approved! You can now log in."
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
