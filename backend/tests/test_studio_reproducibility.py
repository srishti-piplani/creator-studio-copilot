"""Offline build in a clean tree containing only original guides, not manuals."""
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from app.rag import studio


class StudioReproducibility(unittest.TestCase):
    def test_original_only_build_is_complete_stable_and_matches_existing_chunks(self):
        existing = {c: (studio.OUTPUT / c / 'chunks.jsonl').read_bytes()
                    for c in 'ABC' if (studio.OUTPUT / c / 'chunks.jsonl').exists()}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guides = root / 'data/studio_knowledge'
            shutil.copytree(studio.GUIDES, guides)
            output = root / 'data/studio_processed'
            (root / 'evaluations').mkdir()
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in guides.glob('*.md')}
            with patch.object(studio, 'PROJECT_ROOT', root), patch.object(studio, 'GUIDES', guides), patch.object(studio, 'OUTPUT', output):
                report = studio.prepare_studio()
                first = {c: (output / c / 'chunks.jsonl').read_bytes() for c in 'ABC'}
                self.assertEqual(studio.prepare_studio(), report)
                self.assertEqual(first, {c: (output / c / 'chunks.jsonl').read_bytes() for c in 'ABC'})
            self.assertFalse((root / 'data/corpus').exists())
            self.assertFalse((root / 'data/processed').exists())
            self.assertEqual(report['guides'], 12)
            self.assertEqual(report['chunk_counts'], {'A':36, 'B':24, 'C':12})
            self.assertTrue(report['same_retained_text'])
            self.assertNotIn('manual_phrase_overlap', report)
            self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in guides.glob('*.md')})
            for strategy, old_bytes in existing.items():
                self.assertEqual(first[strategy], old_bytes)
            self.assertEqual(len([json.loads(line) for line in (output / 'sections.jsonl').read_text().splitlines()]), 12)
