"""Google SMTP transport. App passwords stay in server environment variables."""
import os
import smtplib
import ssl
from email.message import EmailMessage


def configured():
    return bool(os.getenv('SMTP_USERNAME') and os.getenv('SMTP_PASSWORD') and os.getenv('PERSONALBUDGET_APP_URL'))


def send_reset(recipient, token):
    url = os.environ['PERSONALBUDGET_APP_URL'].rstrip('/') + '/#reset=' + token
    message = EmailMessage()
    message['Subject'] = 'Redefinir sua senha · Personal Budget'
    message['From'] = os.getenv('SMTP_FROM', os.environ['SMTP_USERNAME'])
    message['To'] = recipient
    message.set_content(f'Você solicitou a recuperação da sua senha no Personal Budget.\n\nAbra este link para criar uma nova senha:\n{url}\n\nO link expira em 20 minutos e só pode ser usado uma vez.\nSe não foi você, ignore este e-mail. Sua senha permanece igual.\n')
    host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.getenv('SMTP_PORT', '587'))
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as client:
            client.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
            client.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            client.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
            client.send_message(message)
