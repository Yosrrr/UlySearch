import re
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


def _html_to_text(html_body: str) -> str:
    """Fallback texte brut minimal pour les clients qui n'affichent pas le HTML."""
    text = re.sub(r"<br\s*/?>", "\n", html_body, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Envoie un email HTML.
    Retourne True si succès, False sinon.
    Ne lève jamais d'exception vers l'appelant.
    """
    if not to_email or not str(to_email).strip():
        print("[mailer] Destinataire vide — envoi ignoré.")
        return False

    if not html_body or not str(html_body).strip():
        print(f"[mailer] Corps vide pour {to_email} — envoi ignoré.")
        return False

    # Garde-fou : détecte un body qui ressemble à du code Python non rendu
    suspicious_markers = (
        "env.get_template(",
        "jinja_env.get_template(",
        "send_email(",
        "db.add(SentLog",
    )
    if any(marker in html_body for marker in suspicious_markers):
        print(
            f"[mailer] ⚠️ Corps suspect (code Python non rendu) pour {to_email} — envoi bloqué."
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SENDER_EMAIL
    msg["To"] = to_email

    # Version texte d'abord, puis HTML (ordre recommandé RFC)
    msg.attach(MIMEText(_html_to_text(html_body), "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SENDER_EMAIL, [to_email], msg.as_string())
            print(f"[mailer] ✅ Envoyé à {to_email} — {subject[:60]}")
            return True
        except Exception as e:
            print(
                f"[mailer] Tentative {attempt}/{MAX_RETRIES} échouée pour {to_email} : {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * attempt)

    print(
        f"[mailer] ❌ Échec définitif pour {to_email} après {MAX_RETRIES} tentatives."
    )
    return False