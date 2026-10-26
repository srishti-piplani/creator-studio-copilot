"""Offline regressions for targeted presentation and diagnostic continuity."""
import unittest
from test_agent import make_agent, routing, assessment, reply
from app.services.resource_license import license_evidence

class Refinements(unittest.TestCase):
    def test_recording_only_followup_preserves_original_problem(self):
        agent, _ = make_agent([
            routing(goal='Why do I hear my voice twice while recording?'),
            routing(goal='Only during recording.', new_goal=True, intent='learn'),
        ], evaluations=[assessment(), {**assessment(), 'sufficient': False}], replies=[
            reply(answer='Does it happen only during recording or also during playback?', step=None,
                  diagnostic_question='Does it happen only during recording or also during playback?', status='diagnosing')])
        first = agent.chat('Why do I hear my voice twice while recording?', equipment=['Logic Pro', 'Focusrite Scarlett 2i2 — 2nd Gen'])
        second = agent.chat('Only during recording.', session_id=first['session_id'])
        self.assertEqual(second['intent'], 'troubleshoot')
        self.assertEqual(second['troubleshooting_status'], 'diagnosing')
        self.assertNotEqual(first['diagnostic_question'], second['diagnostic_question'])
        self.assertNotIn('describe the symptom', second['answer'])
        self.assertIn('direct monitoring versus software monitoring', agent.web.search.call_args.args[0])

    def test_license_requires_explicit_resource_scoped_evidence(self):
        self.assertFalse(license_evidence('Free download! Royalty free!', 'https://example.com'))
        self.assertFalse(license_evidence('Website licensed under CC0', 'https://example.com'))
        self.assertTrue(license_evidence('This sample pack is licensed under CC0 1.0.', 'https://example.com')['license_verified'])
        self.assertFalse(license_evidence('This sample pack is licensed under CC0. Excluding third-party audio.', 'https://example.com'))

    def test_how_to_puts_procedure_before_conceptual_material(self):
        agent, _ = make_agent([routing('learn', goal='How do I add a compressor in Logic Pro?',software_specific=True)],
            replies=[reply(answer='Follow the source. [W1]',citation_ids=['W1'], step=None, status='idle',
                           procedure=['Select the audio channel.', 'Insert the documented compressor.'],
                           verification='The compressor is shown in the channel insert.')])
        agent.web.search.return_value = [{'title':'Synthetic Logic Pro instructions','url':'https://support.apple.com/guide/logicpro/test/mac','source_type':'official','text':'Select the audio channel. Insert the documented compressor. The compressor is shown in the channel insert.'}]
        result = agent.chat('How do I add a compressor in Logic Pro?')
        self.assertTrue(result['answer'].startswith('## Steps'))
        self.assertIn('## Steps', result['answer'])
        self.assertNotIn('## What it means', result['answer'])
        self.assertNotIn('## What it means', result['answer'])

    def test_recording_only_answer_advances_to_evidence_supported_action(self):
        question = 'Does it happen only during recording or also during playback?'
        agent, _ = make_agent([
            routing(goal='Why do I hear my voice twice while recording?'),
            routing(goal='Only during recording.', new_goal=True, intent='learn'),
        ], replies=[reply(answer=question, diagnostic_question=question, step=None, status='diagnosing'),
                    reply(step='Check whether input monitoring is enabled in Logic Pro; its control location is not verified.',
                          action_key='compare_monitoring', why='Two active monitoring paths can produce two versions of the input.')])
        first = agent.chat('Why do I hear my voice twice while recording?', equipment=['Logic Pro', 'Focusrite Scarlett 2i2 — 2nd Gen'])
        second = agent.chat('Only during recording.', first['session_id'])
        self.assertEqual(second['troubleshooting_status'], 'awaiting_outcome')
        self.assertIn('Logic Pro', second['answer'])
        self.assertIsNone(second['diagnostic_question'])
        state = agent.session(first['session_id'])
        self.assertEqual(state['goal'], 'Why do I hear my voice twice while recording?')
        self.assertIn('Focusrite Scarlett 2i2 — 2nd Gen', state['equipment'])
