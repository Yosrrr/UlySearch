import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Retourne True si l'envoi a réussi, False sinon — ne lève jamais
    d'exception vers l'appelant, pour ne jamais interrompre une boucle
    d'envoi en cours (un échec sur un marché ne doit pas bloquer les
    suivants)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SENDER_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SENDER_EMAIL, [to_email], msg.as_string())
            return True
        except Exception as e:
            print(f"[mailer] Tentative {attempt}/{MAX_RETRIES} échouée pour {to_email} : {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * attempt)  # backoff progressif

    print(f"[mailer] Échec définitif de l'envoi à {to_email} après {MAX_RETRIES} tentatives.")
    return False