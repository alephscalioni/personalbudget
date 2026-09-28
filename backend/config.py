"""Paths shared by the API and the offline report generator."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
FINANCE = ROOT / 'finance' / 'pluggy'
REPORTS = Path(os.getenv('PERSONALBUDGET_REPORTS', ROOT / 'data' / 'reports'))
DATABASE = Path(os.getenv('PERSONALBUDGET_DATABASE', ROOT / 'data' / 'budget.sqlite3'))
GENERATOR = Path(os.getenv('PERSONALBUDGET_GENERATOR', FINANCE / 'gera_fluxo_mensal.py'))

FINANCE_CONFIG = Path(os.getenv('PERSONALBUDGET_FINANCE_CONFIG', FINANCE))
