"""Persisted, leased classification queue; independent of the chat queue."""
import hashlib
import hmac
import json
import secrets
import time
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field
from . import classification as engine, kaleu, store
from .models import Model

router = APIRouter()


def write(db, kind, body):
    db.execute('INSERT INTO documents VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body', (kind, body['id'], json.dumps(body, ensure_ascii=False)))


def enqueue(items):
    if not engine.ai_enabled():
        return
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        for item in items:
            body = dict(item, id=item['fingerprint'], status='queued', created=time.time(), attempts=0)
            db.execute('INSERT OR IGNORE INTO documents VALUES (?,?,?)', ('classification-task', body['id'], json.dumps(body, ensure_ascii=False)))


@router.get('/api/classification')
def status():
    from . import service
    data = service.data()
    tasks = store.all_of('classification-task')
    return {'catalog': engine.catalog(), 'rules': store.all_of('classification-rule'), 'ai_enabled': engine.ai_enabled(),
            'pending': [t for t in data['transactions'] if t['classification']['needs_review']],
            'queue': {state: sum(t['status'] == state for t in tasks) for state in ('queued', 'running', 'done', 'failed')}}


@router.put('/api/classification/rules/{identifier}')
def save_rule(identifier: str, body: engine.Rule):
    if len(identifier) > 100:
        raise HTTPException(422, 'Identificador muito longo.')
    return store.save('classification-rule', body.model_dump(mode='json'), identifier)


@router.delete('/api/classification/rules/{identifier}', status_code=204)
def delete_rule(identifier: str):
    if not store.remove('classification-rule', identifier):
        raise HTTPException(404, 'Regra não encontrada.')
    return Response(status_code=204)


@router.post('/api/classification/claim')
def claim(request: Request):
    if not kaleu.is_agent(request):
        raise HTTPException(403, 'Acesso exclusivo do worker.')
    if not engine.ai_enabled():
        return {'job': None}
    # Recompute active fingerprints: do not process old rules or user-adjusted rows.
    from . import service
    active = {t['classification'].get('fingerprint') for t in service.data()['transactions'] if t['classification']['source'] == 'pending'}
    now = time.time()
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        tasks = [json.loads(r['body']) for r in db.execute("SELECT body FROM documents WHERE kind='classification-task' ORDER BY rowid")]
        selected = []
        for task in tasks:
            if task['status'] == 'running' and task.get('started', 0) < now - 360:
                task['status'] = 'queued' if task['attempts'] < 3 else 'failed'
                write(db, 'classification-task', task)
            if task['id'] in active and task['status'] == 'queued' and len(selected) < 20:
                selected.append(task)
        if not selected:
            return {'job': None}
        lease = secrets.token_urlsafe(32)
        job = {'id': str(uuid4()), 'status': 'running', 'started': now, 'lease_hash': hashlib.sha256(lease.encode()).hexdigest(), 'items': selected}
        for task in selected:
            task.update(status='running', started=now, attempts=task['attempts'] + 1, job_id=job['id'])
            write(db, 'classification-task', task)
        write(db, 'classification-job', job)
        fields = ('transaction_id', 'kind', 'description', 'bank_category', 'method', 'allowed_categories', 'fingerprint')
        return {'job': {'id': job['id'], 'lease': lease, 'items': [{k: t.get(k) for k in fields} for t in selected]}}


class Decision(Model):
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    category: str | None = Field(default=None, max_length=80)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=500)


class Completion(Model):
    lease: str = Field(min_length=20, max_length=200)
    failed: bool = False
    decisions: list[Decision] = Field(default_factory=list, max_length=20)


@router.post('/api/classification/jobs/{identifier}/complete')
def complete(identifier: str, body: Completion, request: Request):
    if not kaleu.is_agent(request):
        raise HTTPException(403, 'Acesso exclusivo do worker.')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT body FROM documents WHERE kind='classification-job' AND id=?", (identifier,)).fetchone()
        job = json.loads(row['body']) if row else None
        if not job or job['status'] != 'running' or time.time() - job['started'] > 360 or not hmac.compare_digest(job.get('lease_hash', ''), hashlib.sha256(body.lease.encode()).hexdigest()):
            raise HTTPException(409, 'Execução expirada ou já concluída.')
        allowed = {item['fingerprint']: item['allowed_categories'] for item in job['items']}
        decisions = {d.fingerprint: d for d in body.decisions}
        if not body.failed and (len(decisions) != len(body.decisions) or set(decisions) != set(allowed) or any(d.category is not None and d.category not in allowed[d.fingerprint] for d in body.decisions)):
            raise HTTPException(422, 'A resposta deve conter exatamente os lançamentos e categorias permitidos.')
        for item in job['items']:
            task = json.loads(db.execute("SELECT body FROM documents WHERE kind='classification-task' AND id=?", (item['fingerprint'],)).fetchone()['body'])
            if task.get('job_id') != identifier:
                raise HTTPException(409, 'Lançamento atribuído a outra execução.')
            if not body.failed:
                result = decisions[item['fingerprint']].model_dump(mode='json')
                result.update(id=item['fingerprint'], transaction_id=item['transaction_id'], completed=time.time())
                store.audit(db, 'classification-result', result['id'], None, result)
                write(db, 'classification-result', result)
            task['status'] = ('queued' if task['attempts'] < 3 else 'failed') if body.failed else 'done'
            write(db, 'classification-task', task)
        job.update(status='failed' if body.failed else 'done', completed=time.time())
        job.pop('lease_hash', None)
        write(db, 'classification-job', job)
    return {'ok': True}
