"""Authenticated work queue for the user's existing Kaleu Codex worker."""
import hashlib
import hmac
import json
import os
import secrets
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from . import auth, store

router = APIRouter()
FINANCE_PATHS = ('/api/data', '/api/budget', '/api/cashflow', '/api/goals', '/api/transactions', '/api/positions', '/api/backup', '/api/audit')


def is_agent(request):
    key = os.getenv('PERSONALBUDGET_KALEU_TOKEN', '')
    value = request.headers.get('authorization', '')
    return bool(key and value.startswith('Bearer ') and hmac.compare_digest(value[7:], key))


def allowed(request):
    path = request.url.path.rstrip('/')
    return is_agent(request) and (any(path == p or path.startswith(p + '/') for p in FINANCE_PATHS) or path == '/api/kaleu/claim' or path.startswith('/api/kaleu/jobs/'))


def user_id(request):
    user = auth.current_user(request)
    if user and not user['must_change_password']:
        return user['username']
    if not auth.required():
        return 'local'
    raise HTTPException(401, 'Entre para conversar com o Kaleu.')


def public(job):
    return {k: job.get(k) for k in ('id','message','reply','status','created','completed')}


class Message(BaseModel):
    message: str = Field(min_length=1, max_length=6000)


class Completion(BaseModel):
    lease: str = Field(min_length=20, max_length=200)
    reply: str = Field(min_length=1, max_length=40000)
    failed: bool = False


@router.get('/api/kaleu/messages')
def messages(request: Request):
    username = user_id(request)
    heartbeat = store.get('setting', 'kaleu-worker') or {}
    return {'available': time.time() - heartbeat.get('seen', 0) < 90 or any(j['status'] == 'running' and time.time() - j.get('started',0) < 1900 for j in store.all_of('kaleu-job')),
            'messages': [public(j) for j in store.all_of('kaleu-job') if j['username'] == username][-40:]}


@router.post('/api/kaleu/messages', status_code=202)
def enqueue(body: Message, request: Request):
    username = user_id(request)
    text = body.message.strip()
    if not text:
        raise HTTPException(422, 'Escreva uma mensagem.')
    auth.rate_limit(request, 'kaleu-chat', 20)
    if not os.getenv('PERSONALBUDGET_KALEU_TOKEN'):
        raise HTTPException(503, 'O Kaleu ainda não está conectado.')
    if sum(j['username'] == username and j['status'] in ('queued','running') for j in store.all_of('kaleu-job')) >= 3:
        raise HTTPException(429, 'Aguarde o Kaleu responder às mensagens anteriores.')
    return public(store.save('kaleu-job', {'username': username, 'message': text, 'reply': '', 'status': 'queued', 'created': time.time()}))


@router.post('/api/kaleu/claim')
def claim(request: Request):
    if not is_agent(request):
        raise HTTPException(403, 'Acesso exclusivo do Kaleu.')
    store.save('setting', {'seen': time.time()}, 'kaleu-worker')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute("SELECT body FROM documents WHERE kind='kaleu-job' ORDER BY rowid").fetchall()
        jobs = [json.loads(row['body']) for row in rows]
        for job in jobs:
            if job['status'] == 'running' and job.get('started', 0) < time.time() - 1900:
                job.update(status='interrupted', reply='A conexão foi interrompida. Confira o histórico de alterações antes de reenviar o pedido.')
                db.execute("UPDATE documents SET body=? WHERE kind='kaleu-job' AND id=?", (json.dumps(job), job['id']))
        job = next((j for j in jobs if j['status'] == 'queued'), None)
        if not job:
            return {'job': None}
        lease = secrets.token_urlsafe(32)
        job.update(status='running', started=time.time(), lease_hash=hashlib.sha256(lease.encode()).hexdigest())
        db.execute("UPDATE documents SET body=? WHERE kind='kaleu-job' AND id=?", (json.dumps(job), job['id']))
        history = [public(j) for j in jobs if j['username'] == job['username'] and j['status'] == 'done'][-8:]
        return {'job': dict(public(job), username=job['username'], lease=lease, history=history)}


@router.post('/api/kaleu/jobs/{identifier}/complete')
def complete(identifier: str, body: Completion, request: Request):
    if not is_agent(request):
        raise HTTPException(403, 'Acesso exclusivo do Kaleu.')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT body FROM documents WHERE kind='kaleu-job' AND id=?", (identifier,)).fetchone()
        job = json.loads(row['body']) if row else None
        digest = hashlib.sha256(body.lease.encode()).hexdigest()
        if not job or job['status'] != 'running' or not hmac.compare_digest(job.get('lease_hash',''), digest):
            raise HTTPException(409, 'Execução expirada ou já concluída.')
        job.update(status='failed' if body.failed else 'done', reply=body.reply, completed=time.time())
        job.pop('lease_hash', None)
        db.execute("UPDATE documents SET body=? WHERE kind='kaleu-job' AND id=?", (json.dumps(job), identifier))
    return {'ok': True}
