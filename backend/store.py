"""Local planning data. Bank snapshots remain immutable."""
import json
import os
import re
import sqlite3
import time
from contextvars import ContextVar
from contextlib import contextmanager
from uuid import uuid4

from .config import DATABASE

DATABASE_URL = os.getenv("DATABASE_URL", "")

actor = ContextVar('finance_actor', default='local')
FINANCE_KINDS = {'budget','goal','transaction','override','position','cashflow','classification-rule','classification-result'}


def audit(db, kind, identifier, before, after):
    if kind not in FINANCE_KINDS:
        return
    entry = {'id': str(uuid4()), 'kind': kind, 'record_id': identifier, 'actor': actor.get(), 'at': time.time(), 'before': before, 'after': after}
    db.execute('INSERT INTO documents VALUES (?,?,?)', ('audit', entry['id'], json.dumps(entry, ensure_ascii=False)))



class PostgresConnection:
    """Translate the small legacy SQL surface; values always remain parameters."""
    def __init__(self, db):
        self.db = db

    def execute(self, sql, params=()):
        if sql == 'BEGIN IMMEDIATE':
            return self.db.execute('SELECT pg_advisory_xact_lock(748391)')
        ignore = 'INSERT OR IGNORE' in sql
        sql = sql.replace('INSERT OR IGNORE', 'INSERT')
        sql = sql.replace('INTO documents VALUES', 'INTO documents (kind,id,body) VALUES')
        sql = sql.replace('VALUES (?,?,?)', 'VALUES (?, ?, ?::jsonb)')
        sql = sql.replace('SET body=?', 'SET body=?::jsonb')
        sql = sql.replace('ORDER BY rowid', 'ORDER BY seq').replace('?', '%s')
        if ignore:
            sql += ' ON CONFLICT(kind,id) DO NOTHING'
        return self.db.execute(sql, params)


def postgres_rows(cursor):
    names = [column.name for column in (cursor.description or [])]
    def row(values):
        return {name: json.dumps(value, ensure_ascii=False) if name == 'body' and not isinstance(value, str) else value
                for name, value in zip(names, values)}
    return row


@contextmanager
def connection():
    if DATABASE_URL:
        import psycopg
        with psycopg.connect(DATABASE_URL, row_factory=postgres_rows, connect_timeout=10) as db:
            yield PostgresConnection(db)
        return
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute('CREATE TABLE IF NOT EXISTS documents (kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(kind,id))')
        yield db
        db.commit()
    finally:
        db.close()


def initialize():
    """Atomic, restart-safe migration. SQLite is retained as a recovery copy."""
    if not DATABASE_URL:
        return
    import psycopg
    with psycopg.connect(DATABASE_URL, connect_timeout=10) as db:
        db.execute('SELECT pg_advisory_xact_lock(748391)')
        db.execute('CREATE TABLE IF NOT EXISTS documents (seq BIGSERIAL UNIQUE, kind TEXT NOT NULL, id TEXT NOT NULL, body JSONB NOT NULL, PRIMARY KEY(kind,id))')
        done = db.execute("SELECT 1 FROM documents WHERE kind='setting' AND id='postgres-migrated'").fetchone()
        if not done:
            count = 0
            if DATABASE.exists():
                backup = DATABASE.with_name('budget.before-postgres.sqlite3')
                with sqlite3.connect(DATABASE) as source, sqlite3.connect(backup) as dest:
                    source.backup(dest)
                    for kind, identifier, body in source.execute('SELECT kind,id,body FROM documents ORDER BY rowid'):
                        db.execute('INSERT INTO documents(kind,id,body) VALUES (%s,%s,%s::jsonb) ON CONFLICT(kind,id) DO NOTHING', (kind, identifier, body))
                        count += 1
            db.execute("INSERT INTO documents(kind,id,body) VALUES ('setting','postgres-migrated',%s::jsonb)", (json.dumps({'records':count,'at':time.time()}),))


def all_of(kind):
    with connection() as db:
        return [json.loads(row['body']) for row in db.execute('SELECT body FROM documents WHERE kind=? ORDER BY rowid', (kind,))]


def save(kind, body, identifier=None):
    body = dict(body, id=identifier or str(uuid4()))
    with connection() as db:
        previous = db.execute('SELECT body FROM documents WHERE kind=? AND id=?', (kind, body['id'])).fetchone()
        audit(db, kind, body['id'], json.loads(previous['body']) if previous else None, body)
        db.execute('INSERT INTO documents VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body', (kind, body['id'], json.dumps(body, ensure_ascii=False)))
    return body


def remove(kind, identifier):
    with connection() as db:
        previous = db.execute('SELECT body FROM documents WHERE kind=? AND id=?', (kind, identifier)).fetchone()
        if previous:
            audit(db, kind, identifier, json.loads(previous['body']), None)
        return db.execute('DELETE FROM documents WHERE kind=? AND id=?', (kind, identifier)).rowcount > 0


def get(kind, identifier):
    with connection() as db:
        row = db.execute('SELECT body FROM documents WHERE kind=? AND id=?', (kind, identifier)).fetchone()
        return json.loads(row['body']) if row else None


def migrate_override(old_id, new_id):
    """Move a legacy adjustment once, without replacing a newer adjustment."""
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM documents WHERE kind=? AND id=?', ('override', new_id)).fetchone():
            return False
        row = db.execute('SELECT body FROM documents WHERE kind=? AND id=?', ('override', old_id)).fetchone()
        if not row:
            return False
        before = json.loads(row['body'])
        after = dict(before, id=new_id)
        db.execute('INSERT INTO documents VALUES (?,?,?)', ('override', new_id, json.dumps(after, ensure_ascii=False)))
        db.execute('DELETE FROM documents WHERE kind=? AND id=?', ('override', old_id))
        audit(db, 'override', old_id, before, None)
        audit(db, 'override', new_id, None, after)
    return True
