"""Guard evaluation scope and historical retrieval comparability; no network."""
import ast
import json
import unittest
from unittest.mock import patch
from scripts.golden_sets import ROOT, load_golden


class GoldenEvaluations(unittest.TestCase):
    def test_rag_sources_and_scope(self):
        rows = load_golden('golden_questions.json', 'rag_only')
        self.assertEqual(len(rows), 20)
        self.assertEqual(sum(r['rag_answerable'] for r in rows), 16)
        self.assertTrue(all('answerable' not in r for r in rows))
        self.assertTrue(all(r['relevant_source_ids'] == [] for r in rows if not r['rag_answerable']))

    def test_positive_benchmark_unchanged(self):
        old = json.loads((ROOT / 'evaluations/phase5a_baseline/golden_questions.json').read_text())
        new = load_golden('golden_questions.json', 'rag_only')
        for before, after in zip(old, new):
            self.assertEqual(before['id'], after['id'])
            self.assertEqual(before['answerable'], after['rag_answerable'])
            self.assertEqual(before['expected_facts'], after['expected_facts'])
            self.assertEqual(before['relevant_source_ids'], after['relevant_source_ids'])
            if before['answerable']:
                self.assertEqual(before['question'], after['question'])
        self.assertNotIn('for every automation mode', new[16]['question'])
        self.assertIn('any documented', new[16]['question'])

    def test_agent_search_candidates_are_not_negative_rag_labels(self):
        rows = load_golden('agent_golden_questions.json', 'full_agent')
        self.assertEqual(len(rows), 12)
        self.assertTrue(all('rag_answerable' not in r and 'answerable' not in r for r in rows))
        self.assertTrue(any(r['answerability']['status'] == 'evidence_search_required' for r in rows))
        self.assertTrue(any(len(r['user_turns']) > 1 for r in rows))
        self.assertTrue(any(r['category'] == 'licensing' for r in rows))
        insufficient = [r for r in rows if r['answerability']['status'] == 'insufficient_evidence_after_research']
        self.assertEqual(len(insufficient), 1)
        self.assertTrue(insufficient[0]['evaluation_conditions'])
        for row in rows:
            for ref in row['verified_source_references']:
                self.assertTrue((ROOT / ref['artifact']).is_file())
                self.assertIn(ref['url'], (ROOT / ref['artifact']).read_text())

    def test_runtime_does_not_consume_golden_labels(self):
        for path in (ROOT / 'backend/app').rglob('*.py'):
            if path.name == 'studio_cli.py':  # explicit offline evaluation entrypoint
                continue
            text = path.read_text()
            for marker in ('golden_questions.json', 'rag_answerable', 'scripts.golden_sets'):
                self.assertNotIn(marker, text, str(path))
            tree = ast.parse(text)
            self.assertFalse(any(isinstance(n, ast.ImportFrom) and
                                 n.module == 'app.rag.studio_cli' for n in ast.walk(tree)))

    def test_retrieval_metric_excludes_negatives_without_changing_denominator(self):
        from app.rag import studio_cli
        rows = load_golden('golden_questions.json', 'rag_only')
        expected = {r['question']: r['relevant_source_ids'] for r in rows}
        def search(_store, question, namespace, top_k):
            return [{'metadata': {'source_id': s}} for s in expected[question]]
        with patch.object(studio_cli, 'connected'), patch.object(studio_cli, 'search', search), \
                patch('pathlib.Path.write_text'):
            report = studio_cli.retrieval_evaluation()
        for strategy in report['strategies'].values():
            self.assertEqual(strategy['rag_answerable_questions'], 16)
            self.assertEqual(strategy['source_recall_at_5'], 1)
            self.assertEqual(sum(r['recall_at_5'] is None for r in strategy['results']), 4)
