import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT

try:
    from plyer import notification as _plyer_notification
    _PLYER_AVAILABLE = True
except ImportError:
    _PLYER_AVAILABLE = False


def send_desktop_notification(title: str, message: str) -> None:
    if not _PLYER_AVAILABLE:
        print(f"[Desktop] {title}: {message}")
        return
    _plyer_notification.notify(
        title=title,
        message=message,
        app_name="IPO Tracker",
        timeout=10,
    )


def send_email(new_ipos: list[dict]) -> bool:
    """Sendet eine E-Mail mit den neuen IPOs. Gibt True bei Erfolg zurück."""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        return False

    subject = f"IPO Tracker: {len(new_ipos)} neue Börsengang(e) entdeckt"

    lines = [f"Neue IPOs gefunden ({len(new_ipos)}):\n"]
    for ipo in new_ipos:
        lines.append(
            f"  • {ipo.get('name', 'N/A')} ({ipo.get('symbol', '?')})\n"
            f"    Datum: {ipo.get('date', 'N/A')}\n"
            f"    Börse: {ipo.get('exchange', 'N/A')}\n"
            f"    Preis: {ipo.get('price', 'N/A')}\n"
            f"    Status: {ipo.get('status', 'N/A')}\n"
        )

    body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        return True
    except Exception as e:
        print(f"E-Mail Fehler: {e}")
        return False


def notify_new_ipos(new_ipos: list[dict]) -> None:
    """Desktop-Benachrichtigung + E-Mail für neue IPOs."""
    if not new_ipos:
        return

    names = ", ".join(ipo.get("name", "?") for ipo in new_ipos[:3])
    suffix = f" (+{len(new_ipos) - 3} weitere)" if len(new_ipos) > 3 else ""
    send_desktop_notification(
        title=f"{len(new_ipos)} neuer Börsengang!",
        message=f"{names}{suffix}",
    )

    if send_email(new_ipos):
        print("E-Mail erfolgreich gesendet.")
    else:
        print("(E-Mail nicht konfiguriert — nur Desktop-Benachrichtigung.)")
