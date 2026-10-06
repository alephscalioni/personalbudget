from __future__ import annotations

import os
import posixpath
import sqlite3
import psycopg
import subprocess
import sys
import threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from . import bank_sync
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, FRONTEND, GENERATOR
from .models import Budget, Goal, Transaction, TransactionOverride, Position, CashflowPlan
from . import auth, service, store, kaleu

@asynccontextmanager
async def lifespan(app):
    store.initialize()
    bank_sync.seed()
    worker, stop = bank_sync.start()
    yield
    stop.set()


app = FastAPI(title='Personal Budget', version='3.0.0', lifespan=lifespan)
app.include_router(auth.router)
app.include_router(kaleu.router)
refresh_lock = threading.Lock()


@app.exception_handler(psycopg.Error)
@app.exception_handler(sqlite3.Error)
async def database_error(request: Request, exc: sqlite3.Error):
    return JSONResponse({'detail': 'O banco de dados está temporariamente indisponível. Tente novamente em instantes.'}, status_code=503)


@app.middleware('http')
async def local_privacy(request: Request, call_next):
    # Mutations are only accepted from this app, including on localhost.
    origin = request.headers.get('origin')
    permitted_origins = {str(request.base_url).rstrip('/'), *os.getenv('PERSONALBUDGET_PUBLIC_ORIGINS', '').split(',')}
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in permitted_origins:
        return JSONResponse({'detail': 'Origem não autorizada.'}, status_code=403)
    host = urlsplit(str(request.url)).hostname
    allowed = {'localhost', '127.0.0.1', '::1', 'testserver'} | set(os.getenv('PERSONALBUDGET_ALLOWED_HOSTS', '').split(','))
    allowed.add(os.getenv('RAILWAY_PUBLIC_DOMAIN', ''))
    if host not in allowed and request.url.path != '/api/health':
        return JSONResponse({'detail': 'Host não autorizado.'}, status_code=400)
    path = posixpath.normpath(request.url.path)
    protected = (path.startswith('/api/') and path not in ('/api/health', '/api/session', '/api/password/change', '/api/password/forgot', '/api/password/reset')) or path in ('/app/dashboard.html', '/app/js/classifier.js')
    if protected and not (auth.authenticated(request) or kaleu.allowed(request)):
        if path == '/app/dashboard.html':
            response = RedirectResponse('/')
        else:
            response = JSONResponse({'detail': 'Entre para acessar suas finanças.'}, status_code=401)
    else:
        user = auth.current_user(request)
        actor = 'kaleu' if kaleu.is_agent(request) else user['username'] if user else 'local'
        context = store.actor.set(actor)
        try:
            response = await call_next(request)
        finally:
            store.actor.reset(context)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return response


def sync_dashboard():
    raw = service.latest()
    if not raw or not GENERATOR.exists():
        raise RuntimeError('Consolidado ou gerador indisponível.')
    generated = ROOT / '.runtime' / 'dashboard.html'
    generated.parent.mkdir(exist_ok=True)
    with refresh_lock:
        subprocess.run([sys.executable, str(GENERATOR), '--raw', str(raw), '--out', str(generated)], check=True, capture_output=True, text=True, timeout=120)
        size = generated.stat().st_size
        generated.replace(FRONTEND / 'dashboard.html')
    return {'source': raw.name, 'updated_at': datetime.now(timezone.utc).isoformat(), 'bytes': size}


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/status')
def status():
    raw = service.latest()
    return {'ready': raw is not None, 'source': raw.name if raw else None, 'mode': 'local'}


@app.get('/api/data')
def data():
    try:
        return service.data()
    except FileNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, detail='O consolidado possui dados inválidos. Confira o arquivo de origem.')


@app.post('/api/refresh', status_code=202)
def refresh():
    if not bank_sync.enabled():
        raise HTTPException(503, 'A sincronização bancária ainda não está configurada.')
    current = store.get('setting', 'bank-sync') or {}
    current['requested_at'] = __import__('time').time()
    store.save('setting', current, 'bank-sync')
    return {'ok': True, 'status': 'queued'}


@app.put('/api/budget')
def budget(body: Budget):
    return store.save('budget', body.model_dump(mode='json'), 'current')


@app.post('/api/goals', status_code=201)
def create_goal(body: Goal):
    return store.save('goal', body.model_dump(mode='json'))


@app.put('/api/goals/{identifier}')
def update_goal(identifier: str, body: Goal):
    if not any(g['id'] == identifier for g in store.all_of('goal')):
        raise HTTPException(404, 'Meta não encontrada.')
    return store.save('goal', body.model_dump(mode='json'), identifier)


@app.delete('/api/goals/{identifier}', status_code=204)
def delete_goal(identifier: str):
    if not store.remove('goal', identifier):
        raise HTTPException(404, 'Meta não encontrada.')
    return Response(status_code=204)


@app.post('/api/transactions', status_code=201)
def create_transaction(body: Transaction):
    return store.save('transaction', body.model_dump(mode='json'))


@app.delete('/api/transactions/{identifier}', status_code=204)
def delete_transaction(identifier: str):
    if not store.remove('transaction', identifier):
        raise HTTPException(404, 'Lançamento não encontrado.')
    return Response(status_code=204)


@app.put('/api/transactions/{identifier}/classification')
def classify_transaction(identifier: str, body: TransactionOverride):
    if not any(t['id'] == identifier for t in service.data()['finance']['lancamentos']):
        raise HTTPException(404, 'Lançamento bancário não encontrado.')
    return store.save('override', body.model_dump(mode='json'), identifier)


@app.delete('/api/transactions/{identifier}/classification', status_code=204)
def reset_classification(identifier: str):
    store.remove('override', identifier)
    return Response(status_code=204)


@app.post('/api/positions', status_code=201)
def create_position(body: Position):
    service.data()  # Initialize inherited declarations before the first edit.
    return store.save('position', body.model_dump(mode='json'))


@app.put('/api/positions/{identifier}')
def update_position(identifier: str, body: Position):
    if not store.get('position', identifier):
        raise HTTPException(404, 'Posição não encontrada.')
    return store.save('position', body.model_dump(mode='json'), identifier)


@app.delete('/api/positions/{identifier}', status_code=204)
def delete_position(identifier: str):
    if not store.remove('position', identifier):
        raise HTTPException(404, 'Posição não encontrada.')
    return Response(status_code=204)


@app.get('/api/audit')
def audit_history():
    return {'entries': store.all_of('audit')[-100:][::-1]}


@app.get('/api/backup')
def backup():
    return JSONResponse({'version': 1, 'exported_at': datetime.now(timezone.utc).isoformat(),
        'budget': store.all_of('budget') or [service.default_budget()],
        'cashflow_plans': store.all_of('cashflow'), 'positions': store.all_of('position'), 'goals': store.all_of('goal'), 'transactions': store.all_of('transaction'), 'overrides': store.all_of('override')},
        headers={'Content-Disposition': 'attachment; filename="personal-budget-backup.json"'})


@app.get('/app/js/classifier.js')
def classifier():
    return Response(service.classifier_module(), media_type='text/javascript')


@app.get('/')
def home():
    return FileResponse(FRONTEND / 'index.html')


app.mount('/app', StaticFiles(directory=FRONTEND, html=True), name='frontend')


@app.put('/api/cashflow')
def save_cashflow(body: CashflowPlan):
    return store.save('cashflow', body.model_dump(mode='json'), body.month)
