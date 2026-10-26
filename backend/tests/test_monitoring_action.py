"""Exact questionnaire regression; scripted boundaries, real graph and state."""
import unittest
from unittest.mock import Mock

from app.graph.monitoring import REFERENCE, MONITORING_ACTION_KEY, isolation_test
from app.graph.workflow import StudioAgent
from test_agent import make_agent, routing, reply
from test_creative_monitoring import SECTION


class MonitoringAction(unittest.TestCase):
    def test_delayed_double_voice_advances_to_isolation_not_empty_project(self):
        headphones = 'Where are your headphones connected?'
        delay = 'Does one copy of your voice sound slightly delayed?'
        empty = 'Does it also happen in a new empty project?'
        routes = [routing(goal='Voice twice while recording') for _ in range(4)]
        base, model = make_agent(routes, replies=[
            reply(answer=headphones, diagnostic_question=headphones, step=None, status='diagnosing'),
            reply(answer=delay, diagnostic_question=delay, step=None, status='diagnosing'),
            reply(answer=empty, diagnostic_question=empty, step=None, status='diagnosing'),
        ])
        web = Mock(spec=['search', 'fetch'])
        web.search.return_value = base.web.search.return_value
        # First two turns reproduce the observed questions. The official control
        # excerpt becomes available on the action turn, as real research can do.
        reads = []
        def fetch(url, **kwargs):
            if url == REFERENCE:
                reads.append(url)
            return {'url':url, 'text': SECTION if len(reads) >= 3 and url == REFERENCE else 'No applicable control excerpt.'}
        web.fetch.side_effect = fetch
        agent = StudioAgent(base.rag, web, chat=model)
        first = agent.chat('Why do I hear my voice twice while recording?', equipment=[
            'Logic Pro', 'Focusrite Scarlett 2i2 — 2nd Gen', 'Audio-Technica AT2035'])
        session = first['session_id']
        self.assertEqual(first['diagnostic_question'], headphones)
        self.assertEqual(agent.chat('Scarlett interface.', session)['diagnostic_question'], delay)
        result = agent.chat('Yes.', session)
        self.assertEqual(result['troubleshooting_status'], 'awaiting_outcome')
        self.assertIn('temporarily switch it OFF', result['answer'])
        self.assertIn('leave Logic Pro unchanged', result['answer'])
        self.assertIn('possible cause, not a confirmed diagnosis', result['answer'])
        self.assertIn('change the doubled voice', result['answer'])
        self.assertNotIn('empty project', result['answer'])
        self.assertEqual(result['citations'][0]['url'], REFERENCE)
        state = agent.session(session)
        self.assertEqual(state['goal'], 'Voice twice while recording')
        self.assertEqual(state['steps'][0]['action_key'], MONITORING_ACTION_KEY)
        self.assertEqual(state['steps'][0]['outcome'], 'pending')
        self.assertEqual(len(model.replies), 1)  # Third-question draft was never requested.
        print('\nActual regression response:\n' + result['answer'])
        pending = agent.chat('I have not tried it yet.', session)
        self.assertEqual(pending['troubleshooting_status'], 'awaiting_outcome')
        self.assertNotIn('empty project', pending['answer'])
        self.assertEqual(len(agent.session(session)['steps']), 1)
        # Failed/previous actions, conflicts and missing control proof cannot
        # re-enter this action path or cause guessed hardware instructions.
        for change in [ {'steps':[dict(state['steps'][0], outcome='failed')]},
                        {'steps':[], 'evaluation':{'contradictory':True}},
                        {'steps':[], 'evidence':[]} ]:
            self.assertIsNone(isolation_test({**state, **change}))

    def test_switch_on_followup_preserves_context_and_tracks_both_outcomes(self):
        from app.graph.monitoring import SWITCH_QUESTION, switch_reply
        for answer in ["It's ON.", 'On', "Yes, it's on", 'The switch is enabled']:
            for outcome, expected in [('That fixed it', 'resolved'), ('Still doubled', 'failed')]:
                with self.subTest(answer=answer, outcome=outcome):
                    # Deliberately wrong router output verifies that the pending
                    # question/action, not a model guess or isolated phrase, owns the reply.
                    base, model = make_agent([
                        routing(goal='Voice twice while recording'),
                        routing('clarify', goal=answer, new_goal=True),
                        routing('learn', goal=outcome, new_goal=True),
                    ], replies=[reply(answer='Does the recorded clip itself contain two voices?',
                                      diagnostic_question='Does the recorded clip itself contain two voices?',
                                      step=None, status='diagnosing')])
                    web = Mock(spec=['search', 'fetch'])
                    web.search.return_value = base.web.search.return_value
                    web.fetch.side_effect = lambda url, **kw: {'url':url, 'text':SECTION if url == REFERENCE else 'Synthetic evidence.'}
                    agent = StudioAgent(base.rag, web, chat=model)
                    first = agent.chat('Why do I hear my voice twice while recording?', equipment=[
                        'Logic Pro', 'Focusrite Scarlett 2i2 — 2nd Gen', 'Audio-Technica AT2035'])
                    self.assertEqual(first['diagnostic_question'], SWITCH_QUESTION)
                    session = first['session_id']
                    result = agent.chat(answer, session)
                    self.assertEqual(result['troubleshooting_status'], 'awaiting_outcome')
                    self.assertIn('Temporarily turn DIRECT MONITOR OFF', result['answer'])
                    self.assertIn('Leave Logic Pro unchanged', result['answer'])
                    self.assertNotIn('If it is ON', result['answer'])
                    self.assertNotIn('already OFF', result['answer'])
                    self.assertEqual(result['diagnostic_question'], 'Did the doubling disappear?')
                    self.assertNotIn('headphones', result['answer'].lower())
                    self.assertEqual(agent.session(session)['steps'][0]['outcome'], 'pending')
                    self.assertEqual(agent.session(session)['goal'], 'Voice twice while recording')
                    followup = agent.chat(outcome, session)
                    state = agent.session(session)
                    self.assertEqual(state['steps'][0]['outcome'], expected)
                    self.assertEqual(len(state['steps']), 1)
                    self.assertEqual(state['goal'], 'Voice twice while recording')
                    if expected == 'resolved':
                        self.assertEqual(followup['troubleshooting_status'], 'resolved')
                    else:
                        self.assertEqual(followup['troubleshooting_status'], 'diagnosing')
                        self.assertNotIn('temporarily switch it OFF', followup['answer'])
                    unrelated = dict(state, status='diagnosing', steps=[],
                        questions_asked=['Is your microphone connected?'], messages=[
                            {'role':'assistant','content':'Is your microphone connected?'},
                            {'role':'user','content':answer}])
                    self.assertIsNone(switch_reply(unrelated))
                    self.assertIsNone(isolation_test(unrelated))

    def test_confirmed_on_action_is_concise_cited_and_pending(self):
        base, _ = make_agent([])
        from app.graph.provenance import provenance
        from app.graph.monitoring import SWITCH_QUESTION
        proof = provenance({'id':'W1', 'title':'Focusrite Scarlett 2i2 instructions',
            'url':REFERENCE, 'text':SECTION, 'hardware_generation':'2nd Gen'},
            'Focusrite Scarlett 2i2')
        state = dict(intent='troubleshoot', goal='Voice twice while recording',
            equipment=['Logic Pro','Focusrite Scarlett 2i2 — 2nd Gen'],
            status='diagnosing', questions_asked=[SWITCH_QUESTION],
            messages=[{'role':'assistant','content':SWITCH_QUESTION},
                      {'role':'user','content':"it's ON."}], steps=[],
            evidence=[proof], citations=[dict(proof)], activities=[], session_id='test')
        result = base._monitoring_action_reply(state)
        answer = result['response']['answer']
        self.assertIn('Temporarily turn DIRECT MONITOR OFF', answer)
        self.assertNotIn('If', answer)
        self.assertNotIn('already OFF', answer)
        self.assertIn('possible cause, not a confirmed diagnosis', answer)
        self.assertEqual(result['steps'][0]['outcome'], 'pending')
        self.assertEqual(result['response']['citations'][0]['url'], REFERENCE)
        self.assertEqual(result['response']['diagnostic_question'], 'Did the doubling disappear?')
