"""Local tests using only synthetic content, including a generated minimal PDF."""

import json
from pathlib import Path
import tempfile
import unittest

from app.rag.chunking import TOKEN, approximate_token_count, chunk_documents
from app.rag.ingest import Document, clean_pdf_pages, clean_text, load_documents

FIXTURES = Path(__file__).parent / 'fixtures'


class IngestionTests(unittest.TestCase):
    def fixture_documents(self):
        return load_documents(FIXTURES / 'corpus', FIXTURES / 'sources.json', allowed_products=('Synthetic Test Device',))

    def test_fixture_metadata_and_stable_ids(self):
        documents = self.fixture_documents()
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents, self.fixture_documents())
        self.assertIn('SYNTHETIC TEST FIXTURE', documents[0].text)
        for strategy in ('fixed', 'structure'):
            chunks = chunk_documents(documents, strategy)
            self.assertEqual(chunks, chunk_documents(self.fixture_documents(), strategy))
            for chunk in chunks:
                for key, value in documents[0].metadata.items():
                    self.assertEqual(chunk.metadata[key], value)
                self.assertEqual(chunk.metadata['chunking_strategy'], strategy)
                self.assertEqual(len(chunk.metadata['chunk_id']), 64)
        self.assertEqual(documents[0].metadata['hardware_generation'], 'fictional-v1')

    def test_text_markdown_empty_and_pdf_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'sources.json').write_text(json.dumps([
                {'path': 'note.txt', 'product': 'Synthetic', 'topic': 'Test',
                 'document_title': 'Synthetic note', 'source_url': 'https://example.invalid/test',
                 'software_version': 'test-1'},
                {'path': 'note.md', 'product': 'Synthetic'},
                {'path': 'synthetic.pdf', 'product': 'Synthetic'}]))
            (root / 'note.txt').write_text('  Synthetic   text  \n\n\n Second paragraph. ')
            (root / 'note.md').write_text('# Synthetic heading\n\nParagraph.')
            (root / 'empty.txt').write_text(' \n\t ')
            (root / 'ignored.csv').write_text('not loaded')
            # Minimal synthetic PDF assembled locally; no manual or download needed.
            stream = b'BT /F1 12 Tf 72 720 Td (Synthetic PDF only) Tj ET'
            objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
                       b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                       b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
                       b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
                       b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
            pdf = b'%PDF-1.4\n'
            offsets = [0]
            for number, obj in enumerate(objects, 1):
                offsets.append(len(pdf))
                pdf += str(number).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
            xref = len(pdf)
            pdf += b'xref\n0 6\n0000000000 65535 f \n'
            pdf += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
            pdf += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
            (root / 'synthetic.pdf').write_bytes(pdf)
            docs = load_documents(root, root / 'sources.json', allowed_products=('Synthetic',))
            self.assertEqual(len(docs), 3)
            self.assertTrue(any('Synthetic PDF only' in doc.text for doc in docs))
            note = next(doc for doc in docs if doc.metadata['document_title'] == 'Synthetic note')
            self.assertEqual(note.metadata['software_version'], 'test-1')
            self.assertEqual(note.text, 'Synthetic text\n\nSecond paragraph.')
            self.assertEqual(len({doc.metadata['document_id'] for doc in docs}), 3)

    def test_cleaning(self):
        self.assertEqual(clean_text('  a\t b\n\n\n c '), 'a b\n\nc')
        pages = [f'SYNTHETIC HEADER\nUnique body {i}\nPage {i}' for i in range(1, 4)]
        text = clean_pdf_pages(pages)
        self.assertNotIn('HEADER', text)
        self.assertNotIn('Page ', text)
        self.assertIn('Unique body 3', text)
        self.assertEqual(clean_pdf_pages(['', '']), '')

    def test_fixed_overlap_size_and_content(self):
        text = ' '.join(f'word{i}' for i in range(900))
        doc = Document(text, {'document_id': 'synthetic'})
        chunks = chunk_documents([doc])
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(approximate_token_count(c.text) <= 500 for c in chunks))
        left, right = chunks[0].text.split(), chunks[1].text.split()
        overlap = next(n for n in range(min(len(left), len(right)), 0, -1)
                       if left[-n:] == right[:n])
        self.assertLessEqual(approximate_token_count(' '.join(left[-overlap:])), 75)
        self.assertGreater(approximate_token_count(' '.join(left[-overlap:])), 65)
        self.assertTrue(text.endswith(chunks[-1].text))
        self.assertEqual(len(chunks), len({c.metadata['chunk_id'] for c in chunks}))
        changed = chunk_documents([Document(text + ' changed', doc.metadata)])
        self.assertNotEqual(chunks[-1].metadata['chunk_id'], changed[-1].metadata['chunk_id'])

    def test_structure_keeps_instructions_and_headings(self):
        text = '# Setup\n\n1. Connect cable.\n2. Select input.\n\nRelated paragraph.\n\n# Meter\n\nObserve level.'
        chunks = chunk_documents([Document(text, {'document_id': 'test'})], 'structure', 30, 5)
        self.assertIn('# Setup\n\n1. Connect cable.\n2. Select input.\n\nRelated paragraph.', chunks[0].text)
        long = Document('# Heading\n\n' + 'Synthetic paragraph. ' * 300, {'document_id': 'long'})
        chunks = chunk_documents([long], 'structure')
        self.assertTrue(all(approximate_token_count(c.text) <= 500 for c in chunks))
        self.assertIn('paragraph.', chunks[-1].text)

    def test_mvp_allowlist_and_unavailable_products(self):
        from app.rag.ingest import product_coverage
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entries = []
            for directory, product in [('logic_pro', 'Logic Pro'),
                                       ('garageband', 'GarageBand'),
                                       ('imovie', 'iMovie'),
                                       ('other', 'Unknown'),
                                       ('empty', 'DaVinci Resolve')]:
                (root / directory).mkdir()
                (root / directory / 'test.txt').write_text(
                    '' if directory == 'empty' else 'Synthetic scope test only.')
                entries.append({'path': f'{directory}/test.txt', 'product': product})
            (root / 'unlisted.txt').write_text('Unlisted synthetic source.')
            (root / 'sources.json').write_text(json.dumps(entries))
            docs = load_documents(root, root / 'sources.json')
            self.assertEqual([doc.metadata['product'] for doc in docs], ['Logic Pro'])
            coverage = product_coverage(docs)
            self.assertEqual(coverage['Logic Pro'], 'available')
            self.assertEqual(coverage['DaVinci Resolve'], 'unavailable')
            self.assertNotIn('GarageBand', coverage)
            self.assertNotIn('iMovie', coverage)
            # Folder exclusions also hold if a manifest mislabels an excluded file.
            entries[1]['product'] = 'Logic Pro'
            entries[2]['product'] = 'Logic Pro'
            (root / 'sources.json').write_text(json.dumps(entries))
            self.assertEqual(load_documents(root, root / 'sources.json'), docs)
            self.assertEqual(load_documents(FIXTURES / 'corpus', FIXTURES / 'sources.json'), [])

    def test_invalid_settings_and_empty_content(self):
        self.assertEqual(chunk_documents([Document('', {'document_id': 'empty'})]), [])
        for kwargs in ({'strategy': 'other'}, {'chunk_size': 0}, {'overlap': 500}):
            with self.assertRaises(ValueError):
                chunk_documents([], **kwargs)


if __name__ == '__main__':
    unittest.main()
