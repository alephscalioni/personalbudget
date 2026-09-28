"""Create a minimal Railway upload without credentials or development files."""
from pathlib import Path
import shutil
import tempfile

root = Path(__file__).resolve().parents[1]
target = Path(tempfile.mkdtemp(prefix='personalbudget-deploy-', dir='/private/tmp'))
for directory in ['backend', 'frontend', 'finance/pluggy', 'scripts', 'deployment']:
    shutil.copytree(root / directory, target / directory, copy_function=shutil.copyfile, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.env', '.env.*', 'dashboard.html'))
for name in ['Dockerfile', '.dockerignore', 'railway.json']:
    shutil.copyfile(root/name, target/name)
for name in ['salary-rules.json', 'premissas-fluxo.json', 'contrapartes.json', 'mascara.json', 'posicoes-manuais.json']:
    path = target/'finance/pluggy'/name
    if path.exists():
        path.unlink()
(root / '.runtime' / 'deployment-path.txt').write_text(str(target))
assert not list(target.rglob('.env'))
assert not list(target.rglob('cloud-access.json'))
print(target)
