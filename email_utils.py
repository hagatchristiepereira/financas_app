# email desativado (modo desenvolvimento)

def enviar_email_senha(*args, **kwargs):
    return True

def enviar_email(*args, **kwargs):
    return True


'''import smtplib
import os
from email.message import EmailMessage
from typing import Optional

# Config via env vars
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)

def send_email(to_email: str, subject: str, body: str, html: Optional[str] = None) -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:

        print(f"[DEV EMAIL] to={to_email} subject={subject}\n{body}")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

def send_temporary_password(to_email: str, temp_password: str, nome: str = "usuário"):
    subject = "Sua senha temporária - Minha Renda"
    body = (
        f"Olá {nome},\n\n"
        f"Uma conta foi criada/atualizada para você no Minha Renda.\n\n"
        f"Senha temporária: {temp_password}\n\n"
        "Ao entrar pela primeira vez, você será solicitado(a) a trocar a senha.\n\n"
        "Se você não solicitou isso, ignore esta mensagem.\n\n"
        "Atenciosamente,\nMinha Renda"
    )
    send_email(to_email, subject, body)'''