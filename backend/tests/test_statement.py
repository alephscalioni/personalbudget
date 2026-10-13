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

    def test_investment_holdings_are_never_cash_movements(self):
        d=data([transaction('purchase','2026-09-01',100)],start='2026-09-01',balance=900)
        before=build(d)
        d['finance']['investimentos']=[{'nome':'Carteira','saldo':999999}]
        d['finance']['resumo']['investimentos']=999999
        after=build(d)
        self.assertEqual(before['history'],after['history'])
        self.assertEqual(before['forecast'],after['forecast'])
        self.assertEqual(after['history'][0]['operating_spending'],100)
        self.assertEqual(after['history'][0]['financial_net'],0)

    def test_applications_and_redemptions_are_separate_from_revenue_and_expenses(self):
        application=transaction('apply','2026-09-01',200)
        application.update(kind='other',natureza='investimento',categoria='Investments')
        redemption=transaction('redeem','2026-09-02',50,True)
        redemption.update(kind='other',natureza='investimento',categoria='Investments')
        report=build(data([application,redemption],start='2026-09-01',balance=850))
        row=report['history'][0]
        self.assertEqual(row['opening'],1000)
        self.assertEqual(row['operating_income'],0)
        self.assertEqual(row['operating_spending'],0)
        self.assertEqual(row['financial_net'],-150)
        self.assertEqual(row['financial_outgoing'][0]['name'],'Aplicações em investimentos')
        self.assertEqual(row['financial_incoming'][0]['name'],'Resgates de investimentos')
        self.assertEqual(row['operating_balance']+row['financial_net'],row['closing'])
        self.assertEqual(report['average_income'],0)
        self.assertEqual(report['average_spending'],0)

    def test_unidentified_other_movements_are_not_called_investments(self):
        row=transaction('unknown','2026-09-01',100)
        row.update(kind='other',natureza='unknown')
        report=build(data([row],start='2026-09-01',balance=900))
        self.assertEqual(report['history'][0]['financial_outgoing'][0]['name'],'Outras movimentações a conferir')

    def test_forecast_preserves_actual_financial_movements_in_current_month(self):
        rows=[transaction('salary','2026-09-01',1000,True),transaction('cost','2026-09-02',500),transaction('oct-salary','2026-10-01',200,True),transaction('oct-cost','2026-10-02',100)]
        application=transaction('apply','2026-10-03',200)
        application.update(kind='other',natureza='investimento')
        rows.append(application)
        report=build(data(rows,start='2026-09-01',balance=1000))
        for row in report['forecast']:
            self.assertAlmostEqual(row['opening']+row['operating_income']-row['operating_spending']+row['financial_net'],row['closing'],places=2)
        self.assertEqual(report['forecast'][0]['financial_net'],-200)
        self.assertTrue(all(r['financial_net']==0 for r in report['forecast'][1:]))

    def account_fixture(self):
        incoming=transaction('in','2026-09-01',100,True)
        outgoing=transaction('out','2026-09-02',70)
        for t in (incoming,outgoing):
            t.update(conta_id='a',instituicao='Banco',conta='Conta A')
        d=data([incoming,outgoing],balance=1030)
        d['finance']['contas']=[{'id':'a','instituicao':'Banco','nome':'Conta A','tipo':'BANK','saldo':1030,'saldo_inicial':1000}]
        return d

    def test_account_totals_and_collector_anchor_reconcile(self):
        report=build(self.account_fixture())['reconciliation']
        self.assertEqual(report['status'],'consistent')
        self.assertEqual(report['accounts'][0]['opening_difference'],0)
        self.assertTrue(all(not any(row['differences'].values()) for row in report['totals']))
        september=next(row for row in report['accounts'][0]['history'] if row['month']=='2026-09')
        self.assertEqual(september,{'month':'2026-09','opening':1000,'income':100,'spending':70,'closing':1030,'count':2})

    def test_missing_account_anchor_difference_and_sign_conflict_are_visible(self):
        for issue in ('missing','anchor','sign'):
            d=self.account_fixture()
            if issue=='missing': d['transactions'][0]['conta_id']='unknown'
            if issue=='anchor': d['finance']['contas'][0]['saldo_inicial']=900
            if issue=='sign': d['transactions'][1]['valor']=70
            report=build(d)['reconciliation']
            self.assertEqual(report['status'],'difference',issue)
            if issue=='missing':self.assertEqual(report['unmatched_transaction_ids'],['in'])
            if issue=='anchor':self.assertEqual(report['accounts'][0]['opening_difference'],100)
            if issue=='sign':self.assertEqual(report['sign_conflict_ids'],['out'])

    def test_duplicate_transactions_are_not_reported_as_reconciled(self):
        d=self.account_fixture()
        d['transactions'].append(dict(d['transactions'][0]))
        report=build(d)['reconciliation']
        self.assertEqual(report['status'],'difference')
        self.assertEqual(report['duplicate_transaction_ids'],['in'])

    def test_internal_transfer_reconciles_both_accounts_and_consolidated_cash(self):
        sent=transaction('sent','2026-09-01',200)
        received=transaction('received','2026-09-01',200,True)
        for t,identifier,name in ((sent,'a','A'),(received,'b','B')):
            t.update(kind='other',natureza='interna',conta_id=identifier,instituicao='Banco',conta=name)
        d=data([sent,received],balance=1500)
        d['finance']['contas']=[{'id':'a','instituicao':'Banco','nome':'A','tipo':'BANK','saldo':800,'saldo_inicial':1000},{'id':'b','instituicao':'Banco','nome':'B','tipo':'BANK','saldo':700,'saldo_inicial':500}]
        report=build(d)['reconciliation']
        self.assertEqual(report['status'],'consistent')
        self.assertEqual(report['accounts'][0]['history'][-1]['closing'],800)
        self.assertEqual(report['accounts'][1]['history'][-1]['closing'],700)
        self.assertTrue(all(not any(row['differences'].values()) for row in report['totals']))

    def test_legacy_duplicate_account_names_are_not_silently_combined(self):
        d=self.account_fixture()
        for t in d['transactions']:t['conta_id']=None
        d['finance']['contas'].append(dict(d['finance']['contas'][0],id='b',saldo=0,saldo_inicial=0))
        report=build(d)['reconciliation']
        self.assertEqual(report['status'],'difference')
        self.assertEqual(len(report['unmatched_transaction_ids']),2)

    def test_december_rollover_and_negative_cash(self):
        row=transaction('out','2026-11-01',100)
        report=build(data([row],as_of='2026-12-01',start='2026-11-01',balance=50),horizon=2)
        self.assertEqual(report['forecast'][-1]['month'],'2027-02')
        self.assertLess(report['forecast'][-1]['closing'],0)
