"""Synthetic-only cleaning and provenance regression tests."""

import unittest

from app.rag.chunking import CONFIGURATIONS, approximate_token_count, chunk_sections, word_windows
from app.rag.ingest import Document
from app.rag.preprocessing import clean_section, heading_match, repeated_edges, stable_id


def metadata():
    return {'document_id': 'synthetic-doc', 'source_id': 'synthetic-doc',
            'section_id': 'synthetic-section', 'section_title': 'Synthetic recording procedure',
            'product': 'Logic Pro', 'software_version': 'test-only', 'version': 'test-only',
            'source_url': None, 'document_title': 'SYNTHETIC TEST ONLY',
            'headings': ['Synthetic recording procedure']}


class PreprocessingTests(unittest.TestCase):
    def test_repeated_multiline_edges_and_page_provenance(self):
        pages = {n: f'{n}\nSynthetic repeated document header\n\nUnique body on page {n}.\n\nSynthetic repeated footer\n{n}'
                 for n in (1, 2, 3)}
        exclusions = []
        sections = clean_section(pages, metadata(), repeated_edges(pages), exclusions)
        self.assertEqual(len(sections), 1)
        self.assertNotIn('header', sections[0].text)
        self.assertNotIn('footer', sections[0].text)
        self.assertEqual([s['page'] for s in sections[0].metadata['page_spans']], [1, 2, 3])
        self.assertTrue(any(e['reason'] == 'repeated_header_footer' for e in exclusions))
        for config in CONFIGURATIONS:
            for chunk in chunk_sections(sections, config):
                self.assertEqual(chunk.metadata['document_id'], 'synthetic-doc')
                self.assertEqual(chunk.metadata['software_version'], 'test-only')
                self.assertEqual(chunk.metadata['section_title'], metadata()['section_title'])
                self.assertTrue(set(chunk.metadata['pages']) <= {1, 2, 3})
                self.assertEqual(chunk.metadata['page_start'], min(chunk.metadata['pages']))
                self.assertEqual(chunk.metadata['page_end'], max(chunk.metadata['pages']))

    def test_corruption_is_quarantined_not_guessed_and_safe_text_survives(self):
        source = 'Verified intact sentence.\n\nSet level to 4\ufffd dB.\n\nAnother intact sentence.'
        exclusions = []
        sections = clean_section({7: source}, metadata(), set(), exclusions)
        self.assertEqual([s.text for s in sections], ['Verified intact sentence.', 'Another intact sentence.'])
        self.assertEqual(exclusions[0]['pages'], [7])
        self.assertEqual(exclusions[0]['document_id'], 'synthetic-doc')
        self.assertTrue(exclusions[0]['technical_risk'])
        self.assertEqual(exclusions[0]['replacement_characters'], 1)
        self.assertNotIn('4 dB', ' '.join(s.text for s in sections))
        # No fabricated/reconstructed text: cleaning only removed the marked source passage.
        self.assertEqual('\n\n'.join(s.text for s in sections), source.replace('Set level to 4\ufffd dB.\n\n', ''))

    def test_exact_duplicate_detection_retains_original_reference(self):
        paragraph = 'Synthetic test paragraph, entirely invented for tests. ' * 4
        exclusions = []
        sections = clean_section({2: paragraph + '\n\n' + paragraph}, metadata(), set(), exclusions)
        self.assertEqual(sum(s.text.count('Synthetic test paragraph') for s in sections), 4)
        duplicate = next(e for e in exclusions if e['reason'] == 'exact_duplicate_passage')
        self.assertEqual(duplicate['duplicate_of']['page'], 2)

    def test_passage_review_fails_closed_with_page_and_fingerprint(self):
        approved = 'A complete synthetic source instruction for testing.'
        excluded = 'Synthetic setting contains an ambiguous symµbol.'
        unknown = 'A new passage that has never been reviewed.'
        meta = metadata()
        meta['passage_review'] = [
            {'content_sha256': stable_id(approved), 'page': 8, 'heading': 'Synthetic heading',
             'decision': 'include', 'reason': 'Synthetic test approval.'},
            {'content_sha256': stable_id(excluded), 'page': 8, 'heading': 'Synthetic heading',
             'decision': 'exclude', 'reason': 'Ambiguous glyph in synthetic text.'}]
        exclusions = []
        sections = clean_section({8: '\n\n'.join([approved, excluded, unknown])}, meta, set(), exclusions)
        self.assertEqual([s.text for s in sections], [approved])
        self.assertEqual(len(exclusions), 2)
        self.assertTrue(all(e['reason']=='passage_review_quarantine' for e in exclusions))
        span = sections[0].metadata['page_spans'][0]
        self.assertEqual(span['page'], 8)
        self.assertEqual(span['heading'], 'Synthetic heading')
        self.assertEqual(span['review_status'], 'approved')
        self.assertNotIn('passage_review', sections[0].metadata)
        self.assertEqual(clean_section({9: approved}, meta, set(), []), [])
        self.assertEqual(clean_section({8: approved + ' Changed.'}, meta, set(), []), [])

    def test_source_coverage_rejects_omission_and_rewritten_chunk_body(self):
        from app.rag.prepare import verify_source_coverage
        sections = clean_section({2: 'Synthetic recording procedure\n' + 'Whole source sentence. ' * 70},
                                 metadata(), set(), [])
        for configuration in CONFIGURATIONS:
            chunks = chunk_sections(sections, configuration)
            self.assertTrue(verify_source_coverage(sections, chunks))
            with self.assertRaises(ValueError):
                verify_source_coverage(sections, chunks[:-1])
            changed = [Document(c.text + ' Altered.', c.metadata) for c in chunks]
            with self.assertRaises(ValueError):
                verify_source_coverage(sections, changed)

    def test_windows_preserve_whole_words(self):
        text = ' '.join('extraordinaryWord' + str(n) for n in range(60))
        for start, end in word_windows(text, 30, 5):
            self.assertTrue(start == 0 or text[start-1].isspace())
            self.assertTrue(end == len(text) or text[end].isspace())
            self.assertLessEqual(approximate_token_count(text[start:end]), 30)
        long_word = 'z' * 4000
        self.assertEqual(word_windows(long_word, 300, 45), [(0, 4000)])

    def test_numbered_procedure_stays_together(self):
        text = ('Synthetic recording procedure\n\nWarning: synthetic instructions only.\n'
                '1. Connect the imaginary cable.\n2. Select the pretend input.\n'
                '3. Start the fictional recording.\n4. Stop and inspect the test signal.')
        sections = clean_section({5: text}, metadata(), set(), [])
        chunks = chunk_sections(sections, 'C')
        self.assertEqual(len(chunks), 1)
        self.assertIn(text, chunks[0].text)
        self.assertIn('Warning:', chunks[0].text)

    def test_short_procedure_after_long_setup_is_not_split(self):
        setup = 'Synthetic setup guidance. ' * 350
        procedure = ('Record a synthetic signal\n1. Connect the imaginary cable.\n'
                     '2. Select the pretend input.\n3. Start the fictional recording.\n'
                     '4. Stop the test recording.')
        sections = clean_section({1: setup + '\n' + procedure}, metadata(), set(), [])
        chunks = chunk_sections(sections, 'C')
        self.assertTrue(any(procedure in chunk.text for chunk in chunks))

    def test_long_procedure_keeps_source_context_and_all_source_words(self):
        text = 'Synthetic recording procedure\nWarning: test only.\n' + '\n'.join(
            f'{n}. ' + 'Synthetic step content with imaginary settings. ' * 20 for n in range(1, 15))
        sections = clean_section({4: text}, metadata(), set(), [])
        chunks = chunk_sections(sections, 'C')
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.metadata['context_repeated'] for c in chunks))
        self.assertTrue(all('Warning: test only.' in c.text for c in chunks))
        self.assertTrue(all(c.metadata['token_count'] <= 800 for c in chunks))
        bodies = [sections[0].text[c.metadata['body_start']:c.metadata['body_end']] for c in chunks]
        self.assertEqual(' '.join(' '.join(bodies).split()), ' '.join(text.split()))

    def test_determinism_equal_coverage_and_no_word_splitting_in_all_configs(self):
        sections = clean_section({3: 'Synthetic recording procedure\n' + 'WholeWord repeated test content. ' * 200,
                                  4: 'Another complete synthetic sentence.'}, metadata(), set(), [])
        expected_ids = {s.metadata['section_id'] for s in sections}
        for config in CONFIGURATIONS:
            chunks = chunk_sections(sections, config)
            self.assertEqual(chunks, chunk_sections(sections, config))
            self.assertEqual({c.metadata['section_id'] for c in chunks}, expected_ids)
            self.assertEqual(len({c.metadata['chunk_id'] for c in chunks}), len(chunks))
            self.assertTrue(all(c.metadata['token_count'] <= CONFIGURATIONS[config]['target'] for c in chunks))
            for section in sections:
                covered = set()
                for chunk in chunks:
                    if chunk.metadata['section_part'] != section.metadata['section_part']:
                        continue
                    a,b = chunk.metadata['body_start'], chunk.metadata['body_end']
                    self.assertTrue(a == 0 or section.text[a-1].isspace())
                    self.assertTrue(b == len(section.text) or section.text[b].isspace())
                    covered.update(range(a,b))
                self.assertTrue(all(i in covered for i,c in enumerate(section.text) if not c.isspace()))

    def test_heading_wrap_and_small_fragment_merging(self):
        self.assertIsNotNone(heading_match('Synthetic\nrecording procedure\nBody.', 'Synthetic recording procedure'))
        text = 'Synthetic recording procedure\n\n' + 'Related complete sentence. ' * 150
        chunks = chunk_sections(clean_section({1: text}, metadata(), set(), []), 'C')
        self.assertTrue(all(c.metadata['token_count'] >= 50 for c in chunks))


if __name__ == '__main__':
    unittest.main()
