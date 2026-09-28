"""Check the Git index and public build without exposing credential values."""
import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(['git','diff','--cached','--name-only'],cwd=root,text=True).splitlines()
forbidden = re.compile(r'(^|/)(data|\.runtime|\.venv|seed)/|(^|/)\.env($|\.)|dashboard\.html$|\.(sqlite3?|db)$')
problems = [name for name in files if forbidden.search(name)]
secrets = []
for path in [root/'finance/pluggy/.env',root/'.env.local']:
    if not path.exists():
        continue
    for line in path.read_text().splitlines():
        if '=' not in line or line.lstrip().startswith('#'):
            continue
        key,value=line.split('=',1)
        value=value.strip().strip('"').strip("'")
        if len(value)>=12 and re.search('SECRET|TOKEN|PASSWORD',key):
            secrets.append(value)
access=root/'.runtime/cloud-access.json'
if access.exists():
    secrets.extend(str(v) for v in json.loads(access.read_text()).values())
for name in files:
    body=subprocess.check_output(['git','show',':'+name],cwd=root).decode(errors='replace')
    if any(secret in body for secret in secrets):
        problems.append(name+' (credential content)')
if problems:
    raise SystemExit('Publicação bloqueada: '+', '.join(problems))
public_files=[str(p.relative_to(root/'dist')) for p in (root/'dist').rglob('*') if p.is_file()]
assert all(name=='index.html' or name=='app/shell.css' or name.startswith('app/js/') for name in public_files)
print(f'Verificados {len(files)} arquivos no Git e {len(public_files)} arquivos públicos: sem extratos ou credenciais.')
