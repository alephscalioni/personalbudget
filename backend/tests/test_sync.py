import copy
import unittest
from unittest.mock import patch
from backend import bank_sync

class SyncTests(unittest.TestCase):
    def test_history_keeps_only_records_before_provider_window(self):
        old = {'janela':['2024-01-01','2026-09-01'], 'instituicoes':[{'contas':[{'id':'a','lancamentos':[{'data':'2024-01-01','valor':10},{'data':'2026-09-01','valor':20}]}]}]}
        new = {'janela':['2025-09-28','2026-09-28'], 'instituicoes':[{'contas':[{'id':'a','tipo':'BANK','saldo_inicial':100,'lancamentos':[{'data':'2026-09-01','valor':21}]}]}]}
        merged = bank_sync.preserve_history(copy.deepcopy(new),old)
        rows = merged['instituicoes'][0]['contas'][0]['lancamentos']
        self.assertEqual([t['valor'] for t in rows],[21,10])
        self.assertEqual(merged['janela'][0],'2024-01-01')
        self.assertEqual(merged['caixa_inicial'],90)
        self.assertEqual(merged['instituicoes'][0]['contas'][0]['saldo_inicial'],90)

    def test_partial_and_empty_collections_rejected(self):
        for raw in [{'instituicoes':[]},{'instituicoes':[{'contas':[{'erro_extrato':'failure'}]}]}]:
            with self.assertRaises(ValueError): bank_sync.validate(raw)
        old={'instituicoes':[{'contas':[{'id':'a'},{'id':'b'}]}]}
        with self.assertRaises(ValueError): bank_sync.validate({'instituicoes':[{'contas':[{'id':'a'}]}]},old)
