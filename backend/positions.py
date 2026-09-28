"""Editable declared balances, kept separate from bank statements."""
import copy
import hashlib
import json
from . import store


def apply(payload):
    payload = copy.deepcopy(payload)
    originals = [v for v in payload['investimentos'] if v.get('manual')]
    with store.connection() as db:
        if not db.execute("SELECT 1 FROM documents WHERE kind='setting' AND id='positions-initialized'").fetchone():
            for index, v in enumerate(originals):
                identifier = hashlib.sha256(f"{v.get('instituicao')}:{v.get('nome')}:{index}".encode()).hexdigest()[:24]
                body = dict(id=identifier, name=v['nome'], institution=v['instituicao'], balance=v['saldo'], reference=v.get('referencia') or payload['gerado_em'][:10], asset_class=v.get('subtipo') or 'Declarado')
                db.execute('INSERT OR IGNORE INTO documents VALUES (?,?,?)', ('position', identifier, json.dumps(body)))
            db.execute('INSERT INTO documents VALUES (?,?,?)', ('setting','positions-initialized','{}'))
    entries = store.all_of('position')
    old_total = sum(v['saldo'] for v in originals)
    new_total = sum(v['balance'] for v in entries)
    payload['investimentos'] = [v for v in payload['investimentos'] if not v.get('manual')]
    for inst in payload['instituicoes']:
        delta = sum(v['balance'] for v in entries if v['institution'] == inst['nome']) - sum(v['saldo'] for v in originals if v['instituicao'] == inst['nome'])
        inst['investimentos'] = round(inst['investimentos'] + delta, 2)
        inst['liquido'] = round(inst['liquido'] + delta, 2)
    known = {i['nome'] for i in payload['instituicoes']}
    for v in entries:
        if v['institution'] not in known:
            total = sum(x['balance'] for x in entries if x['institution'] == v['institution'])
            payload['instituicoes'].append(dict(nome=v['institution'], caixa=0, divida=0, investimentos=total, liquido=total, status='DECLARADO', zeradas=0))
            known.add(v['institution'])
        payload['investimentos'].append(dict(id=v['id'], nome=v['name'], instituicao=v['institution'], saldo=v['balance'], referencia=v['reference'], subtipo=v['asset_class'], tipo='Declarado', manual=True))
    for key in ('investimentos','liquido'):
        payload['resumo'][key] = round(payload['resumo'][key] - old_total + new_total, 2)
    payload['manual_total'] = round(new_total, 2)
    return payload, entries
