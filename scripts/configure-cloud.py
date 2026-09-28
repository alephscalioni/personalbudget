"""Provision private access without writing secrets to logs or Git."""
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.auth import password_hash

path = root / '.runtime' / 'cloud-access.json'
path.parent.mkdir(exist_ok=True)
if path.exists():
    credentials = json.loads(path.read_text())
else:
    password = secrets.token_urlsafe(18)
    credentials = {'password': password, 'password_hash': password_hash(password), 'session_secret': secrets.token_urlsafe(48)}
    path.write_text(json.dumps(credentials, indent=2))
    path.chmod(0o600)
variables = {
    'PERSONALBUDGET_AUTH_REQUIRED': '1',
    'PERSONALBUDGET_PASSWORD_HASH': credentials['password_hash'],
    'PERSONALBUDGET_SESSION_SECRET': credentials['session_secret'],
    'PERSONALBUDGET_PUBLIC_ORIGINS': 'https://personalbudget-beta.vercel.app',
    'PERSONALBUDGET_APP_URL': 'https://personalbudget-beta.vercel.app',
    'PERSONALBUDGET_REPORTS': '/data/reports',
    'PERSONALBUDGET_DATABASE': '/data/budget.sqlite3',
    'PERSONALBUDGET_FINANCE_CONFIG': '/data/config',
}
for key, value in variables.items():
    result = subprocess.run(['railway','variable','set',key,'--stdin','--skip-deploys'], input=value, text=True, capture_output=True, cwd=root)
    if result.returncode:
        raise SystemExit(f'Falha ao configurar {key}; código {result.returncode}. Nenhum segredo foi registrado no log.')
    print('Configurado:', key, flush=True)
print('Credenciais guardadas em .runtime/cloud-access.json; não versionar esse arquivo.')
