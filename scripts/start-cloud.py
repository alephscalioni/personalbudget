"""Initialize persistent storage once, then serve the private app."""
import json
import os
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = Path(os.getenv('PERSONALBUDGET_DATA', '/data'))
seed = root / 'deployment' / 'seed'
for folder in ('reports', 'config'):
    target = data / folder
    target.mkdir(parents=True, exist_ok=True)
    if (seed / folder).exists():
        for file in (seed / folder).glob('*.json'):
            if not (target / file.name).exists():
                shutil.copy2(file, target / file.name)
os.environ.setdefault('PERSONALBUDGET_REPORTS', str(data / 'reports'))
os.environ.setdefault('PERSONALBUDGET_DATABASE', str(data / 'budget.sqlite3'))
os.environ.setdefault('PERSONALBUDGET_FINANCE_CONFIG', str(data / 'config'))
os.environ.setdefault('PERSONALBUDGET_AUTH_REQUIRED', '1')
# Rule-first classification; the authenticated Kaleu worker handles only pending cases.
os.environ.setdefault('PERSONALBUDGET_CLASSIFICATION_AI_ENABLED', '1')
sys.path.insert(0, str(root))
from backend import auth, store
if not auth.configured():
    raise SystemExit('Configure PERSONALBUDGET_PASSWORD_HASH and PERSONALBUDGET_SESSION_SECRET before deployment.')
store.initialize()
auth.seed_users()
marker = data / '.planning-initialized'
if not marker.exists() and (seed / 'planning.json').exists():
    planning = json.loads((seed / 'planning.json').read_text())
    for kind, key in [('budget','budget'), ('goal','goals'), ('transaction','transactions'), ('override','overrides')]:
        if store.all_of(kind):
            continue
        for item in planning.get(key, []):
            identifier = item.pop('id', None)
            store.save(kind, item, identifier or ('current' if kind == 'budget' else None))
    marker.touch()
# The legacy report contains private data and is generated only behind auth.
if list((data / 'reports').glob('consolidado-*.json')):
    from backend.app import sync_dashboard
    sync_dashboard()
os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '0.0.0.0', '--port', os.getenv('PORT', '8080')])
