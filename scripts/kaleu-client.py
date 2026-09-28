#!/usr/bin/env python3
"""Kaleu's narrow finance API client. JSON bodies arrive on stdin."""
import json
import os
from pathlib import Path
import sys
import urllib.request
import urllib.error


def config():
    path = Path(os.getenv('PERSONALBUDGET_AGENT_CONFIG', Path.home() / '.config/personalbudget/kaleu.json'))
    return json.loads(path.read_text())


def request(method, path, body=None):
    settings = config()
    if not path.startswith('/api/'):
        raise ValueError('Use um caminho /api/.')
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(settings['url'].rstrip('/') + path, data=data, method=method,
        headers={'Authorization': 'Bearer ' + settings['token'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


if __name__ == '__main__':
    method, path = sys.argv[1:3]
    body = json.load(sys.stdin) if method in ('POST','PUT','PATCH') else None
    try:
        print(json.dumps(request(method, path, body), ensure_ascii=False))
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read()).get('detail', 'Falha na API')
        except Exception:
            detail = 'Falha na API'
        print(json.dumps({'error': detail, 'status': error.code}, ensure_ascii=False))
        raise SystemExit(1)
