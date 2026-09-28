"""Upload SMTP configuration using stdin, without logging credentials."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / '.runtime' / 'smtp.env'
allowed = {'SMTP_HOST','SMTP_PORT','SMTP_USERNAME','SMTP_PASSWORD','SMTP_FROM'}
values = {}
for line in path.read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        if key.strip() in allowed:
            values[key.strip()] = value.strip().strip('"').strip("'")
if not values.get('SMTP_PASSWORD'):
    raise SystemExit('Preencha SMTP_PASSWORD em .runtime/smtp.env antes de configurar o envio.')
for key, value in values.items():
    result = subprocess.run(['railway','variable','set',key,'--stdin','--skip-deploys'], input=value, text=True, capture_output=True, cwd=root)
    if result.returncode:
        raise SystemExit(f'Não foi possível configurar {key}.')
    print('Configurado:', key)
