"""Monthly bank cash statement and a trailing moving-average projection."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def month_add(month, count):
    year, number = map(int, month.split('-'))
    index = year * 12 + number - 1 + count
    return f'{index // 12:04d}-{index % 12 + 1:02d}'


def text(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value or '') if not unicodedata.combining(c)).lower()


def bucket(t, incoming):
    if not incoming and (t.get('natureza') == 'fatura' or t.get('categoria') == 'Credit card payment'):
        return 'Faturas dos cartões'
    if t.get('kind') == 'other':
        if t.get('natureza') == 'interna' or t.get('externa'):
            return 'Transferências recebidas (não receitas)' if incoming else 'Transferências enviadas (não despesas)'
        return 'Resgates e outras entradas patrimoniais' if incoming else 'Aplicações e outras saídas patrimoniais'
    if incoming:
        if t.get('is_salary') or t.get('salary_person') or t.get('income_category') == 'Salário' or t.get('metodo') == 'Salário' or t.get('categoria') == 'Salary':
            person = {'aleph': 'Aleph', 'bianca': 'Bianca'}.get(t.get('salary_person'), 'titular a identificar')
            return 'Salário · ' + person
        category = t.get('income_category')
        return 'Outras receitas a identificar' if category in (None, 'Receitas a revisar') else category
    if t.get('natureza') == 'fatura' or t.get('categoria') == 'Credit card payment':
        return 'Faturas dos cartões'
    desc = text(t.get('description') or t.get('desc'))
    category = text(t.get('category') or t.get('categoria'))
    if re.search(r'financ\w* imobili|credito imobili', desc) or 'financiamento imobili' in category:
        return 'Financiamento'
    if re.search(r'condominio|harmonia morumbi|\blello\b', desc) or category == 'condominio':
        return 'Condomínio'
    if t.get('categoria') in ('Electricity', 'Water and sewage', 'Utilities', 'Internet', 'Telecommunications') or category in ('energia', 'agua e gas', 'agua e esgoto', 'internet', 'telefonia', 'contas de casa'):
        return 'Contas residenciais'
    if t.get('kind') == 'refund':
        return 'Estornos recebidos'
    group = t.get('group') or 'Outras saídas a identificar'
    return 'Outras saídas a identificar' if group in ('Outros', 'Transferências', 'Pessoas', 'Sem categoria') else group


def build(data, window=3, horizon=6):
    finance = data['finance']
    as_of = finance['gerado_em'][:10]
    current = as_of[:7]
    raw_start = finance.get('janela', [as_of])[0]
    start = (raw_start or as_of)[:10]
    transactions = [t for t in data['transactions'] if not t.get('manual') and t.get('conta_tipo') != 'CREDIT' and t['date'] <= as_of]
    if transactions:
        start = min(start, min(t['date'] for t in transactions))
    first = start[:7]
    rows = defaultdict(list)
    for t in transactions:
        rows[t['date'][:7]].append(t)
    months = []
    month = first
    while month <= current:
        months.append(month)
        month = month_add(month, 1)
    result = []
    closing = cents(finance['resumo']['caixa'])
    for month in reversed(months):
        incoming, outgoing = defaultdict(lambda: {'value': 0, 'transactions': [], 'operational': True}), defaultdict(lambda: {'value': 0, 'transactions': [], 'operational': True})
        for t in rows[month]:
            positive = t.get('tipo') == 'CREDIT' if t.get('tipo') in ('CREDIT', 'DEBIT') else t.get('valor', 0) > 0
            name = bucket(t, positive)
            entry = (incoming if positive else outgoing)[name]
            entry['value'] += cents(t['amount'])
            # Invoice payments are operational cash, even though kind is "other".
            operational = t['kind'] in ('income', 'expense', 'refund') or t.get('natureza') == 'fatura' or t.get('categoria') == 'Credit card payment'
            entry['operational'] = entry['operational'] and operational
            entry['transactions'].append({k: t.get(k) for k in ('id', 'date', 'description', 'amount', 'kind', 'group', 'category', 'classification')})
        for name in ('Financiamento', 'Condomínio', 'Contas residenciais', 'Alimentação', 'Faturas dos cartões', 'Outras saídas a identificar'):
            outgoing[name]  # Keep the main cost lines visible even with no payment.
        incoming['Outras receitas a identificar']
        income = sum(e['value'] for e in incoming.values())
        spending = sum(e['value'] for e in outgoing.values())
        opening = closing - income + spending
        def entries(groups):
            return [{'name': name, 'amount': entry['value'] / 100, 'operational': entry['operational'], 'transactions': entry['transactions']} for name, entry in sorted(groups.items(), key=lambda pair: -pair[1]['value'])]
        result.append({'month': month, 'status': 'partial' if month == current or (month == first and start > month + '-01') else 'historical',
                       'opening': opening / 100, 'income': income / 100, 'spending': spending / 100, 'closing': closing / 100,
                       'incoming': entries(incoming), 'outgoing': entries(outgoing)})
        closing = opening
    history = list(reversed(result))
    # Take consecutive full calendar months; an observed zero is part of the mean.
    eligible = [r for r in history if r['status'] == 'historical'][-window:]
    averages = {'incoming': defaultdict(int), 'outgoing': defaultdict(int)}
    for row in eligible:
        for side in averages:
            for entry in row[side]:
                if entry['operational']:
                    averages[side][entry['name']] += cents(entry['amount'])
    count = len(eligible)
    average_rows = {side: [{'name': name, 'amount': int((Decimal(value) / count).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) / 100} for name, value in sorted(groups.items())] if count else [] for side, groups in averages.items()}
    average_income = sum(cents(e['amount']) for e in average_rows['incoming'])
    average_spending = sum(cents(e['amount']) for e in average_rows['outgoing'])
    forecast = []
    if count:
        actual = history[-1]
        observed_income = sum(cents(e['amount']) for e in actual['incoming'] if e['operational'])
        observed_spending = sum(cents(e['amount']) for e in actual['outgoing'] if e['operational'])
        remaining_income = max(0, average_income - observed_income)
        remaining_spending = max(0, average_spending - observed_spending)
        closing = cents(actual['closing']) + remaining_income - remaining_spending
        forecast.append({'month': current, 'status': 'estimate', 'opening': actual['opening'], 'income': (cents(actual['income']) + remaining_income) / 100, 'spending': (cents(actual['spending']) + remaining_spending) / 100, 'closing': closing / 100})
        for offset in range(1, horizon + 1):
            opening = closing
            closing += average_income - average_spending
            forecast.append({'month': month_add(current, offset), 'status': 'forecast', 'opening': opening / 100, 'income': average_income / 100, 'spending': average_spending / 100, 'closing': closing / 100})
    return {'as_of': as_of, 'snapshot_balance': finance['resumo']['caixa'], 'history': history, 'forecast': forecast,
            'window': window, 'sample_months': [r['month'] for r in eligible], 'sample_count': count, 'horizon': horizon,
            'average_income': average_income / 100 if count else None, 'average_spending': average_spending / 100 if count else None,
            'average_incoming': average_rows['incoming'], 'average_outgoing': average_rows['outgoing'],
            'balance_source': 'Saldo bancário da coleta; saldos anteriores reconstruídos pelos movimentos disponíveis.'}
