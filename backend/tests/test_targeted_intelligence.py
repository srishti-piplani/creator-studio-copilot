"""Focused Phase 4D regressions. Scripted providers; no external calls."""
import json
import unittest
from unittest.mock import Mock
from app.graph.context import studio_context, context_issues
from app.graph.workflow import Reply
from app.graph.answers import resource_usage
from app.services.evidence_evaluator import evaluate
from test_agent import make_agent, routing, assessment, reply

SETUP = ['Logic Pro (documentation reference 12.3; installed version unknown)',
         'DaVinci Resolve (documentation reference 21.1; installed version unknown)',
         'Focusrite Scarlett 2i2 — 2nd Gen', 'Audio-Technica AT2035']

class TargetedIntelligenceTests(unittest.TestCase):
    def test_configured_logic_is_not_reasked_and_reference_is_not_installed_version(self):
        state = {'equipment': SETUP, 'goal': 'My voice is doubled while recording', 'messages': [],
                 'intent': 'troubleshoot', 'steps': [], 'evidence': [], 'version': None}
        model = Mock(spec=['complete'])
        model.complete.return_value = {**assessment(), 'clarification_needed': True,
                                       'clarification_question': 'Which DAW are you using?'}
        result = evaluate(model, state)
        self.assertFalse(result['clarification_needed'])
        self.assertTrue(result['web_needed'])
        payload = json.loads(model.complete.call_args.args[0][1]['content'].split('\n', 1)[1])
        self.assertEqual(payload['studio_context']['primary_software'], 'Logic Pro')
        self.assertEqual(payload['studio_context']['documentation_versions']['Logic Pro'], '12.3')
        self.assertIsNone(payload['studio_context']['installed_software_version'])

    def test_usb_transport_is_known_and_thunderbolt_draft_is_blocked(self):
        state = {'equipment': SETUP, 'goal': 'Recording fails', 'messages': []}
        self.assertEqual(studio_context(state)['interface_connection'], 'USB (not Thunderbolt)')
        self.assertTrue(context_issues(Reply(**reply(step='Reconnect the Thunderbolt cable.')), state))
        agent, _ = make_agent([routing(goal='Recording fails', equipment=[])], replies=[
            reply(step='Reconnect the Thunderbolt cable.'), reply(step='Reconnect the Thunderbolt cable.')])
        result = agent.chat('Recording fails', equipment=SETUP)
        self.assertNotIn('Thunderbolt', result['answer'])
        self.assertEqual(result['troubleshooting_status'], 'unsupported')

    def test_known_setup_reaches_generation_and_official_research(self):
        agent, model = make_agent([routing(goal='My voice is doubled', equipment=[])], replies=[reply(
            step='In Logic Pro, check the input meter.', why='This distinguishes missing input from a monitoring-only issue.')])
        result = agent.chat('My voice is doubled', equipment=SETUP)
        state = agent.session(result['session_id'])
        self.assertIn('Focusrite Scarlett 2i2 — 2nd Gen', state['equipment'])
        self.assertIn('Logic Pro', agent.web.search.call_args.args[0])
        self.assertTrue(agent.web.search.call_args.kwargs['official_only'])
        self.assertIn('Logic Pro', result['answer'])
        generation = next(c for c in model.calls if 'Respond as Creator Studio Copilot using ONLY' in c[0]['content'])
        payload = json.loads(generation[1]['content'].split('\n', 1)[1])
        self.assertIn('Audio-Technica AT2035', payload['studio_context']['equipment'])

    def test_short_clarifications_cannot_replace_the_active_topic(self):
        routes = [routing(goal='Why do I hear my voice twice while recording?', equipment=[])] + [
            routing(goal=text, new_goal=True, equipment=[]) for text in ['Logic Pro', 'USB', 'Yes', 'No', "That didn't work"]]
        agent, _ = make_agent(routes)
        first = agent.chat('Why do I hear my voice twice while recording?', equipment=SETUP)
        for text in ['Logic Pro', 'USB', 'Yes', 'No', "That didn't work"]:
            response = agent.chat(text, first['session_id'])
            self.assertEqual(response['topic_title'], 'Why do I hear my voice twice while recording?')
            self.assertFalse(response['new_topic'])

    def test_explicit_equipment_change_overrides_saved_default(self):
        agent, _ = make_agent([routing(equipment=['Audio-Technica AT2020', 'Focusrite Scarlett Solo — 4th Gen'])])
        response = agent.chat('I am using AT2020 and Scarlett Solo today', equipment=SETUP)
        equipment = agent.session(response['session_id'])['equipment']
        self.assertNotIn('Audio-Technica AT2035', equipment)
        self.assertNotIn('Focusrite Scarlett 2i2 — 2nd Gen', equipment)

    def test_tutorial_viewing_and_sample_reuse_have_different_labels(self):
        for question, title, usage in [('Find vocal-mixing tutorials in Logic Pro', 'Vocal mixing tutorial', 'view'),
                                       ('Find tabla loops for my cover', 'Tabla loops', 'reuse')]:
            agent, _ = make_agent([routing('discover', goal=question)], replies=[reply(
                citation_ids=['W1'], step=None, status='idle')])
            agent.web.search.return_value[0]['title'] = title
            response = agent.chat(question, equipment=SETUP)
            card = response['resource_cards'][0]
            self.assertEqual(card['usage'], usage)
            if usage == 'view':
                self.assertNotIn('license', card)
                self.assertNotIn('Usage permissions', response['answer'])
            else:
                self.assertEqual(card['license'], 'License not verified.')
        self.assertEqual(resource_usage('Redistribute tutorial videos'), 'reuse')

    def test_explicit_software_choice_survives_later_short_answers(self):
        agent, _ = make_agent([routing(goal='Double monitoring in Logic Pro', equipment=[]),
                              routing(goal='DaVinci Resolve', new_goal=True, equipment=[]),
                              routing(goal='USB', new_goal=True, equipment=[])])
        first = agent.chat('Double monitoring in Logic Pro', equipment=SETUP)
        agent.chat('DaVinci Resolve', first['session_id'])
        agent.chat('USB', first['session_id'])
        state = agent.session(first['session_id'])
        self.assertEqual(studio_context(state)['primary_software'], 'DaVinci Resolve')
        self.assertEqual(state['goal'], 'Double monitoring in Logic Pro')

    def test_generic_monitoring_toggle_is_not_a_verified_control_location(self):
        state = {'equipment': SETUP, 'goal': 'Double monitoring', 'messages': []}
        self.assertTrue(context_issues(Reply(**reply(step='Disable software monitoring in your DAW.')), state))
        agent, _ = make_agent([routing(goal='Double monitoring', equipment=[])], replies=[
            reply(step='Disable software monitoring in your DAW.'),
            reply(step='Disable software monitoring in your DAW.')])
        result = agent.chat('Double monitoring', equipment=SETUP)
        self.assertNotIn('Disable software monitoring in your DAW', result['answer'])
        self.assertIn("control's location in Logic Pro", result['answer'])
        self.assertEqual(result['troubleshooting_status'], 'unsupported')


    def test_model_cannot_promote_documentation_reference_to_installed_version(self):
        agent, _ = make_agent([routing(goal='Recording issue', equipment=[], version='12.3'),
                              routing(goal='Recording issue', equipment=[], version='11.2')])
        first = agent.chat('Recording issue', equipment=SETUP)
        self.assertIsNone(agent.session(first['session_id'])['version'])
        agent.chat('I use Logic Pro 11.2', first['session_id'])
        self.assertEqual(agent.session(first['session_id'])['version'], '11.2')
