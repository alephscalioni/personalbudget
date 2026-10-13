import unittest
from backend.statement import build


def transaction(identifier, date, amount, incoming=False, **extra):
    return dict(id=identifier, date=date, amount=amount, valor=amount if incoming else -amount, tipo='CREDIT' if incoming else 'DEBIT', kind='income' if incoming else 'expense', group='Alimentação', description='Compra', conta_tipo='BANK', natureza='entrada' if incoming else 'consumo', **extra)


def data(rows, as_of='2026-10-13', start='2026-07-01', balance=1000):
    return {'finance': {'gerado_em': as_of+'T12:00:00Z', 'janela': [start, as_of], 'resumo': {'caixa': balance}}, 'transactions': rows}


class StatementTests(unittest.TestCase):
    def test_balance_chain_and_current_month_remainder(self):
        rows=[]
        for month in ('07', '08', '09'):
            rows.extend([transaction('in'+month, f'2026-{month}-05', 1000, True), transaction('out'+month, f'2026-{month}-10', 500)])
        rows += [transaction('oct-in', '2026-10-05', 200, True), transaction('oct-out', '2026-10-10', 100)]
        report=build(data(rows))
        self.assertEqual(report['sample_months'], ['2026-07', '2026-08', '2026-09'])
        self.assertEqual(report['average_income'], 1000)
        self.assertEqual(report['average_spending'], 500)
        for index,row in enumerate(report['history']):
            self.assertEqual(row['opening']+row['income']-row['spending'],row['closing'])
            if index:self.assertEqual(report['history'][index-1]['closing'], row['opening'])
        self.assertEqual(report['history'][-1]['closing'], 1000)
        self.assertEqual(report['forecast'][0]['closing'], 1400)
        self.assertEqual(report['forecast'][1]['opening'], 1400)
        self.assertEqual(report['forecast'][1]['closing'], 1900)

    def test_credit_purchases_are_not_cash_and_invoice_is_counted_once(self):
        purchase=transaction('buy', '2026-09-01', 200)
        purchase['conta_tipo']='CREDIT'
        invoice=transaction('bill', '2026-09-10', 200)
        invoice.update(kind='other',natureza='fatura')
        report=build(data([purchase,invoice],start='2026-09-01'))
        self.assertEqual(report['history'][0]['spending'],200)
        self.assertEqual(report['history'][0]['outgoing'][0]['name'],'Faturas dos cartões')
        self.assertEqual(report['average_spending'],200)

    def test_transfers_affect_balance_but_not_operational_average(self):
        transfer=transaction('own','2026-09-01',2000,True)
        transfer.update(kind='other',externa=True)
        expense=transaction('out','2026-09-05',200)
        report=build(data([transfer,expense],start='2026-09-01'))
        self.assertEqual(report['history'][0]['income'],2000)
        self.assertEqual(report['average_income'],0)
        self.assertEqual(report['average_spending'],200)

    def test_zero_months_count_and_partial_months_do_not(self):
        rows=[transaction('out','2026-08-01',600),transaction('first','2026-07-20',999)]
        report=build(data(rows,start='2026-07-15'))
        self.assertEqual(report['sample_months'],['2026-08','2026-09'])
        self.assertEqual(report['average_spending'],300)

    def test_insufficient_history_no_projection(self):
        report=build(data([],start='2026-10-01'))
        self.assertEqual(report['forecast'],[])
        self.assertIsNone(report['average_income'])

    def test_financing_condo_and_utilities_have_separate_lines(self):
        rows=[transaction('mortgage','2026-09-01',1000),transaction('condo','2026-09-02',500),transaction('power','2026-09-03',100)]
        rows[0]['description']='Crédito imobiliário'
        rows[1]['description']='Condomínio'
        rows[2]['categoria']='Electricity'
        report=build(data(rows,start='2026-09-01'))
        self.assertTrue({'Financiamento','Condomínio','Contas residenciais'}.issubset({r['name'] for r in report['history'][0]['outgoing']}))

    def test_manual_and_future_movements_do_not_change_observed_balance(self):
        manual=transaction('manual','2026-09-01',10000,True)
        manual['manual']=True
        future=transaction('future','2026-12-01',20000)
        report=build(data([manual,future],start='2026-09-01'))
        self.assertTrue(all(r['opening']==1000 and r['closing']==1000 for r in report['history']))

    def test_december_rollover_and_negative_cash(self):
        row=transaction('out','2026-11-01',100)
        report=build(data([row],as_of='2026-12-01',start='2026-11-01',balance=50),horizon=2)
        self.assertEqual(report['forecast'][-1]['month'],'2027-02')
        self.assertLess(report['forecast'][-1]['closing'],0)
