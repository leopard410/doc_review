import smtplib
from email.message import EmailMessage

from fastapi import Request

from app.config import settings


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


def _is_configured() -> bool:
    return bool(settings.smtp_email and settings.smtp_password and settings.notify_email)


def send_work_notification(
    request: Request,
    *,
    filename: str,
    chapters_processed: int,
) -> None:
    """Email the site owner when a client processes a document. No-op if SMTP is not configured."""
    if not _is_configured():
        return

    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")

    msg = EmailMessage()
    msg["Subject"] = f"Document processed from {ip}"
    msg["From"] = settings.smtp_email
    msg["To"] = settings.notify_email
    msg.set_content(
        f"A client used your DOCX Editorial Annotator.\n\n"
        f"IP address: {ip}\n"
        f"File: {filename}\n"
        f"Chapters processed: {chapters_processed}\n"
        f"User-Agent: {user_agent}\n"
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(settings.smtp_email, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        return
