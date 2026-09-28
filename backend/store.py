"""Local planning data. Bank snapshots remain immutable."""
import json
import sqlite3
from contextlib import contextmanager
from uuid import uuid4

from .config import DATABASE


@contextmanager
def connection():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute('CREATE TABLE IF NOT EXISTS documents (kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(kind,id))')
        yield db
        db.commit()
    finally:
        db.close()


def all_of(kind):
    with connection() as db:
        return [json.loads(row['body']) for row in db.execute('SELECT body FROM documents WHERE kind=? ORDER BY rowid', (kind,))]


def save(kind, body, identifier=None):
    body = dict(body, id=identifier or str(uuid4()))
    with connection() as db:
        db.execute('INSERT INTO documents VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body', (kind, body['id'], json.dumps(body, ensure_ascii=False)))
    return body


def remove(kind, identifier):
    with connection() as db:
        return db.execute('DELETE FROM documents WHERE kind=? AND id=?', (kind, identifier)).rowcount > 0


def get(kind, identifier):
    with connection() as db:
        row = db.execute('SELECT body FROM documents WHERE kind=? AND id=?', (kind, identifier)).fetchone()
        return json.loads(row['body']) if row else None
