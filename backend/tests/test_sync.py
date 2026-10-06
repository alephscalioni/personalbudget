import copy
import importlib
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from backend import bank_sync

class SyncTests(unittest.TestCase):
    def test_report_publication_preserves_previous_file_on_generator_failure(self):
        app_module = importlib.import_module('backend.app')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            frontend = root / 'frontend'
            frontend.mkdir()
            report = frontend / 'dashboard.html'
            report.write_text('Previous report')
            raw = root / 'consolidado-2026-10-06.json'
            raw.write_text('{}')
            generator = root / 'generator.py'
            generator.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[sys.argv.index('--out')+1]).write_text('Updated report')\n")
            with patch.object(app_module, 'ROOT', root), patch.object(app_module, 'FRONTEND', frontend), \
                 patch.object(app_module, 'GENERATOR', generator), patch.object(app_module.service, 'latest', return_value=raw):
                result = app_module.sync_dashboard()
                self.assertEqual(report.read_text(), 'Updated report')
                self.assertEqual(result['bytes'], len('Updated report'))
                generator.write_text(generator.read_text() + 'raise RuntimeError("Failed")\n')
                with self.assertRaises(Exception):
                    app_module.sync_dashboard()
                self.assertEqual(report.read_text(), 'Updated report')
                self.assertEqual(list(frontend.iterdir()), [report])

    def test_successful_collection_regenerates_report_and_reports_render_failure(self):
        raw = {'gerado_em': '2026-09-27T12:00:00Z', 'janela': ['2026-09-01', '2026-09-27'],
               'instituicoes': [{'nome': 'Teste', 'status': 'UPDATED', 'zeradas': 0, 'contas': [{'id': 'a', 'tipo': 'BANK', 'nome': 'Conta', 'saldo': 10, 'lancamentos': []}], 'investimentos': []}]}
        records = {}
        def save(kind, body, identifier=None):
            records[(kind, identifier)] = copy.deepcopy(body)
            return body
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(bank_sync, 'REPORTS', Path(folder)), \
             patch.object(bank_sync.store, 'get', side_effect=lambda kind, identifier: copy.deepcopy(records.get((kind, identifier)))), \
             patch.object(bank_sync.store, 'save', side_effect=save), \
             patch('coleta_consolidada.coletar', side_effect=lambda *a, **kw: copy.deepcopy(raw)), \
             patch('backend.app.sync_dashboard') as render:
            result = bank_sync.run_once()
            self.assertEqual(result['status'], 'ok')
            render.assert_called_once()
            self.assertIsNone(result['report_error'])
            render.side_effect = RuntimeError('Generator failed')
            result = bank_sync.run_once()
            self.assertEqual(result['status'], 'ok')
            self.assertTrue(result['report_error'])
            self.assertIn(('bank-snapshot', 'current'), records)

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
