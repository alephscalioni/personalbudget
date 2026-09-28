"""Adapt the existing finance pipeline without copying its business rules."""
import hashlib
from collections import Counter
import contextlib
import io
import json
import sys
from functools import lru_cache

from .config import FINANCE, FINANCE_CONFIG, REPORTS
from . import store

sys.path.insert(0, str(FINANCE))
from payload_consolidado import build
from gera_dashboard_consolidado import aplica_contrapartes, aplica_mascara, aplica_posicoes_manuais


def latest():
    return max(REPORTS.glob('consolidado-*.json'), default=None)


def default_budget():
    path = FINANCE_CONFIG / 'premissas-fluxo.json'
    if not path.exists():
        path = FINANCE / 'premissas-fluxo.example.json'
    p = json.loads(path.read_text())
    b, c = p['orcamento_mensal'], p['controle_mensal']
    return {'lines': b['linhas'], 'monthly_income': p['renda_mensal']['aleph_liquido'] + p['renda_mensal']['bia_liquido'],
            'monthly_saving': b['meta_poupanca'], 'benefits_spending': c.get('va_alicia', 0) + c.get('vr_aleph', 0)}


@lru_cache(maxsize=2)
def snapshot(path, fingerprints):
    payload = build(json.loads(path.read_text(encoding='utf-8')))
    seen = Counter()
    for t in payload['lancamentos']:
        identity = [t.get(k) for k in ('instituicao', 'conta', 'conta_tipo', 'data', 'desc', 'valor', 'tipo', 'fatura')]
        digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:32]
        seen[digest] += 1
        t['id'] = f'bank-{digest}-{seen[digest]}'
    # Existing classification helpers can log personal transaction descriptions.
    with contextlib.redirect_stdout(io.StringIO()):
        aplica_contrapartes(payload)
        aplica_mascara(payload)
        aplica_posicoes_manuais(payload)
    return payload


def data():
    path = latest()
    if path is None:
        raise FileNotFoundError('Nenhum consolidado disponível. Adicione um arquivo em data/reports.')
    deps = [path, *(FINANCE_CONFIG / n for n in ['contrapartes.json', 'mascara.json', 'posicoes-manuais.json'])]
    payload = snapshot(path, tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in deps))
    budgets = store.all_of('budget')
    return {'source': path.name, 'finance': payload, 'budget': budgets[0] if budgets else default_budget(),
            'goals': store.all_of('goal'), 'manual': store.all_of('transaction'), 'overrides': store.all_of('override')}


def classifier_module():
    source = (FINANCE / 'classificador.js').read_text(encoding='utf-8')
    return 'export function classifyPayload(D) {\n' + source + '''
const expenses = new Set(gastos), refunds = new Set(estornos);
return D.lancamentos.map((t, index) => {
  let kind = 'other';
  if (expenses.has(t)) kind = 'expense';
  else if (refunds.has(t)) kind = 'refund';
  else if (t.conta_tipo !== 'CREDIT' && !ehMovimentacaoPropria(t) && !ehEventoPatrimonial(t)) {
    if (t.natureza === 'consumo') kind = 'expense';
    if (t.natureza === 'entrada') kind = 'income';
  }
  return {...t, id: t.id || 'bank-' + index, description: limpaDesc(t.desc),
    group: grupoDe(t), category: catDe(t), kind, amount: Math.abs(t.valor), date: t.data.slice(0,10)};
});
}
'''
