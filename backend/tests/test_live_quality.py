"""Regressions from Phase 4I actual generated outputs (no provider calls)."""
import unittest
from app.graph.answers import LearnAnswer, insertion_scope_issues, resource_description

class LiveQuality(unittest.TestCase):
    def test_insert_only_rejects_tuning_and_unrequested_recipe(self):
        state={'goal':'How do I add a compressor to an audio track in Logic Pro?', 'how_to':True}
        draft=LearnAnswer(takeaway='Insert the effect.', procedure=['Select the track.', 'Set Threshold to -20 dB.'])
        self.assertTrue(insertion_scope_issues(draft,state))
        draft=LearnAnswer(takeaway='Insert the effect.', procedure=['Select the track.', 'Choose the effect in its documented menu.'])
        self.assertFalse(insertion_scope_issues(draft,state))
        self.assertFalse(insertion_scope_issues(draft,{'goal':'Configure compressor settings', 'how_to':True}))

    def test_insertion_success_does_not_require_gain_reduction(self):
        draft=LearnAnswer(takeaway='Insert the effect.', procedure=['Select Compressor.'], verification='The gain reduction meter shows activity.')
        self.assertTrue(insertion_scope_issues(draft,{'goal':'Add a compressor to an audio track', 'how_to':True}))

    def test_discovery_relevance_cannot_imply_legal_clearance(self):
        for text in ['This ensures legal safety for distribution on YouTube.', 'Its availability on Splice ensures compliance with usage terms for YouTube distribution.', 'This supports legal use in a YouTube cover, though users must verify the up']:
            self.assertEqual(resource_description(text), 'Open the source to review the resource details.')
