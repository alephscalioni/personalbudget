"""Rule-first categorization. Bank evidence and user decisions are never AI output."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
import re
import unicodedata

from pydantic import Field, model_validator
from .models import Model
from .config import FINANCE
from . import store

VERSION = '1'
INCOME = ['Salário', 'Trabalho extra', 'Reembolsos', 'Rendimentos', 'Cashback', 'Aluguéis', 'Vendas', 'Outras receitas', 'Receitas a revisar']
PENDING = 'Receitas a revisar'


@lru_cache(maxsize=4)
def source_at(stamp):
    return (FINANCE / 'classificador.js').read_text()


@lru_cache(maxsize=4)
def digest_at(stamp):
    return hashlib.sha256(source_at(stamp).encode()).hexdigest()


@lru_cache(maxsize=4)
def taxonomy(stamp):
    # Read only declarative literals in the existing shared taxonomy; never eval JS.
    source = source_at(stamp)
    cats = re.search(r'const CATS = (\{.*?\n\});', source, re.S).group(1)
    cats = re.sub(r'/\*.*?\*/', '', cats, flags=re.S)
    cats = json.loads(re.sub(r',\s*}', '}', cats))
    block = re.search(r'const POR_NOME = \[(.*?)\n\];', source, re.S).group(1)
    rules = [(re.compile(pattern, re.I), json.loads(category), json.loads(group), generic == 'true')
             for pattern, category, group, generic in re.findall(
                 r'\[/((?:\\.|[^/])*)/i,\s*\[("[^"]*"),\s*("[^"]*")\],\s*(true|false)\]', block)]
    return cats, rules


def catalog():
    cats, rules = taxonomy((FINANCE / 'classificador.js').stat().st_mtime_ns)
    return {'income': INCOME, 'expense': sorted({v[1] for v in cats.values()} | {r[2] for r in rules} | {'Pessoas', 'Cuidados pessoais'})}


class Rule(Model):
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    priority: int = Field(default=100, ge=0, le=1000)
    kind: str = Field(pattern=r'^(income|expense)$')
    category: str = Field(min_length=1, max_length=80)
    description_contains: str | None = Field(default=None, min_length=3, max_length=180)
    description_exact: str | None = Field(default=None, min_length=3, max_length=180)
    institution: str | None = Field(default=None, min_length=1, max_length=80)
    payer_document_root: str | None = Field(default=None, pattern=r'^\d{8}$')
    method: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode='after')
    def valid_rule(self):
        if not (self.description_contains or self.description_exact or self.payer_document_root):
            raise ValueError('Informe descrição ou documento do pagador; banco e método sozinhos são insuficientes.')
        allowed = catalog()[self.kind]
        if self.category not in allowed or self.category in ('Salário', PENDING):
            raise ValueError('Categoria inválida. Salários exigem confirmação específica do titular.')
        return self


def matches(t, rule):
    if not rule.get('enabled', True) or t['kind'] != rule['kind']:
        return False
    fields = {'institution': 'instituicao', 'method': 'metodo', 'payer_document_root': 'payer_document_root'}
    if any(rule.get(key) and rule[key] != t.get(field) for key, field in fields.items()):
        return False
    desc = t.get('desc', t.get('description', '')).casefold()
    return (not rule.get('description_contains') or rule['description_contains'].casefold() in desc) and (not rule.get('description_exact') or rule['description_exact'].casefold() == desc)


def clean_description(value):
    return re.sub(r'^(transfer[êe]ncia (pix )?(enviada|recebida)|pix (enviado|recebido)|pagamento de (pix qr code|conta|boleto)|ted (enviada|recebida))\s*\|?\s*', '', value or '?', flags=re.I).strip() or value or '?'


def base(raw, recurrence=None):
    t = deepcopy(raw)
    card = t.get('conta_tipo') == 'CREDIT'
    salary = t.get('is_salary') and t.get('salary_person') and not card and t.get('valor', 0) > 0 and t.get('natureza') == 'entrada'
    kind = 'other'
    if salary:
        kind = 'income'
    elif card and t.get('fatura') and t.get('categoria') != 'Credit card payment':
        kind = 'expense' if t.get('tipo') == 'DEBIT' else 'refund'
    elif not card and not t.get('externa') and t.get('natureza') != 'interna' and not re.search(r'\bkavak\b|\bauto\s*art\b', t.get('desc', ''), re.I):
        kind = {'consumo': 'expense', 'entrada': 'income'}.get(t.get('natureza'), 'other')
    cats, names = taxonomy((FINANCE / 'classificador.js').stat().st_mtime_ns)
    category, group = cats.get(t.get('categoria'), [t.get('categoria') or 'Sem categoria', 'Outros'])
    source, reason = 'bank', 'Categoria informada pelo banco.'
    for pattern, label, bucket, generic in names:
        if (not generic or t.get('categoria') in (None, '', 'Shopping', 'Services', 'Transfers')) and pattern.search(t.get('desc', '')):
            category, group, source, reason = label, bucket, 'rule', 'Regra de descrição do estabelecimento.'
            break
    if kind == 'expense' and not card and not t.get('externa') and (group in ('Transferências', 'Outros') or category == 'Serviços'):
        source_text = source_at((FINANCE / 'classificador.js').stat().st_mtime_ns)
        gateway = re.search(r'const RX_GATEWAY = /(.*?)/i;', source_text).group(1)
        name = clean_description(t.get('desc', ''))
        if re.search(gateway, name, re.I):
            category, group, source, reason = 'Compra via gateway (lojista oculto)', 'Compras', 'rule', 'Identificação de intermediário de pagamento.'
        else:
            tokens = set(json.loads('[' + re.search(r'const EMPRESA_TOKENS = new Set\(\[(.*?)\]\);', source_text, re.S).group(1) + ']'))
            normalized = ''.join(c for c in unicodedata.normalize('NFD', name) if not unicodedata.combining(c)).lower()
            company = any(w in tokens for w in re.split(r'[^a-z0-9]+', normalized))
            person = re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.-]*(\s+[A-Za-zÀ-ÿ'.-]+){1,5}", name)
            if not company and person and not re.match(r'^\d{2}\.\d{3}\.\d{3}\b', name):
                count, value = (recurrence or {}).get(name, (0, 0))
                category = f'{name} ({count}x)' if count >= 3 or value >= 1000 else 'PIX eventual a pessoas'
                group, source, reason = 'Pessoas', 'rule', 'Identificação de contraparte; finalidade pendente.'
    if t.get('grupo'):
        category, group, source, reason = t.get('categoria') or 'Sem categoria', t['grupo'], 'rule', 'Regra local de classificação.'
    t.update(description=clean_description(t.get('desc', '?')), date=t['data'][:10], amount=abs(t['valor']), kind=kind, category=category, group=group)
    return t, source, reason


def fingerprint(t, rules):
    evidence = {k: t.get(k) for k in ('id', 'desc', 'description', 'kind', 'categoria', 'grupo', 'metodo', 'instituicao', 'payer_document_root', 'valor', 'date')}
    return hashlib.sha256(json.dumps([VERSION, evidence, rules, digest_at((FINANCE / 'classificador.js').stat().st_mtime_ns)], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def classify(payload, manual, overrides):
    rules = sorted(store.all_of('classification-rule'), key=lambda r: (-r.get('priority', 100), r['id']))
    adjustments = {o['id']: o for o in overrides}
    cached = {c['id']: c for c in store.all_of('classification-result')}
    rows, pending = [], []
    recurrence = {}
    for raw in payload['lancamentos']:
        if raw.get('conta_tipo') != 'CREDIT' and raw.get('natureza') == 'consumo':
            name = clean_description(raw.get('desc', ''))
            count, value = recurrence.get(name, (0, 0))
            recurrence[name] = (count + 1, value + abs(raw['valor']))
    for raw in payload['lancamentos']:
        t, source, reason = base(raw, recurrence)
        override = adjustments.get(t['id'])
        if override:
            t.update({k: v for k, v in override.items() if v is not None or k in ('salary_person', 'cashflow_line')})
            t['adjusted'] = True
            if any(override.get(k) for k in ('group', 'income_category', 'kind', 'is_salary', 'salary_person', 'reviewed')):
                source, reason = 'manual', 'Ajuste confirmado pelo usuário.'
        unresolved = False
        rule_id = None
        if t['kind'] == 'income':
            category = t.get('income_category')
            if not category and (t.get('is_salary') or t.get('salary_person') or t.get('metodo') == 'Salário' or t.get('categoria') in ('Salary', 'Salaries')):
                category = 'Salário'
            if not category and override and override.get('group'):
                category = override['group']
            if not category:
                category = {'Cashback': 'Cashback', 'Interest income': 'Rendimentos', 'Dividends': 'Rendimentos'}.get(t.get('categoria'), PENDING)
            t['category'] = t['group'] = t['income_category'] = category
            unresolved = category == PENDING
        elif t['kind'] in ('expense', 'refund'):
            unresolved = t['group'] in ('Outros', 'Transferências', 'Pessoas') or (source == 'bank' and t.get('categoria') == 'Services')
        if t['kind'] == 'other' and source != 'manual':
            source, reason = 'rule', 'Movimentação fora do resultado: transferência própria, fatura ou patrimônio.'
        elif source != 'manual':
            matched = next((r for r in rules if matches(t, r)), None)
            if matched and not (t['kind'] == 'income' and t['group'] == 'Salário'):
                t['group'] = t['category'] = matched['category']
                if t['kind'] == 'income':
                    t['income_category'] = matched['category']
                source, reason, rule_id, unresolved = 'rule', matched['name'], matched['id'], False
        else:
            unresolved = False  # User decisions, including "Outros", are authoritative.
        key = fingerprint(t, rules)
        confidence = None
        suggestion = None
        if unresolved:
            result = cached.get(key)
            if result:
                suggestion = result.get('category')
                confidence = result.get('confidence')
                if suggestion and confidence >= 0.9:
                    t['group'] = t['category'] = suggestion
                    if t['kind'] == 'income':
                        t['income_category'] = suggestion
                    source, reason, unresolved = 'ai', result['reason'], False
            if unresolved:
                source, reason = 'pending', 'Evidência insuficiente para categorizar automaticamente.'
                pending.append({'fingerprint': key, 'transaction_id': t['id'], 'kind': t['kind'], 'description': re.sub(r'\d{8,}', '[documento]', t['description'])[:180], 'bank_category': t.get('categoria'), 'method': t.get('metodo'), 'allowed_categories': [c for c in catalog()['income' if t['kind'] == 'income' else 'expense'] if c not in ('Salário', PENDING, 'Outros', 'Transferências', 'Pessoas')]})
        needs_review = unresolved or (t['kind'] == 'income' and t['group'] == 'Salário' and not t.get('salary_person'))
        t['classification'] = {'source': source, 'reason': reason, 'confidence': confidence, 'rule_id': rule_id, 'needs_review': needs_review, 'suggestion': suggestion, 'fingerprint': key, 'version': VERSION}
        t['income_needs_review'] = t['kind'] == 'income' and needs_review
        rows.append(t)
    for raw in manual:
        t = dict(raw, manual=True, instituicao='Manual', conta='Registro manual', conta_tipo='MANUAL', category=raw['group'])
        if t['kind'] == 'income':
            t['group'] = t['category'] = t['income_category'] = t.get('income_category') or ('Salário' if t.get('is_salary') or t.get('salary_person') else t['group'])
        t['classification'] = {'source': 'manual', 'reason': 'Lançamento do usuário.', 'needs_review': False, 'version': VERSION}
        rows.append(t)
    return rows, pending


def ai_enabled():
    return os.getenv('PERSONALBUDGET_CLASSIFICATION_AI_ENABLED', '0') == '1' and bool(os.getenv('PERSONALBUDGET_KALEU_TOKEN'))
