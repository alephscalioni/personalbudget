"""Provision the existing user's Codex worker without exposing its credential."""
import json
from pathlib import Path
import secrets
import subprocess

root = Path(__file__).resolve().parents[1]
secret_file = root / '.runtime/kaleu-access.json'
if secret_file.exists():
    settings = json.loads(secret_file.read_text())
else:
    settings = {'url':'https://personalbudget-beta.vercel.app','token':secrets.token_urlsafe(48),
                'codex':'/home/aleph/.local/bin/codex','codex_home':'/home/aleph/codex-bots/runtime',
                'workspace':'/home/aleph/codex-bots/workspaces/kaleu-personalbudget'}
    secret_file.write_text(json.dumps(settings, indent=2))
    secret_file.chmod(0o600)
result = subprocess.run(['railway','variable','set','PERSONALBUDGET_KALEU_TOKEN','--stdin','--skip-deploys'],input=settings['token'],text=True,capture_output=True,cwd=root)
if result.returncode:
    raise SystemExit('Falha ao configurar token no Railway.')
subprocess.run(['ssh','aleph','umask 077; mkdir -p ~/.config/personalbudget; cat > ~/.config/personalbudget/kaleu.json'],input=json.dumps(settings),text=True,capture_output=True,check=True)
subprocess.run(['ssh','aleph','mkdir -p /home/aleph/codex-bots/workspaces/kaleu-personalbudget; cp /home/aleph/personalbudget/deployment/kaleu/AGENTS.md /home/aleph/codex-bots/workspaces/kaleu-personalbudget/AGENTS.md'],capture_output=True,check=True)
service = '''[Unit]
Description=Kaleu Personal Budget browser worker
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/aleph/personalbudget
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/home/aleph/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 /home/aleph/personalbudget/scripts/kaleu-worker.py
Restart=always
RestartSec=10
TimeoutStopSec=30
UMask=0077

[Install]
WantedBy=default.target
'''
subprocess.run(['ssh','aleph','mkdir -p ~/.config/systemd/user; cat > ~/.config/systemd/user/kaleu-personalbudget.service'],input=service,text=True,capture_output=True,check=True)
print('Credencial financeira e serviço do Kaleu configurados, sem iniciar mensagens.')
