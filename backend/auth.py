"""Two household accounts, forced initial password change and email recovery."""
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from . import mail, store

router = APIRouter()
COOKIE = 'pb_session'
TTL = 60 * 60 * 12
attempts = defaultdict(list)
lock = threading.Lock()
USERNAMES = ('biancascalioni', 'alephscalioni')


def required():
    return bool(os.getenv('RAILWAY_ENVIRONMENT_ID') or os.getenv('PERSONALBUDGET_AUTH_REQUIRED') == '1' or os.getenv('PERSONALBUDGET_PASSWORD_HASH'))


def configured():
    return bool(os.getenv('PERSONALBUDGET_SESSION_SECRET') and (os.getenv('PERSONALBUDGET_PASSWORD_HASH') or store.get('user', 'alephscalioni')))


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'scrypt${salt}${digest}'


def verify_password(password, encoded):
    try:
        algorithm, salt, digest = encoded.split('$')
        return algorithm == 'scrypt' and hmac.compare_digest(encoded, password_hash(password, salt))
    except (ValueError, TypeError):
        return False


def seed_users():
    """Never reset an existing account when a deployment restarts."""
    encoded = os.getenv('PERSONALBUDGET_PASSWORD_HASH')
    if not encoded:
        return
    for username in USERNAMES:
        email = os.getenv('PERSONALBUDGET_BIANCA_EMAIL' if username == 'biancascalioni' else 'PERSONALBUDGET_ALEPH_EMAIL', '').strip()
        body = {'id': username, 'username': username, 'email': email, 'password_hash': encoded, 'must_change_password': True, 'version': 1}
        with store.connection() as db:
            db.execute('INSERT OR IGNORE INTO documents VALUES (?,?,?)', ('user', username, json.dumps(body)))
            # Email provisioned later may fill an empty recovery address, never overwrite one.
            row = db.execute('SELECT body FROM documents WHERE kind=? AND id=?', ('user', username)).fetchone()
            current = json.loads(row['body'])
            if email and not current.get('email'):
                current['email'] = email
                db.execute('UPDATE documents SET body=? WHERE kind=? AND id=?', (json.dumps(current), 'user', username))


def sign(payload):
    return hmac.new(os.environ['PERSONALBUDGET_SESSION_SECRET'].encode(), payload.encode(), hashlib.sha256).hexdigest()


def current_user(request):
    if not required() or not configured():
        return None
    try:
        username, version, expires, nonce, signature = request.cookies.get(COOKIE, '').split('.')
        payload = f'{username}.{version}.{expires}.{nonce}'
        if not (time.time() < int(expires) <= time.time() + TTL + 10 and hmac.compare_digest(sign(payload), signature)):
            return None
        user = store.get('user', username)
        return user if user and user['version'] == int(version) else None
    except (ValueError, KeyError):
        return None


def authenticated(request):
    if not required():
        return True
    user = current_user(request)
    return bool(user and not user['must_change_password'])


def session_response(user):
    payload = f"{user['username']}.{user['version']}.{int(time.time()) + TTL}.{secrets.token_hex(16)}"
    response = JSONResponse({'authenticated': True, 'username': user['username'], 'must_change_password': user['must_change_password']})
    response.set_cookie(COOKIE, payload + '.' + sign(payload), max_age=TTL, httponly=True, secure=required(), samesite='strict', path='/')
    return response


def rate_limit(request, action, maximum):
    ip = request.client.host if request.client else 'unknown'
    key, now = (action, ip), time.time()
    with lock:
        # Bound memory for unique caller addresses.
        if len(attempts) > 5000:
            expired = [k for k,v in attempts.items() if not v or v[-1] < now - 900]
            for k in expired:
                attempts.pop(k, None)
        attempts[key] = [stamp for stamp in attempts[key] if stamp > now - 900]
        if len(attempts[key]) >= maximum:
            raise HTTPException(429, 'Muitas tentativas. Aguarde 15 minutos antes de tentar novamente.')
        attempts[key].append(now)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class ForgotPassword(BaseModel):
    username: str = Field(min_length=1, max_length=80)


class ResetPassword(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=12, max_length=256)


@router.get('/api/session')
def session(request: Request):
    if not required():
        return {'authenticated': True, 'required': False, 'configured': True, 'must_change_password': False}
    user = current_user(request)
    return {'authenticated': bool(user), 'required': True, 'configured': configured(),
            'username': user['username'] if user else None,
            'must_change_password': bool(user and user['must_change_password']),
            'recovery_available': mail.configured()}


@router.post('/api/session')
def login(body: Login, request: Request):
    if not required():
        return {'authenticated': True}
    if not configured():
        raise HTTPException(503, 'O acesso privado ainda está sendo configurado.')
    rate_limit(request, 'login', 15)
    seed_users()
    user = store.get('user', body.username.strip().lower())
    encoded = user['password_hash'] if user else os.getenv('PERSONALBUDGET_PASSWORD_HASH', '')
    valid = verify_password(body.password, encoded)
    if not user or not valid:
        raise HTTPException(401, 'Usuário ou senha incorretos.')
    return session_response(user)


@router.delete('/api/session')
def logout():
    response = JSONResponse({'authenticated': False})
    response.delete_cookie(COOKIE, path='/', secure=required(), httponly=True, samesite='strict')
    return response


def update_password(username, version, new_password):
    encoded = password_hash(new_password)
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT body FROM documents WHERE kind=? AND id=?', ('user', username)).fetchone()
        user = json.loads(row['body']) if row else None
        if not user or user['version'] != version:
            raise HTTPException(401, 'O acesso expirou. Entre novamente.')
        if verify_password(new_password, user['password_hash']):
            raise HTTPException(400, 'Escolha uma senha diferente da atual.')
        user.update(password_hash=encoded, must_change_password=False, version=version + 1)
        db.execute('UPDATE documents SET body=? WHERE kind=? AND id=?', (json.dumps(user), 'user', username))
    return user


@router.post('/api/password/change')
def change_password(body: ChangePassword, request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(401, 'Entre novamente para alterar a senha.')
    rate_limit(request, 'password-change', 10)
    if not verify_password(body.current_password, user['password_hash']):
        raise HTTPException(400, 'A senha atual não confere.')
    if verify_password(body.new_password, user['password_hash']):
        raise HTTPException(400, 'Escolha uma senha diferente da provisória ou atual.')
    return session_response(update_password(user['username'], user['version'], body.new_password))


def deliver_recovery(email, token):
    try:
        mail.send_reset(email, token)
    except Exception:
        logging.getLogger(__name__).warning('Não foi possível enviar um e-mail de recuperação. Confira a configuração SMTP.')


@router.post('/api/password/forgot', status_code=202)
def forgot_password(body: ForgotPassword, request: Request, background: BackgroundTasks):
    rate_limit(request, 'recovery', 5)
    if not mail.configured():
        raise HTTPException(503, 'A recuperação por e-mail ainda não foi configurada.')
    user = store.get('user', body.username.strip().lower())
    if user and user.get('email'):
        token = secrets.token_urlsafe(32)
        identifier = hashlib.sha256(token.encode()).hexdigest()
        store.save('reset', {'username': user['username'], 'version': user['version'], 'expires': int(time.time()) + 1200}, identifier)
        background.add_task(deliver_recovery, user['email'], token)
    return {'message': 'Se a conta tiver um e-mail cadastrado, você receberá um link para redefinir sua senha.'}


@router.post('/api/password/reset')
def reset_password(body: ResetPassword, request: Request):
    rate_limit(request, 'reset', 10)
    identifier = hashlib.sha256(body.token.encode()).hexdigest()
    reset = store.get('reset', identifier)
    if not reset or reset['expires'] <= time.time():
        raise HTTPException(400, 'Este link expirou ou já foi usado. Solicite outro.')
    # Versioned, transactional update makes concurrent reuse fail as well.
    user = update_password(reset['username'], reset['version'], body.new_password)
    store.remove('reset', identifier)
    return session_response(user)
