import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app import app
from backend import auth, store, service


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        fixture = {'gerado_em': '2026-09-27T12:00:00Z', 'janela': ['2026-09-01', '2026-09-27'],
                   'instituicoes': [{'nome': 'Banco teste', 'status': 'UPDATED', 'zeradas': 0,
                     'contas': [{'tipo': 'BANK', 'nome': 'Conta teste', 'saldo': 100, 'lancamentos': [{'data':'2026-08-31','desc':'Salário teste','valor':1000,'tipo':'CREDIT','categoria':'Salary','natureza':'entrada','metodo':'Salário'}]}],
                     'investimentos': []}]}
        (root / 'consolidado-2026-09-27.json').write_text(json.dumps(fixture))
        self.patches = [patch.object(store, 'DATABASE', root / 'test.sqlite3'),
                        patch.object(service, 'REPORTS', root),
                        patch.object(service, 'aplica_contrapartes', lambda p: None),
                        patch.object(service, 'aplica_mascara', lambda p: None),
                        patch.object(service, 'aplica_posicoes_manuais', lambda p: None)]
        for item in self.patches:
            item.start()
        service.snapshot.cache_clear()
        auth.attempts.clear()
        self.client = TestClient(app)

    def tearDown(self):
        for item in self.patches:
            item.stop()
        service.snapshot.cache_clear()
        self.directory.cleanup()

    def test_goal_roundtrip_persists_and_does_not_change_bank_snapshots(self):
        before = self.client.get('/api/data').json()['finance']['resumo']
        goal = {'name': 'Reserva teste', 'target': 1000, 'saved': 125.50, 'deadline': '2027-06-01'}
        response = self.client.post('/api/goals', json=goal)
        self.assertEqual(response.status_code, 201)
        identifier = response.json()['id']
        changed = self.client.put('/api/goals/' + identifier, json={**goal, 'saved': 250})
        self.assertEqual(changed.json()['saved'], 250)
        data = TestClient(app).get('/api/data').json()
        self.assertEqual(data['goals'][0]['saved'], 250)
        self.assertEqual(data['finance']['resumo'], before)
        self.assertEqual(self.client.delete('/api/goals/' + identifier).status_code, 204)
        self.assertEqual(self.client.get('/api/data').json()['goals'], [])
        self.assertEqual(self.client.put('/api/goals/missing', json=goal).status_code, 404)

    def test_transaction_validation_and_deletion(self):
        body = {'description': 'Teste local', 'amount': 15.75, 'date': '2026-09-27', 'kind': 'expense', 'group': 'Alimentação'}
        for change in [{'amount': -1}, {'amount': 0}, {'date': '2026-02-30'}, {'kind': 'transfer'}, {'description': '  '}, {'unexpected': 1}]:
            self.assertEqual(self.client.post('/api/transactions', json={**body, **change}).status_code, 422)
        response = self.client.post('/api/transactions', json=body)
        self.assertEqual(response.status_code, 201)
        identifier = response.json()['id']
        self.assertEqual(len(self.client.get('/api/data').json()['manual']), 1)
        self.assertEqual(self.client.delete('/api/transactions/' + identifier).status_code, 204)
        self.assertEqual(self.client.delete('/api/transactions/' + identifier).status_code, 404)

    def test_competence_override_is_stable_and_preserves_original_date(self):
        original = self.client.get('/api/data').json()['finance']['lancamentos'][0]
        identifier = original['id']
        response = self.client.put('/api/transactions/' + identifier + '/classification', json={'competence':'2026-09','kind':'income','is_salary':True})
        self.assertEqual(response.status_code, 200)
        service.snapshot.cache_clear()
        data = self.client.get('/api/data').json()
        self.assertEqual(data['finance']['lancamentos'][0]['id'], identifier)
        self.assertEqual(data['finance']['lancamentos'][0]['data'], '2026-08-31')
        self.assertEqual(data['overrides'][0]['competence'], '2026-09')
        self.assertEqual(self.client.put('/api/transactions/missing/classification', json={}).status_code, 404)
        self.assertEqual(self.client.delete('/api/transactions/' + identifier + '/classification').status_code, 204)
        self.assertEqual(self.client.get('/api/data').json()['overrides'], [])

    def test_budget_and_backup(self):
        body = {'lines': [{'nome': 'Casa', 'teto': 1000, 'grupos': ['Moradia']}], 'monthly_income': 5000, 'monthly_saving': 1000, 'benefits_spending': 400}
        self.assertEqual(self.client.put('/api/budget', json=body).status_code, 200)
        self.assertEqual(self.client.get('/api/data').json()['budget']['lines'], body['lines'])
        bad = {**body, 'lines': body['lines'] * 2}
        self.assertEqual(self.client.put('/api/budget', json=bad).status_code, 422)
        backup = self.client.get('/api/backup')
        self.assertEqual(backup.json()['version'], 1)
        self.assertEqual(backup.json()['budget'][0]['monthly_income'], 5000)
        self.assertNotIn('finance', backup.json())

    def test_privacy_and_local_origin(self):
        self.assertEqual(self.client.post('/api/goals', headers={'Origin': 'https://untrusted.example'}, json={}).status_code, 403)
        self.assertEqual(self.client.get('/api/data', headers={'Host': 'untrusted.example'}).status_code, 400)
        self.assertEqual(self.client.get('/api/data').headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get('/finance/pluggy/.env').status_code, 404)
        self.assertEqual(self.client.get('/data/budget.sqlite3').status_code, 404)

    def test_missing_and_invalid_report(self):
        missing = Path(self.directory.name) / 'missing'
        missing.mkdir()
        with patch('backend.service.REPORTS', missing):
            self.assertEqual(self.client.get('/api/data').status_code, 404)
            (missing / 'consolidado-2026-09-27.json').write_text('{invalid')
            self.assertEqual(self.client.get('/api/data').status_code, 422)

    def test_cloud_requires_login_and_protects_report_and_classifier(self):
        settings = {'PERSONALBUDGET_AUTH_REQUIRED': '1', 'PERSONALBUDGET_PASSWORD_HASH': auth.password_hash('private-test-password'), 'PERSONALBUDGET_SESSION_SECRET': 'test-secret-value'}
        with patch.dict('os.environ', settings):
            client = TestClient(app, base_url='https://testserver')
            self.assertEqual(client.get('/api/health').status_code, 200)
            self.assertEqual(client.get('/api/data').status_code, 401)
            self.assertEqual(client.get('/app/js/classifier.js').status_code, 401)
            self.assertEqual(client.get('/app/dashboard.html', follow_redirects=False).status_code, 307)
            self.assertFalse(client.get('/api/session').json()['authenticated'])
            self.assertEqual(client.post('/api/session', json={'username':'alephscalioni','password': 'wrong'}).status_code, 401)
            login = client.post('/api/session', json={'username':'alephscalioni','password': 'private-test-password'})
            self.assertEqual(login.status_code, 200)
            self.assertIn('HttpOnly', login.headers['set-cookie'])
            self.assertIn('Secure', login.headers['set-cookie'])
            self.assertTrue(login.json()['must_change_password'])
            self.assertEqual(client.get('/api/data').status_code, 401)
            changed = client.post('/api/password/change', json={'current_password':'private-test-password','new_password':'a-new-private-password'})
            self.assertEqual(changed.status_code, 200)
            self.assertFalse(changed.json()['must_change_password'])
            self.assertEqual(client.get('/api/data').status_code, 200)
            self.assertTrue(client.get('/api/session').json()['authenticated'])
            client.delete('/api/session')
            self.assertEqual(client.get('/api/data').status_code, 401)
            client.cookies.set('pb_session', '9999999999.bad.signature')
            self.assertEqual(client.get('/api/data').status_code, 401)

    def test_two_accounts_first_login_and_one_use_recovery(self):
        settings = {'PERSONALBUDGET_AUTH_REQUIRED':'1', 'PERSONALBUDGET_PASSWORD_HASH':auth.password_hash('temporary-password'), 'PERSONALBUDGET_SESSION_SECRET':'secret-for-test', 'PERSONALBUDGET_ALEPH_EMAIL':'recovery@example.test', 'PERSONALBUDGET_BIANCA_EMAIL':'recovery@example.test', 'PERSONALBUDGET_APP_URL':'https://budget.example.test', 'SMTP_USERNAME':'sender@example.test','SMTP_PASSWORD':'fake-test-only'}
        with patch.dict('os.environ', settings), patch('backend.mail.send_reset') as send:
            client=TestClient(app, base_url='https://testserver')
            auth.seed_users()
            self.assertEqual(len(store.all_of('user')),2)
            client.post('/api/session',json={'username':'biancascalioni','password':'temporary-password'})
            self.assertTrue(client.get('/api/session').json()['must_change_password'])
            self.assertEqual(client.get('/api/backup').status_code,401)
            changed=client.post('/api/password/change',json={'current_password':'temporary-password','new_password':'bianca-personal-test-password'})
            self.assertEqual(changed.status_code,200)
            old_cookie=client.cookies.get(auth.COOKIE)
            auth.seed_users()
            self.assertFalse(store.get('user','biancascalioni')['must_change_password'])
            response=client.post('/api/password/forgot',json={'username':'biancascalioni'})
            self.assertEqual(response.status_code,202)
            send.assert_called_once()
            self.assertEqual(send.call_args.args[0],'recovery@example.test')
            token=send.call_args.args[1]
            self.assertNotIn(token,response.text)
            self.assertNotIn(token,json.dumps(store.all_of('reset')))
            reset=client.post('/api/password/reset',json={'token':token,'new_password':'bianca-reset-test-password'})
            self.assertEqual(reset.status_code,200)
            self.assertEqual(client.post('/api/password/reset',json={'token':token,'new_password':'another-test-password'}).status_code,400)
            other=TestClient(app,base_url='https://testserver')
            other.cookies.set(auth.COOKIE,old_cookie)
            self.assertEqual(other.get('/api/data').status_code,401)
            other.post('/api/session',json={'username':'alephscalioni','password':'temporary-password'})
            self.assertTrue(other.get('/api/session').json()['must_change_password'])
            backup=client.get('/api/backup').json()
            self.assertNotIn('password_hash',json.dumps(backup))
            self.assertNotIn('user',backup)

    def test_cloud_without_secret_fails_closed(self):
        with patch.dict('os.environ', {'PERSONALBUDGET_AUTH_REQUIRED': '1', 'PERSONALBUDGET_PASSWORD_HASH': '', 'PERSONALBUDGET_SESSION_SECRET': ''}):
            self.assertEqual(self.client.get('/api/data').status_code, 401)
            self.assertFalse(self.client.get('/api/session').json()['configured'])
            self.assertEqual(self.client.post('/api/session', json={'username':'alephscalioni','password': 'anything'}).status_code, 503)

    def test_frontend_and_shared_classifier_are_served(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        response = self.client.get('/app/js/classifier.js')
        self.assertEqual(response.status_code, 200)
        self.assertIn('export function classifyPayload', response.text)
        self.assertIn('text/javascript', response.headers['content-type'])

    def test_declared_positions_persist_without_changing_income(self):
        baseline = self.client.get('/api/data').json()
        position = {'name':'Reserva', 'institution':'Banco teste', 'balance':123.45, 'reference':'2026-09-27', 'asset_class':'CDB'}
        r = self.client.post('/api/positions', json=position)
        self.assertEqual(r.status_code, 201)
        identifier = r.json()['id']
        data = self.client.get('/api/data').json()
        self.assertEqual(data['finance']['resumo']['liquido'], baseline['finance']['resumo']['liquido'] + 123.45)
        self.assertEqual(data['finance']['lancamentos'], baseline['finance']['lancamentos'])
        self.client.put('/api/positions/' + identifier, json={**position,'balance':200})
        self.assertEqual(self.client.get('/api/data').json()['finance']['manual_total'], 200)
        self.client.delete('/api/positions/' + identifier)
        self.assertEqual(self.client.get('/api/data').json()['positions'], [])
        audit = self.client.get('/api/audit').json()['entries']
        self.assertEqual(len(audit), 3)
        self.assertEqual(audit[0]['before']['balance'], 200)
        self.assertIsNone(audit[0]['after'])

    def test_kaleu_queue_lease_cannot_be_replayed(self):
        headers = {'Authorization':'Bearer test-agent-token'}
        with patch.dict('os.environ', {'PERSONALBUDGET_KALEU_TOKEN':'test-agent-token'}):
            job = self.client.post('/api/kaleu/messages', json={'message':'Consulte meu orçamento'}).json()
            self.assertEqual(self.client.post('/api/kaleu/claim').status_code, 403)
            claimed = self.client.post('/api/kaleu/claim', headers=headers).json()['job']
            self.assertEqual(claimed['id'], job['id'])
            self.assertIsNone(self.client.post('/api/kaleu/claim', headers=headers).json()['job'])
            visible = self.client.get('/api/kaleu/messages').json()
            self.assertNotIn('lease', str(visible))
            self.assertTrue(visible['available'])
            url = '/api/kaleu/jobs/' + job['id'] + '/complete'
            body = {'lease':claimed['lease'],'reply':'Consulta concluída'}
            self.assertEqual(self.client.post(url, headers=headers, json={**body,'lease':'x'*32}).status_code, 409)
            self.assertEqual(self.client.post(url, headers=headers, json=body).status_code, 200)
            self.assertEqual(self.client.post(url, headers=headers, json=body).status_code, 409)

    def test_kaleu_token_has_only_finance_permissions_and_audit(self):
        headers = {'Authorization':'Bearer test-agent-token'}
        with patch.dict('os.environ', {'PERSONALBUDGET_AUTH_REQUIRED':'1', 'PERSONALBUDGET_KALEU_TOKEN':'test-agent-token', 'PERSONALBUDGET_PASSWORD_HASH':auth.password_hash('a-unique-long-password'), 'PERSONALBUDGET_SESSION_SECRET':'test-secret'}):
            self.assertEqual(self.client.get('/api/data', headers=headers).status_code, 200)
            self.assertFalse(self.client.get('/api/session', headers=headers).json()['authenticated'])
            self.assertEqual(self.client.get('/api/kaleu/messages', headers=headers).status_code, 401)
            self.assertEqual(self.client.get('/app/dashboard.html', headers=headers, follow_redirects=False).status_code, 307)
            self.assertEqual(self.client.post('/api/refresh', headers=headers).status_code, 401)
            self.assertEqual(self.client.post('/api/goals', headers=headers, json={'name':'Meta','target':100,'saved':0}).status_code, 201)
            self.assertEqual(self.client.get('/api/audit', headers=headers).json()['entries'][0]['actor'], 'kaleu')
            self.assertEqual(self.client.get('/api/data', headers={'Authorization':'Bearer wrong'}).status_code, 401)

    def test_salary_plan_and_recipient_are_preserved(self):
        data = self.client.get('/api/data').json()
        self.assertEqual([p['person'] for p in data['salary_plan']], ['aleph','bianca'])
        body = {'description':'Salário Bianca', 'amount':10000, 'date':'2026-08-31', 'kind':'income', 'group':'Salário', 'is_salary':True, 'salary_person':'bianca'}
        self.assertEqual(self.client.post('/api/transactions', json=body).status_code, 201)
        self.assertEqual(self.client.get('/api/data').json()['manual'][0]['salary_person'], 'bianca')
        self.assertEqual(self.client.post('/api/transactions', json={**body,'salary_person':'unknown'}).status_code, 422)
        bank_id = data['finance']['lancamentos'][0]['id']
        r = self.client.put('/api/transactions/' + bank_id + '/classification', json={'kind':'income','is_salary':True,'salary_person':'bianca','cycle':'2026-09'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['salary_person'],'bianca')

    def test_confirmed_company_salary_rule_preserves_bank_totals(self):
        root = Path(self.directory.name)
        (root / 'salary-rules.json').write_text(json.dumps({'rules':[{'person':'bianca','payer_root':'12345678'}]}))
        report = root / 'consolidado-2026-09-27.json'
        raw = json.loads(report.read_text())
        incoming = {'data':'2026-08-31','desc':'Pix recebido 12.345.678 BIANCA','valor':10000,'tipo':'CREDIT','categoria':'Transfer','natureza':'entrada','metodo':'PIX'}
        raw['instituicoes'][0]['contas'][0]['lancamentos'] = [incoming, {**incoming,'desc':'Pix recebido BIANCA','valor':410}, {**incoming,'valor':-100,'natureza':'consumo','tipo':'DEBIT'}]
        report.write_text(json.dumps(raw))
        with patch.object(service,'FINANCE_CONFIG',root):
            service.snapshot.cache_clear()
            rows = self.client.get('/api/data').json()['finance']['lancamentos']
        self.assertEqual(rows[0]['salary_person'],'bianca')
        self.assertTrue(rows[0]['is_salary'])
        self.assertEqual(rows[0]['data'],'2026-08-31')
        self.assertEqual(rows[0]['valor'],10000)
        self.assertNotIn('salary_person',rows[1])
        self.assertNotIn('salary_person',rows[2])
        self.assertEqual(len(rows),3)

    def test_salary_portability_requires_exact_confirmed_rule(self):
        t = {'instituicao':'Banco teste','metodo':'TED','desc':'TED recebida TITULAR TESTE','externa':True}
        rule = {'person':'aleph','institution':'Banco teste','method':'TED','description':'TED recebida TITULAR TESTE'}
        self.assertFalse(service.matches_salary_rule(t, rule))
        confirmed = {**rule,'confirmed_portability':True}
        self.assertTrue(service.matches_salary_rule(t, confirmed))
        for changed in [{'desc':'PIX recebido TITULAR TESTE'}, {'instituicao':'Outro banco'}, {'metodo':'PIX'}]:
            self.assertFalse(service.matches_salary_rule({**t,**changed}, confirmed))
        self.assertFalse(service.matches_salary_rule(t, {**confirmed,'description':None}))
        self.assertTrue(service.matches_salary_rule({'instituicao':'Banco teste','metodo':'Salário'}, {'person':'aleph','institution':'Banco teste','method':'Salário'}))

    def test_portability_remains_one_credit_and_does_not_change_balances(self):
        root = Path(self.directory.name)
        before = self.client.get('/api/data').json()['finance']['resumo']
        report = root / 'consolidado-2026-09-27.json'
        raw = json.loads(report.read_text())
        t = raw['instituicoes'][0]['contas'][0]['lancamentos'][0]
        t.update(desc='TED recebida TITULAR TESTE', metodo='TED', externa=True)
        report.write_text(json.dumps(raw))
        rule = {'person':'aleph','institution':'Banco teste','method':'TED','description':t['desc'],'confirmed_portability':True}
        (root / 'salary-rules.json').write_text(json.dumps({'rules':[rule]}))
        with patch.object(service,'FINANCE_CONFIG',root):
            service.snapshot.cache_clear()
            result = self.client.get('/api/data').json()['finance']
        self.assertEqual(result['resumo'],before)
        self.assertEqual(len(result['lancamentos']),1)
        self.assertEqual(result['lancamentos'][0]['salary_person'],'aleph')
        self.assertTrue(result['lancamentos'][0]['externa'])
        self.assertEqual(result['lancamentos'][0]['valor'],1000)


if __name__ == '__main__':
    unittest.main()
