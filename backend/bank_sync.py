"""Hourly bank ingestion on the cloud server; failed imports preserve good data."""
import contextlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from . import service, store
from .config import REPORTS


def enabled():
    return os.getenv('PERSONALBUDGET_SYNC_ENABLED') == '1' and bool(os.getenv('PLUGGY_CLIENT_SECRET'))


def seed():
    try:
        record = service.current_snapshot()
    except FileNotFoundError:
        return
    if 'imported_at' not in record:
        store.save('bank-snapshot', dict(record, imported_at=time.time()), 'current')


def validate(raw, previous=None):
    institutions = raw.get('instituicoes', [])
    if not institutions or not any(i.get('contas') for i in institutions):
        raise ValueError('Empty bank response')
    if any(c.get('erro_extrato') for i in institutions for c in i.get('contas', [])):
        raise ValueError('Incomplete bank response')
    if previous:
        old = {c['id'] for i in previous['instituicoes'] for c in i.get('contas', []) if c.get('id')}
        new = {c['id'] for i in institutions for c in i.get('contas', []) if c.get('id')}
        if not old.issubset(new):
            raise ValueError('Missing connected accounts')
    service.build(raw)  # Validate financial structure before publishing.


def preserve_history(raw, previous):
    """Retain records outside the provider window, not duplicate current ones."""
    if not previous:
        return raw
    old = {c.get('id'):c for i in previous['instituicoes'] for c in i.get('contas', []) if c.get('id')}
    cutoff = raw['janela'][0]
    for institution in raw['instituicoes']:
        for account in institution.get('contas', []):
            retained = [t for t in old.get(account.get('id'),{}).get('lancamentos',[]) if t['data'][:10] < cutoff]
            account['lancamentos'].extend(retained)
            if account.get('tipo') != 'CREDIT' and 'saldo_inicial' in account:
                account['saldo_inicial'] = round(account['saldo_inicial'] - sum(t['valor'] for t in retained), 2)
            for bill, totals in old.get(account.get('id'),{}).get('faturas',{}).items():
                if bill[:10] < cutoff:
                    account.setdefault('faturas',{}).setdefault(bill,totals)
    raw['janela'][0] = min(cutoff, previous['janela'][0])
    raw['caixa_inicial'] = round(sum(c.get('saldo_inicial',0) for i in raw['instituicoes'] for c in i.get('contas',[]) if c.get('tipo')!='CREDIT'),2)
    return raw


def run_once():
    status = store.get('setting', 'bank-sync') or {}
    attempted = time.time()
    status.update(status='running', last_attempt=attempted, interval_seconds=3600)
    store.save('setting', status, 'bank-sync')
    try:
        # The collector uses the existing Pluggy connection; no bank transfers.
        from coleta_consolidada import coletar
        raw = coletar(365, 'api', strict=True)
        previous = store.get('bank-snapshot', 'current')
        validate(raw, previous['raw'] if previous else None)
        raw = preserve_history(raw, previous['raw'] if previous else None)
        raw['gerado_em'] = datetime.now(timezone.utc).isoformat()
        name = 'consolidado-' + raw['gerado_em'][:10] + '.json'
        REPORTS.mkdir(parents=True, exist_ok=True)
        staging = REPORTS / (name + '.tmp')
        staging.write_text(json.dumps(raw, ensure_ascii=False))
        staging.replace(REPORTS / name)
        store.save('bank-snapshot', {'source':name,'raw':raw,'imported_at':time.time()}, 'current')
        status.update(status='ok', last_success=time.time(), error=None, next_run=attempted+3600)
        try:
            from .app import sync_dashboard
            sync_dashboard()
            status['report_error'] = None
        except Exception:
            status['report_error'] = 'Os dados foram atualizados, mas o relatório detalhado não pôde ser regenerado.'
    except Exception:
        status.update(status='error', error='Não foi possível concluir a coleta. Os últimos dados válidos foram preservados.', next_run=attempted+3600)
    current = store.get('setting', 'bank-sync') or {}
    status['requested_at'] = max(status.get('requested_at',0), current.get('requested_at',0))
    store.save('setting', status, 'bank-sync')
    return status


def loop(stop):
    while not stop.is_set():
        try:
            status = store.get('setting', 'bank-sync') or {}
            last = status.get('last_attempt', 0)
            if time.time()-last >= 3600 or status.get('requested_at',0) > last:
                # Dedicated lock prevents overlapping syncs across app replicas.
                if store.DATABASE_URL:
                    with store.connection() as db:
                        if db.execute('SELECT pg_try_advisory_xact_lock(748392) AS acquired').fetchone()['acquired']:
                            run_once()
                else:
                    run_once()
        except Exception:
            pass  # Never terminate scheduling on a temporary database outage.
        stop.wait(15)


def start():
    stop = threading.Event()
    worker = None
    if enabled():
        worker = threading.Thread(target=loop, args=(stop,), daemon=True, name='bank-hourly-sync')
        worker.start()
    return worker, stop
