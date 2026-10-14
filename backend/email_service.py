"""Email delivery service for RIA AI Agent authentication.

Handles verification OTPs for self-service sign-up and password resets via SMTP
(e.g., Google Workspace with an App Password).
"""
import logging
import os
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

logger = logging.getLogger("ria-email")


def is_smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD"))


def _send_smtp_message(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "587").strip())
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("SMTP_FROM", username).strip() or username
    from_name = os.getenv("SMTP_FROM_NAME", "RIA AI AGENT").strip()

    if not host or not username or not password:
        logger.warning("SMTP is not configured. Could not send email to %s", to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((str(Header(from_name, "utf-8")), from_email))
    msg["To"] = to_email

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(username, password)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        logger.info("Successfully sent email to %s (subject: %s)", to_email, subject)
        return True
    except Exception as exc:
        logger.exception("Failed to send SMTP email to %s: %s", to_email, exc)
        return False


def send_signup_otp(email: str, name: str, code: str) -> bool:
    """Sends 6-digit confirmation code for new workspace registration."""
    subject = f"{code} is your RIA account verification code"
    first_name = name.split()[0] if name else "there"

    text = (
        f"Hi {first_name},\n\n"
        f"Your verification code to set up your RIA company account is: {code}\n\n"
        "This code will expire in 15 minutes.\n"
        "If you did not request this code, please ignore this email.\n\n"
        "— RIA AI Agent Team"
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; color: #1e293b; }}
        .card {{ max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
        .header {{ background: linear-gradient(135deg, #091e42 0%, #0052cc 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
        .header p {{ margin: 6px 0 0; font-size: 13px; color: #bae3ff; }}
        .content {{ padding: 32px 28px; }}
        .content p {{ font-size: 15px; line-height: 1.6; color: #334155; margin: 0 0 16px; }}
        .code-box {{ background: #f0f7ff; border: 2px dashed #0052cc; border-radius: 8px; padding: 18px; text-align: center; margin: 24px 0; }}
        .code {{ font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #0052cc; font-family: monospace; }}
        .exp {{ font-size: 13px; color: #64748b; margin-top: 8px; }}
        .footer {{ border-top: 1px solid #f1f5f9; padding: 20px 28px; font-size: 12px; color: #94a3b8; text-align: center; line-height: 1.5; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>RIA AI Agent</h1>
          <p>Distribution Intelligence & Collections Platform</p>
        </div>
        <div class="content">
          <p>Hi <b>{first_name}</b>,</p>
          <p>Thank you for setting up your workspace on RIA. Use the verification code below to confirm your email and activate your account:</p>
          <div class="code-box">
            <div class="code">{code}</div>
            <div class="exp">Expires in 15 minutes</div>
          </div>
          <p style="font-size: 13px; color: #64748b;">If you didn't request this code, you can safely ignore this email. Never share this code with anyone.</p>
        </div>
        <div class="footer">
          &copy; 2026 RIA AI Agent. Secured Enterprise Platform.
        </div>
      </div>
    </body>
    </html>
    """
    return _send_smtp_message(email, subject, html, text)


def send_password_reset_otp(email: str, name: str, code: str) -> bool:
    """Sends 6-digit code for password reset."""
    subject = f"{code} is your RIA password reset code"
    first_name = name.split()[0] if name else "there"

    text = (
        f"Hi {first_name},\n\n"
        f"We received a request to reset your password. Your reset code is: {code}\n\n"
        "This code will expire in 15 minutes.\n"
        "If you did not request a password reset, please secure your account immediately.\n\n"
        "— RIA AI Agent Team"
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; color: #1e293b; }}
        .card {{ max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
        .header {{ background: linear-gradient(135deg, #091e42 0%, #0052cc 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
        .header p {{ margin: 6px 0 0; font-size: 13px; color: #bae3ff; }}
        .content {{ padding: 32px 28px; }}
        .content p {{ font-size: 15px; line-height: 1.6; color: #334155; margin: 0 0 16px; }}
        .code-box {{ background: #fef2f2; border: 2px dashed #dc2626; border-radius: 8px; padding: 18px; text-align: center; margin: 24px 0; }}
        .code {{ font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #dc2626; font-family: monospace; }}
        .exp {{ font-size: 13px; color: #64748b; margin-top: 8px; }}
        .footer {{ border-top: 1px solid #f1f5f9; padding: 20px 28px; font-size: 12px; color: #94a3b8; text-align: center; line-height: 1.5; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>RIA AI Agent</h1>
          <p>Password Reset Request</p>
        </div>
        <div class="content">
          <p>Hi <b>{first_name}</b>,</p>
          <p>We received a request to reset the password for your RIA account (<b>{email}</b>). Use this code to continue:</p>
          <div class="code-box">
            <div class="code">{code}</div>
            <div class="exp">Expires in 15 minutes</div>
          </div>
          <p style="font-size: 13px; color: #64748b;">If you did not request this, someone else may be trying to access your account. You can safely ignore this email; your password will not be changed.</p>
        </div>
        <div class="footer">
          &copy; 2026 RIA AI Agent. Secured Enterprise Platform.
        </div>
      </div>
    </body>
    </html>
    """
    return _send_smtp_message(email, subject, html, text)
