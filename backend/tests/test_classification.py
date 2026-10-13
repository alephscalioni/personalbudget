import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from starlette.requests import Request
from pydantic import ValidationError
from backend import classification as engine, classification_api as queue, store


def credit(**changes):
    return dict(id='bank-test', data='2026-10-01', desc='PIX recebido Pessoa', valor=100, tipo='CREDIT', conta_tipo='CHECKING', natureza='entrada', categoria='Income', **changes)


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(store, 'DATABASE', Path(self.temp.name) / 'test.sqlite'), patch.object(store, 'DATABASE_URL', ''), patch.dict(os.environ, PERSONALBUDGET_CLASSIFICATION_AI_ENABLED='1', PERSONALBUDGET_KALEU_TOKEN='test-token')]
        for p in self.patches:
            p.start()
        self.request = Request({'type': 'http', 'headers': [(b'authorization', b'Bearer test-token')]})

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def classify(self, raw=None, overrides=None):
        return engine.classify({'lancamentos': [raw or credit()]}, [], overrides or [])

    def test_unknown_income_is_pending_without_mutating_bank(self):
        raw = credit()
        original = copy.deepcopy(raw)
        rows, pending = self.classify(raw)
        self.assertEqual(raw, original)
        self.assertEqual(rows[0]['group'], engine.PENDING)
        self.assertEqual(len(pending), 1)

    def test_manual_precedes_rules_and_ai(self):
        rule = engine.Rule(name='Cliente', kind='income', category='Vendas', description_contains='Pessoa')
        store.save('classification-rule', rule.model_dump(), 'client')
        rows, pending = self.classify(overrides=[{'id': 'bank-test', 'group': 'Reembolsos', 'kind': 'income'}])
        self.assertEqual(rows[0]['group'], 'Reembolsos')
        self.assertEqual(rows[0]['classification']['source'], 'manual')
        self.assertFalse(pending)

    def test_custom_rule_handles_income(self):
        store.save('classification-rule', engine.Rule(name='Cliente', kind='income', category='Vendas', description_contains='Pessoa').model_dump(), 'client')
        rows, pending = self.classify()
        self.assertEqual(rows[0]['income_category'], 'Vendas')
        self.assertFalse(pending)

    def test_transfers_and_investments_not_income(self):
        for change in ({'externa': True}, {'natureza': 'interna'}, {'natureza': 'aplicacao'}, {'desc': 'Kavak'}):
            raw = credit()
            raw.update(change)
            rows, pending = self.classify(raw)
            self.assertEqual(rows[0]['kind'], 'other')
            self.assertFalse(pending)

    def test_salary_never_sent_to_ai(self):
        raw = credit(is_salary=True, salary_person='bianca')
        rows, pending = self.classify(raw)
        self.assertEqual(rows[0]['group'], 'Salário')
        self.assertFalse(pending)

    def test_existing_merchant_rules(self):
        raw = credit()
        raw.update(desc='Railway', conta_tipo='CREDIT', tipo='DEBIT', fatura='2026-10', categoria='Public transportation')
        rows, pending = self.classify(raw)
        self.assertEqual((rows[0]['kind'], rows[0]['group']), ('expense', 'Infra'))
        self.assertFalse(pending)

    def test_no_salary_or_unbounded_rules(self):
        for options in ({'institution': 'Bank'}, {'description_contains': 'Pessoa', 'category': 'Salário'}):
            body = dict(name='test', kind='income', category='Vendas')
            body.update(options)
            with self.assertRaises(ValidationError):
                engine.Rule(**body)

    def test_ai_result_validates_and_manual_still_wins(self):
        _, pending = self.classify()
        queue.enqueue(pending)
        queue.enqueue(pending)
        self.assertEqual(len(store.all_of('classification-task')), 1)
        with patch('backend.service.data', return_value={'transactions': self.classify()[0]}):
            job = queue.claim(self.request)['job']
        decision = {'fingerprint': pending[0]['fingerprint'], 'category': 'Reembolsos', 'confidence': .95, 'reason': 'Descrição explícita de reembolso.'}
        body = queue.Completion(lease=job['lease'], decisions=[decision])
        queue.complete(job['id'], body, self.request)
        rows, pending = self.classify()
        self.assertEqual(rows[0]['group'], 'Reembolsos')
        self.assertEqual(rows[0]['classification']['source'], 'ai')
        self.assertFalse(pending)
        rows, _ = self.classify(overrides=[{'id': 'bank-test', 'group': 'Vendas'}])
        self.assertEqual(rows[0]['group'], 'Vendas')
        with self.assertRaises(HTTPException):
            queue.complete(job['id'], body, self.request)

    def test_low_confidence_and_stale_results_remain_pending(self):
        _, pending = self.classify()
        key = pending[0]['fingerprint']
        store.save('classification-result', {'category': 'Vendas', 'confidence': .5, 'reason': 'Duvidoso'}, key)
        rows, pending = self.classify()
        self.assertEqual(rows[0]['group'], engine.PENDING)
        self.assertEqual(rows[0]['classification']['suggestion'], 'Vendas')
        store.save('classification-result', {'category': 'Vendas', 'confidence': .99, 'reason': 'Anterior'}, key)
        raw = credit()
        raw['desc'] = 'Outro PIX'
        rows, pending = self.classify(raw)
        self.assertEqual(rows[0]['group'], engine.PENDING)

    def test_invalid_ai_category_does_not_commit(self):
        _, pending = self.classify()
        queue.enqueue(pending)
        with patch('backend.service.data', return_value={'transactions': self.classify()[0]}):
            job = queue.claim(self.request)['job']
        with self.assertRaises(HTTPException):
            queue.complete(job['id'], queue.Completion(lease=job['lease'], decisions=[{'fingerprint': pending[0]['fingerprint'], 'category': 'Salário', 'confidence': 1, 'reason': 'Inventado'}]), self.request)
        self.assertFalse(store.all_of('classification-result'))
        self.assertEqual(store.get('classification-job', job['id'])['status'], 'running')

    def test_expired_lease_and_failure_retry_limit(self):
        _, pending = self.classify()
        queue.enqueue(pending)
        with patch('backend.service.data', return_value={'transactions': self.classify()[0]}):
            first = queue.claim(self.request)['job']
            job = store.get('classification-job', first['id'])
            job['started'] = 0
            store.save('classification-job', job, job['id'])
            with self.assertRaises(HTTPException):
                queue.complete(first['id'], queue.Completion(lease=first['lease'], failed=True), self.request)
            task = store.get('classification-task', pending[0]['fingerprint'])
            task['started'] = 0
            store.save('classification-task', task, task['id'])
            for attempt in (2, 3):
                job = queue.claim(self.request)['job']
                self.assertIsNotNone(job)
                queue.complete(job['id'], queue.Completion(lease=job['lease'], failed=True), self.request)
            self.assertIsNone(queue.claim(self.request)['job'])
        self.assertEqual(store.get('classification-task', pending[0]['fingerprint'])['status'], 'failed')

    def test_financial_fields_in_ai_output_are_rejected(self):
        with self.assertRaises(ValidationError):
            queue.Decision(fingerprint='a' * 64, category='Vendas', confidence=1, reason='Teste', amount=1000)


if __name__ == '__main__':
    unittest.main()
