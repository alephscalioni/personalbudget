"""Adapt the existing finance pipeline without copying its business rules."""
import hashlib
from collections import Counter
import contextlib
import io
import json
import re
import sys
from functools import lru_cache

from .config import FINANCE, FINANCE_CONFIG, REPORTS
from . import store, positions

sys.path.insert(0, str(FINANCE))
from payload_consolidado import build
from gera_dashboard_consolidado import aplica_contrapartes, aplica_mascara, aplica_posicoes_manuais


def latest():
    return max(REPORTS.glob('consolidado-*.json'), default=None)


def salary_plan():
    path = FINANCE_CONFIG / 'premissas-fluxo.json'
    if not path.exists():
        path = FINANCE / 'premissas-fluxo.example.json'
    income = json.loads(path.read_text()).get('renda_mensal', {})
    return [{'person': 'aleph', 'name': 'Aleph', 'net': income.get('aleph_liquido', 0), 'gross': income.get('aleph_bruto'), 'regime': 'CLT'},
            {'person': 'bianca', 'name': 'Bianca', 'net': income.get('bia_liquido', 0), 'gross': income.get('bia_bruto_pj'), 'regime': 'PJ'}]


def default_budget():
    path = FINANCE_CONFIG / 'premissas-fluxo.json'
    if not path.exists():
        path = FINANCE / 'premissas-fluxo.example.json'
    p = json.loads(path.read_text())
    b, c = p['orcamento_mensal'], p['controle_mensal']
    return {'lines': b['linhas'], 'monthly_income': p['renda_mensal']['aleph_liquido'] + p['renda_mensal']['bia_liquido'],
            'monthly_saving': b['meta_poupanca'], 'benefits_spending': c.get('va_alicia', 0) + c.get('vr_aleph', 0)}


def matches_salary_rule(transaction, rule):
    if rule.get('person') not in ('aleph', 'bianca'):
        return False
    # External own-account credits require explicit confirmation of portability.
    if transaction.get('externa') and not rule.get('confirmed_portability'):
        return False
    root = rule.get('payer_root', '')
    if root:
        return (len(root) == 8 and root.isdigit()
                and re.sub(r'\D', '', transaction.get('desc', '')).startswith(root))
    # Never infer ownership from an amount, date, or a generic transfer method.
    if not rule.get('institution') or rule.get('institution') != transaction.get('instituicao'):
        return False
    if not rule.get('method') or rule['method'] != transaction.get('metodo'):
        return False
    description = rule.get('description')
    return (description == transaction.get('desc') if description
            else rule['method'] == 'Salário')


@lru_cache(maxsize=2)
def snapshot(path, fingerprints):
    return prepare(json.loads(path.read_text(encoding='utf-8')))


@lru_cache(maxsize=2)
def database_snapshot(body, fingerprints):
    return prepare(json.loads(body))


def prepare(raw):
    payload = build(raw)
    seen = Counter()
    for t in payload['lancamentos']:
        identity = [t.get(k) for k in ('instituicao', 'conta', 'conta_tipo', 'data', 'desc', 'valor', 'tipo', 'fatura')]
        digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:32]
        seen[digest] += 1
        t['id'] = f'bank-{digest}-{seen[digest]}'
    # Private payer rules identify existing credits without changing bank records.
    rules_path = FINANCE_CONFIG / 'salary-rules.json'
    rules = json.loads(rules_path.read_text()).get('rules', []) if rules_path.exists() else []
    for t in payload['lancamentos']:
        if t.get('conta_tipo') == 'CREDIT' or t.get('valor', 0) <= 0 or t.get('natureza') != 'entrada':
            continue
        for rule in rules:
            if matches_salary_rule(t, rule):
                t['salary_person'] = rule['person']
                t['is_salary'] = True
                break
    # Existing classification helpers can log personal transaction descriptions.
    with contextlib.redirect_stdout(io.StringIO()):
        aplica_contrapartes(payload)
        aplica_mascara(payload)
        aplica_posicoes_manuais(payload)
    return payload


def data():
    record = store.get('bank-snapshot', 'current')
    path = latest()
    if path is None and not record:
        raise FileNotFoundError('Nenhum consolidado disponível. Adicione um arquivo em data/reports.')
    deps = [*(FINANCE_CONFIG / n for n in ['contrapartes.json', 'mascara.json', 'posicoes-manuais.json', 'salary-rules.json'])]
    fingerprints = tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in deps)
    payload = database_snapshot(json.dumps(record['raw']), fingerprints) if record else snapshot(path, (path.stat().st_mtime_ns, *fingerprints))
    payload, declared = positions.apply(payload)
    overrides = store.all_of('override')
    assigned = {o['id'] for o in overrides if o.get('is_salary') and o.get('salary_person')}
    confirmed = {t['desc']:o['salary_person'] for t in payload['lancamentos'] for o in overrides if o['id']==t['id'] and o.get('is_salary') and o.get('salary_person')}
    rules_path = FINANCE_CONFIG / 'salary-rules.json'
    payer_rules = json.loads(rules_path.read_text()).get('rules', []) if rules_path.exists() else []
    for t in payload['lancamentos']:
        if t.get('valor',0)<=0 or t.get('conta_tipo')=='CREDIT' or t.get('salary_person') or t['id'] in assigned:
            continue
        if t.get('desc') in confirmed:
            t['salary_candidate'] = confirmed[t['desc']]
        for rule in payer_rules:
            root=rule.get('payer_root','')
            if len(root)==8 and re.sub(r'\D','',t.get('desc','')).startswith(root[:5]):
                t['salary_candidate']=rule['person']
    budgets = store.all_of('budget')
    return {'source': record['source'] if record else path.name, 'sync': store.get('setting', 'bank-sync') or {}, 'storage': 'postgresql' if store.DATABASE_URL else 'sqlite', 'finance': payload, 'budget': budgets[0] if budgets else default_budget(),
            'salary_plan': salary_plan(), 'cashflow_plans': store.all_of('cashflow'), 'positions': declared, 'goals': store.all_of('goal'), 'manual': store.all_of('transaction'), 'overrides': store.all_of('override')}


def classifier_module():
    source = (FINANCE / 'classificador.js').read_text(encoding='utf-8')
    return 'export function classifyPayload(D) {\n' + source + '''
const expenses = new Set(gastos), refunds = new Set(estornos);
return D.lancamentos.map((t, index) => {
  let kind = 'other';
  if (t.is_salary && t.salary_person && t.conta_tipo !== 'CREDIT' && t.valor > 0 && t.natureza === 'entrada') kind = 'income';
  else if (expenses.has(t)) kind = 'expense';
  else if (refunds.has(t)) kind = 'refund';
  else if (t.conta_tipo !== 'CREDIT' && !ehMovimentacaoPropria(t) && !ehEventoPatrimonial(t)) {
    if (t.natureza === 'consumo') kind = 'expense';
    if (t.natureza === 'entrada') kind = 'income';
  }
  return {...t, id: t.id || 'bank-' + index, description: limpaDesc(t.desc),
    group: t.is_salary && kind === 'income' ? 'Salário' : grupoDe(t), category: t.is_salary && kind === 'income' ? 'Salário' : catDe(t), kind, amount: Math.abs(t.valor), date: t.data.slice(0,10)};
});
}
'''
