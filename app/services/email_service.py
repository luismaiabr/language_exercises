import html
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def markdown_to_clean_html(md_text: str) -> str:
    """Converts clean markdown lesson text into dark-theme email-safe HTML."""
    if not md_text:
        return ""

    escaped = html.escape(md_text.strip())

    # Format Markdown Headers (###, ##, #)
    escaped = re.sub(
        r"^###\s+(.+)$",
        r'<h3 style="color: #58A6FF; font-size: 16px; margin: 22px 0 8px 0; font-weight: 700;">\1</h3>',
        escaped,
        flags=re.MULTILINE,
    )
    escaped = re.sub(
        r"^##\s+(.+)$",
        r'<h2 style="color: #FFFFFF; font-size: 18px; margin: 26px 0 10px 0; font-weight: 700;">\1</h2>',
        escaped,
        flags=re.MULTILINE,
    )
    escaped = re.sub(
        r"^#\s+(.+)$",
        r'<h1 style="color: #FFFFFF; font-size: 22px; margin: 28px 0 12px 0; font-weight: 800;">\1</h1>',
        escaped,
        flags=re.MULTILINE,
    )

    # Format bold (**text**)
    escaped = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color: #FFFFFF;">\1</strong>', escaped)
    # Format italic (*text*)
    escaped = re.sub(r"\*(.+?)\*", r'<em style="color: #D2A8FF;">\1</em>', escaped)

    # Format Pro-Tips (💡 Pro-Tip: ...)
    escaped = re.sub(
        r"(💡\s*(?:Pro-Tip|Tip):?[^\n]+)",
        r'<div style="background-color: #1C2128; border-left: 3px solid #D29922; padding: 12px 14px; margin: 16px 0; border-radius: 4px; color: #E6EDF3; font-size: 13.5px; line-height: 1.5;">\1</div>',
        escaped,
    )

    # Format phonetic brackets (e.g. [tsvy], [nool])
    escaped = re.sub(
        r"(\[[a-zA-Z0-9\s/_\-ÄÖÜäöüß]+\])",
        r'<span style="color: #7EE787; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px;">\1</span>',
        escaped,
    )

    # Convert linebreaks and paragraph spacing
    paragraphs = escaped.split("\n\n")
    formatted_paras = []
    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        if p_clean.startswith("<h") or p_clean.startswith("<div"):
            formatted_paras.append(p_clean.replace("\n", "<br>"))
        else:
            p_with_breaks = p_clean.replace("\n", "<br>")
            formatted_paras.append(
                f'<p style="margin: 0 0 14px 0; color: #C9D1D9; font-size: 14.5px; line-height: 1.65;">{p_with_breaks}</p>'
            )

    return "\n".join(formatted_paras)


def render_plain_text_email(
    student_name: str,
    course_name: str,
    lesson_id: int,
    theory_summary: Optional[str],
    magic_link_url: str,
) -> str:
    """Renders clean markdown plain text lesson email without exercises list."""
    lines = []
    if theory_summary:
        lines.append(theory_summary.strip())
    else:
        lines.append(f"🇩🇪 German Micro-Lesson #{lesson_id:03d}: {course_name}")

    lines.extend([
        "",
        "---",
        "🎯 START INTERACTIVE EXERCISES ONLINE:",
        magic_link_url,
        "",
        "(5 interactive exercises • Valid for 7 days • Zero password/login required)",
    ])

    return "\n".join(lines)


def render_html_email(
    student_name: str,
    course_name: str,
    lesson_id: int,
    theory_summary: Optional[str],
    magic_link_url: str,
) -> str:
    """Renders simple, elegant markdown-styled dark HTML email."""
    safe_course = html.escape(course_name)
    safe_url = html.escape(magic_link_url)

    content_html = (
        markdown_to_clean_html(theory_summary)
        if theory_summary
        else f"<p>Lektion #{lesson_id:03d} vorbereitet.</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_course} — Lektion #{lesson_id:03d}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0A0A0A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #C9D1D9; -webkit-font-smoothing: antialiased;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #0A0A0A; padding: 24px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 620px; background-color: #121212; border: 1px solid #262626; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);" cellspacing="0" cellpadding="0" border="0">
                    
                    <!-- Top Category Bar -->
                    <tr>
                        <td style="padding: 20px 24px 16px 24px; border-bottom: 1px solid #1F1F1F;">
                            <div style="display: inline-block; font-size: 11px; font-weight: 700; color: #00E5FF; text-transform: uppercase; letter-spacing: 1px;">
                                🇩🇪 {safe_course} • Lektion #{lesson_id:03d}
                            </div>
                        </td>
                    </tr>

                    <!-- Markdown Content Body -->
                    <tr>
                        <td style="padding: 24px; font-size: 14.5px; line-height: 1.65; color: #C9D1D9;">
                            {content_html}

                            <!-- Interactive Magic Link Call-to-Action -->
                            <div style="margin-top: 32px; padding: 20px; background-color: #181818; border: 1px solid #00E5FF; border-radius: 8px; text-align: center; box-shadow: 0 4px 14px rgba(0, 229, 255, 0.12);">
                                <p style="margin: 0 0 14px 0; color: #FFFFFF; font-size: 14px; font-weight: 600;">
                                    🎯 Start your 5 interactive exercises online (Zero login required):
                                </p>
                                
                                <div style="margin-bottom: 12px;">
                                    <a href="{safe_url}" target="_blank" style="display: inline-block; padding: 12px 28px; background-color: #00E5FF; color: #0A0A0A; text-decoration: none; font-size: 14px; font-weight: 800; border-radius: 6px; letter-spacing: 0.5px;">
                                        Start Exercises Online →
                                    </a>
                                </div>

                                <div style="font-size: 11.5px; color: #888888; word-break: break-all;">
                                    Direct Link: <a href="{safe_url}" style="color: #00E5FF; text-decoration: underline;">{safe_url}</a>
                                </div>
                            </div>
                        </td>
                    </tr>

                    <!-- Simple Footer -->
                    <tr>
                        <td style="padding: 16px 24px; background-color: #0D0D0D; border-top: 1px solid #1F1F1F; text-align: center;">
                            <p style="margin: 0; font-size: 11.5px; color: #666666;">
                                Deutsch Daily • Micro-Learning Service • Ephemeral Link valid for 7 days
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


class EmailDispatchResult:
    def __init__(self, success: bool, message: str = "", error: Optional[str] = None):
        self.success = success
        self.message = message
        self.error = error

    def __repr__(self):
        return f"<EmailDispatchResult success={self.success} message='{self.message}'>"


class EmailService:
    def __init__(self, is_mock: bool = False):
        self.is_mock = is_mock
        self.mock_sent_emails: List[Dict[str, Any]] = []

    def send_lesson_email(
        self,
        recipient_email: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> EmailDispatchResult:
        """Transmits a multi-part HTML & plain-text lesson email via SMTP."""
        recipient_clean = recipient_email.strip().lower()

        if self.is_mock or not settings.is_smtp_configured:
            logger.info(
                f"[MOCK/FALLBACK SMTP] Email prepared for {recipient_clean}. Subject: '{subject}'"
            )
            self.mock_sent_emails.append({
                "to": recipient_clean,
                "subject": subject,
                "text": text_content,
                "html": html_content,
            })
            return EmailDispatchResult(
                success=True,
                message=f"[Mock] Email to {recipient_clean} simulated (SMTP not configured).",
            )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = recipient_clean

            part1 = MIMEText(text_content, "plain", "utf-8")
            part2 = MIMEText(html_content, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            logger.info(
                f"Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}..."
            )
            if settings.SMTP_USE_SSL:
                server = smtplib.SMTP_SSL(
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT,
                )
            else:
                server = smtplib.SMTP(
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT,
                )
                if settings.SMTP_USE_TLS:
                    server.starttls()

            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [recipient_clean], msg.as_string())
            server.quit()

            logger.info(f"Successfully delivered email via SMTP to {recipient_clean}.")
            return EmailDispatchResult(
                success=True,
                message=f"Email delivered successfully to {recipient_clean}",
            )

        except Exception as exc:
            err = f"SMTP transmission failure to {recipient_clean}: {exc}"
            logger.error(err)
            return EmailDispatchResult(success=False, message=err, error=str(exc))

    async def trigger_scheduler_cron(self) -> int:
        """Triggers the scheduler's /api/cron endpoint to process due lessons."""
        scheduler_url = settings.SCHEDULER_URL.rstrip("/")
        endpoint = f"{scheduler_url}/api/cron"
        headers = {}
        if settings.CRON_SECRET:
            headers["Authorization"] = f"Bearer {settings.CRON_SECRET}"

        logger.info(f"Triggering instant dispatch on scheduler at {endpoint}...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(endpoint, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    count = data.get("processed_count", 0)
                    logger.info(f"Scheduler /api/cron triggered successfully. Dispatched {count} email(s).")
                    return count
                else:
                    logger.warning(
                        f"Scheduler /api/cron returned HTTP {res.status_code}: {res.text[:200]}"
                    )
        except Exception as exc:
            logger.warning(
                f"Failed to connect to scheduler at {endpoint}: {exc}"
            )
        return 0


email_service = EmailService()
