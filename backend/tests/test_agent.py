"""Offline graph scenarios: real LangGraph/checkpointer, scripted provider boundaries."""
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import httpx
from fastapi.testclient import TestClient

from app.graph.workflow import StudioAgent
from app.graph.router import structured
from app.graph.state import Route
from app.rag.generate import ChatError
from app.tools.web_search import KeenableSearch, WebSearchError, official_source
from app.main import app


def routing(intent='troubleshoot', outcome='unknown', **kwargs):
    result = dict(intent=intent, goal='Microphone has no signal', equipment=['Logic Pro'],
                  software_specific=False, outcome=outcome)
    result.update(kwargs)
    return result


def assessment(**kwargs):
    return dict(sufficient=True, product_relevant=True, version_relevant=True,
                clarification_needed=False, web_needed=False, contradictory=False,
                reason='Scripted synthetic evidence', **kwargs)


def reply(**kwargs):
    result = dict(answer='Check the input connection. [K1]', citation_ids=['K1'],
                  step='Check the input connection.', action_key='check_connection',
                  status='awaiting_outcome')
    result.update(kwargs)
    return result


class ScriptedChat:
    def __init__(self, routes, evaluations=None, replies=None):
        self.routes = list(routes)
        self.evaluations = list(evaluations or [assessment()] * 20)
        self.replies = list(replies or [reply()] * 20)
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        instruction = messages[0]['content']
        if 'Classify the user' in instruction:
            return self.routes.pop(0)
        if 'Assess whether evidence' in instruction:
            return self.evaluations.pop(0)
        if 'Review only whether the retained source instructions' in instruction:
            payload = json.loads(messages[1]['content'].split('\n', 1)[1])
            return {'essential_complete': all(payload['valid_spans']), 'unresolved_conflict': False,
                    'keep_indices': [i for i, valid in enumerate(payload['valid_spans']) if valid], 'check_supported': True}
        if 'Extract the shortest complete procedure' in instruction:
            result = self.replies.pop(0)
            steps = result.get('procedure', [])
            return {'status': 'supported' if steps else 'insufficient_evidence',
                    'procedure': [{'source_id': (result.get('citation_ids') or ['K1'])[0], 'quote': text} for text in steps] or None,
                    'success_check': {'source_id': (result.get('citation_ids') or ['K1'])[0], 'quote': result['verification']} if result.get('verification') else None,
                    'missing_evidence': None}
        if 'Review the draft' in instruction:
            return {'supported': True, 'complete': True, 'verification_supported': True, 'issues': []}
        result = self.replies.pop(0)
        if '"resource_ids":' in instruction:
            return {'resource_ids': result.get('citation_ids', []), 'relevance': []}
        if '"takeaway":' in instruction and '"key_points":' in instruction:
            return {'takeaway': result['answer'], 'key_points': [],
                    'citation_ids': result.get('citation_ids', []),
                    'procedure': result.get('procedure', []), 'verification': result.get('verification')}
        return result


def make_agent(routes, evaluations=None, replies=None):
    chat = ScriptedChat(routes, evaluations, replies)
    rag = Mock()
    rag.chat = chat
    rag.retrieve.return_value = {'evidence': [{'id': 'S1', 'text': 'Synthetic conceptual evidence.', 'guide_title': 'Synthetic test guide'}],
        'citations': {'S1': {'id': 'S1', 'guide_title': 'Synthetic test guide',
                            'guide_path': 'synthetic-only', 'reference_urls': []}}}
    web = Mock(spec=['search'])
    web.search.return_value = [{'title': 'Synthetic official result',
        'url': 'https://support.apple.com/synthetic-test', 'source': 'support.apple.com',
        'source_type': 'official', 'text': 'Synthetic test evidence.',
        'description': 'Synthetic test fixture only.', 'license': 'License not verified.'}]
    return StudioAgent(rag, web), chat


class AgentScenarios(unittest.TestCase):
    def test_learn_citations(self):
        agent, _ = make_agent([routing('learn')], replies=[reply(step=None, status='idle')])
        result = agent.chat('Explain input gain')
        self.assertEqual(result['intent'], 'learn')
        self.assertEqual(result['citations'][0]['id'], 'K1')
        self.assertIn('[K1]', result['answer'])
        agent.web.search.assert_not_called()

    def test_diagnostic_progression(self):
        agent, _ = make_agent([routing(), routing()], replies=[
            reply(step=None, diagnostic_question='Does the input meter move?', status='diagnosing'),
            reply()])
        first = agent.chat('No signal')
        second = agent.chat('No, the meter stays still', first['session_id'])
        state = agent.session(first['session_id'])
        self.assertEqual(second['troubleshooting_status'], 'awaiting_outcome')
        self.assertEqual(state['questions_asked'], ['Does the input meter move?'])
        self.assertEqual(len(state['messages']), 4)
        self.assertIn('meter stays still', state['messages'][2]['content'])

    def test_failed_fix_is_not_repeated(self):
        agent, _ = make_agent([routing(), routing('learn', 'failed')])
        first = agent.chat('No signal')
        second = agent.chat("That didn't work", first['session_id'])
        self.assertEqual(second['intent'], 'troubleshoot')
        self.assertEqual(second['troubleshooting_status'], 'unsupported')
        self.assertEqual(agent.session(first['session_id'])['steps'][0]['outcome'], 'failed')
        self.assertEqual(agent.web.search.call_count, 1)

    def test_web_fallback_for_software(self):
        agent, _ = make_agent([routing('learn', software_specific=True)], replies=[
            reply(step=None, answer='Use the official instructions. [W1]', citation_ids=['W1'], status='idle')])
        result = agent.chat('Where is the audio input menu in Logic Pro?')
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertTrue(agent.web.search.call_args.kwargs['official_only'])
        self.assertEqual(len(agent.session(result['session_id'])['web_history']), 1)

    def test_conflicting_sources_stop(self):
        conflict = assessment()
        conflict['contradictory'] = True
        agent, chat = make_agent([routing()], [conflict, conflict])
        result = agent.chat('Which conflicting setting is correct?')
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertIn('conflict', result['answer'])
        self.assertEqual(agent.web.search.call_count, 1)
        self.assertEqual(len(chat.calls), 3)  # route + two assessments; no synthesis

    def test_discover_resource_cards(self):
        agent, _ = make_agent([routing('discover')], replies=[reply(step=None,
            answer='A relevant resource is listed. [W1]', citation_ids=['W1'], status='idle')])
        result = agent.chat('Find a tutorial')
        self.assertEqual(result['resource_cards'][0]['license'], 'License not verified.')
        self.assertFalse(agent.web.search.call_args.kwargs['official_only'])
        agent.rag.retrieve.assert_not_called()

    def test_timeout_bounded(self):
        ev = assessment()
        ev.update(sufficient=False, web_needed=True)
        agent, _ = make_agent([routing()], [ev, ev])
        agent.web.search.side_effect = WebSearchError('timeout')
        result = agent.chat('A version-specific problem')
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertTrue(result['limitations'])
        self.assertEqual(agent.web.search.call_count, 1)

    def test_resolved_and_session_isolation(self):
        agent, _ = make_agent([routing(), routing(outcome='resolved'), routing('learn')])
        first = agent.chat('No signal')
        resolved = agent.chat('It works now', first['session_id'])
        other = agent.chat('Explain gain')
        self.assertEqual(resolved['troubleshooting_status'], 'resolved')
        self.assertNotEqual(first['session_id'], other['session_id'])
        self.assertEqual(agent.session(first['session_id'])['steps'][0]['outcome'], 'resolved')

    def test_missing_evidence(self):
        ev = assessment(); ev['sufficient'] = False
        agent, _ = make_agent([routing('learn')], [ev, ev])
        agent.rag.retrieve.return_value = {'evidence': [], 'citations': {}}
        agent.web.search.return_value = []
        self.assertEqual(agent.chat('Unknown exact specification')['troubleshooting_status'], 'unsupported')

    def test_repeated_question(self):
        question = reply(step=None, diagnostic_question='Does the meter move?', status='diagnosing')
        agent, _ = make_agent([routing(), routing()], replies=[question, question])
        first = agent.chat('No audio')
        result = agent.chat('I already answered that', first['session_id'])
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertIsNone(result['diagnostic_question'])

    def test_invalid_citation_rejected(self):
        agent, _ = make_agent([routing('learn')], replies=[reply(citation_ids=['W99'])])
        with self.assertRaises(ChatError):
            agent.chat('Explain gain')

    def test_schema_retry_bounded(self):
        chat = Mock(spec=['complete'])
        chat.complete.return_value = {'intent': 'invalid'}
        with self.assertRaises(ChatError):
            structured(chat, Route, 'route', {})
        self.assertEqual(chat.complete.call_count, 2)

    def test_api_and_session_404(self):
        agent, _ = make_agent([routing('learn')])
        with patch('app.main.get_agent_service', return_value=agent):
            client = TestClient(app)
            result = client.post('/chat', json={'message': 'Explain gain'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(client.get('/sessions/' + result.json()['session_id']).status_code, 200)
            self.assertEqual(client.get('/sessions/00000000-0000-0000-0000-000000000000').status_code, 404)
            self.assertEqual(client.post('/chat', json={'message': '   '}).status_code, 400)
            self.assertEqual(client.get('/health').status_code, 200)

    def test_context_sent_to_router(self):
        agent, chat = make_agent([routing(), routing(outcome='failed')])
        first = agent.chat('No microphone signal')
        agent.chat("That didn't work", first['session_id'])
        routes = [m for m in chat.calls if 'Classify the user' in m[0]['content']]
        payload = json.loads(routes[1][1]['content'].split('\n', 1)[1])
        self.assertEqual(payload['current_intent'], 'troubleshoot')
        self.assertTrue(payload['last_step'])
        self.assertEqual(len(payload['messages']), 3)


class WebTests(unittest.TestCase):
    def test_authentication_schema_and_official_filter(self):
        captured = []
        def handle(request):
            captured.append(request)
            return httpx.Response(200, json={'results': [
                {'title': 'Official', 'url': 'https://support.apple.com/guide/logicpro/test', 'snippet': 'Test'},
                {'title': 'Spoof', 'url': 'https://support.apple.com.evil.example/x'},
                {'url': 'javascript:alert(1)'}, {'url': 'http://127.0.0.1/private'}]})
        web = KeenableSearch('synthetic-secret', client=httpx.Client(transport=httpx.MockTransport(handle)))
        results = web.search('test', product='Logic Pro', official_only=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(captured[0].headers['X-API-Key'], 'synthetic-secret')
        self.assertEqual(json.loads(captured[0].content)['site'], 'support.apple.com')
        self.assertEqual(results[0]['license'], 'License not verified.')

    def test_timeout_retry(self):
        attempts = []
        def handle(request):
            attempts.append(1)
            raise httpx.ReadTimeout('synthetic secret must not leak')
        web = KeenableSearch('secret', client=httpx.Client(transport=httpx.MockTransport(handle)))
        with self.assertRaises(WebSearchError) as caught:
            web.search('test')
        self.assertEqual(len(attempts), 2)
        self.assertNotIn('secret', str(caught.exception))

    def test_transient_retry(self):
        statuses = iter([429, 200])
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(next(statuses), json={'results': []})))
        sleep = Mock()
        self.assertEqual(KeenableSearch('key', client=client, sleep=sleep).search('test'), [])
        sleep.assert_called_once()

    def test_official_domain_boundaries(self):
        self.assertTrue(official_source('https://support.focusrite.com/a', 'Focusrite Scarlett Solo'))
        self.assertFalse(official_source('https://focusrite.com.example.org/a', 'Focusrite Scarlett Solo'))


class AgentModelTests(unittest.TestCase):
    def test_native_schema_transport(self):
        from app.config import ChatSettings
        from app.rag.generate import NebiusChat
        from app.graph.model import AgentChat
        requests = []
        def handle(request):
            requests.append(request)
            if request.url.path.endswith('/models'):
                return httpx.Response(200, json={'data': [{'id': 'test-model'}]})
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(routing('learn'))}}]})
        transport = NebiusChat(ChatSettings(api_key='synthetic-key', model='test-model'),
                               client=httpx.Client(transport=httpx.MockTransport(handle)))
        output = structured(AgentChat(transport), Route, 'Classify request', {'message': 'Explain gain'})
        self.assertEqual(output.intent, 'learn')
        body = json.loads(requests[-1].content)
        self.assertEqual(body['response_format']['type'], 'json_schema')
        self.assertEqual(body['response_format']['json_schema']['name'], 'Route')
        self.assertEqual(body['model'], 'test-model')
        self.assertNotIn('synthetic-key', json.dumps(body))

    def test_evaluation_rejects_missing_or_mismatched_evidence(self):
        from app.services.evidence_evaluator import evaluate
        state = {'goal': 'Test', 'messages': [], 'equipment': [], 'steps': [], 'evidence': [],
                 'intent': 'learn', 'software_specific': False}
        chat = Mock(spec=['complete'])
        chat.complete.return_value = assessment()
        self.assertFalse(evaluate(chat, state)['sufficient'])
        state['evidence'] = [{'text': 'Synthetic evidence'}]
        for key in ['product_relevant', 'version_relevant']:
            row = assessment(); row[key] = False
            chat.complete.return_value = row
            self.assertFalse(evaluate(chat, state)['sufficient'])

    def test_optional_tracing_does_not_initialize_without_keys(self):
        from app.services.tracing import tracing_callbacks
        with patch('app.services.tracing.dotenv_values', return_value={}), patch.dict('os.environ', {}, clear=True):
            self.assertEqual(tracing_callbacks(), [])

    def test_changed_wording_with_same_action_key_is_blocked(self):
        agent, _ = make_agent([routing(), routing(outcome='failed')], replies=[reply(),
            reply(answer='Please reseat the lead. [K1]', step='Unplug and reconnect the cable.', action_key='check_connection')])
        first = agent.chat('No audio')
        result = agent.chat('Still no audio', first['session_id'])
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertEqual(len(agent.session(first['session_id'])['steps']), 1)

    def test_only_tracked_action_is_displayed(self):
        agent, _ = make_agent([routing()], replies=[reply(
            answer='Check input. Also reinstall drivers and change cables. [K1]')])
        result = agent.chat('No audio')
        self.assertEqual(result['answer'], 'Check the input connection. [K1]')
        self.assertNotIn('reinstall', result['answer'])

    def test_complete_action_is_not_silently_truncated(self):
        agent, _ = make_agent([routing(software_specific=True)], replies=[reply(
            answer='Try the documented action. [W1]', step='Open Audio settings and then set the input device to the interface.', citation_ids=['W1'],
            step_evidence=[{'source_id':'W1','quote':'Open Audio settings and then set the input device to the interface.'}])])
        agent.web.search.return_value = [{'title':'Synthetic Logic Pro instructions','url':'https://support.apple.com/guide/logicpro/test/mac','source_type':'official','text':'Open Audio settings and then set the input device to the interface.'}]
        agent.rag.retrieve.return_value['evidence'][0]['text'] = 'Concepts only.'
        result = agent.chat('No audio')
        self.assertIn('set the input device to the interface.', result['answer'])
        self.assertEqual(agent.session(result['session_id'])['steps'][0]['text'], 'Open Audio settings and then set the input device to the interface.')

    def test_clarify_does_not_call_tools(self):
        agent, _ = make_agent([routing('clarify')])
        result = agent.chat('Help')
        self.assertEqual(result['intent'], 'clarify')
        self.assertIsNotNone(result['diagnostic_question'])
        agent.rag.retrieve.assert_not_called()
        agent.web.search.assert_not_called()

    def test_explicit_failed_followup_overrides_unknown_outcome(self):
        agent, _ = make_agent([routing(), routing('learn')])
        first = agent.chat('No microphone audio')
        result = agent.chat("That didn't work", first['session_id'])
        self.assertEqual(result['intent'], 'troubleshoot')
        self.assertEqual(agent.session(first['session_id'])['steps'][0]['outcome'], 'failed')


    def test_explicit_equipment_replaces_saved_conflicting_product(self):
        agent, _ = make_agent([
            routing(equipment=['Audio-Technica AT2035', 'Focusrite Scarlett 2i2']),
            routing(equipment=['Audio-Technica AT2020', 'Focusrite Scarlett 2i2']),
        ])
        first = agent.chat('Help with recording', equipment=['Audio-Technica AT2035', 'Focusrite Scarlett 2i2'])
        agent.chat('Actually I am using an AT2020 today', first['session_id'])
        current = agent.session(first['session_id'])['equipment']
        self.assertIn('Audio-Technica AT2020', current)
        self.assertNotIn('Audio-Technica AT2035', current)
        self.assertIn('Focusrite Scarlett 2i2', current)


    def test_diagnostic_question_takes_precedence_over_unasked_fix(self):
        agent, _ = make_agent([routing()], replies=[reply(
            diagnostic_question='Does the track input meter move?', status='diagnosing')])
        result = agent.chat('Ask one diagnostic question first')
        self.assertEqual(result['answer'], 'Does the track input meter move? [K1]')
        self.assertEqual(result['troubleshooting_status'], 'diagnosing')
        self.assertEqual(agent.session(result['session_id'])['steps'], [])

    def test_pure_diagnostic_question_does_not_require_invented_citations(self):
        agent, _ = make_agent([routing()], replies=[reply(
            answer='Does the track input meter move?', diagnostic_question='Does the track input meter move?',
            citation_ids=[], step=None, status='diagnosing')])
        result = agent.chat('No recording signal')
        self.assertEqual(result['citations'], [])
        self.assertEqual(result['diagnostic_question'], 'Does the track input meter move?')


class Phase4BQualityTests(unittest.TestCase):
    def test_complete_howto_renders_all_steps_and_success_check(self):
        agent, _ = make_agent([routing('learn', goal='How do I record audio?')], replies=[reply(
            answer='Record a short test clip. [K1]', step=None, status='idle',
            procedure=['Choose the verified input.', 'Record a short passage.', 'Stop and play it back.'],
            verification='You can hear the recorded passage during playback.')])
        agent.rag.retrieve.return_value['evidence'][0]['text'] = 'Choose the verified input. Record a short passage. Stop and play it back. You can hear the recorded passage during playback.'
        result = agent.chat('How do I record audio?')
        self.assertIn('## Steps', result['answer'])
        self.assertIn('3. Stop and play it back.', result['answer'])
        self.assertIn('## Check it worked', result['answer'])
        self.assertEqual(result['troubleshooting_status'], 'idle')

    def test_incomplete_howto_is_labeled_not_invented(self):
        agent, _ = make_agent([routing('learn')], replies=[reply(step=None, status='idle')])
        result = agent.chat('How do I record audio?')
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertEqual(result['troubleshooting_status'], 'unsupported')

    def test_troubleshooting_keeps_one_action_and_its_rationale(self):
        agent, chat = make_agent([routing(equipment=['Audio-Technica AT2035', 'Focusrite Scarlett 2i2'])], replies=[reply(
            why='This checks whether the signal is reaching the interface before software routing.')])
        result = agent.chat('My recording is silent', equipment=['Audio-Technica AT2035', 'Focusrite Scarlett 2i2'])
        self.assertIn('**Why this helps:**', result['answer'])
        payload = json.loads(chat.calls[-1][1]['content'].split('\n', 1)[1])
        self.assertIn('Audio-Technica AT2035', payload['equipment'])
        self.assertEqual(len(agent.session(result['session_id'])['steps']), 1)

    def test_activity_reports_only_executed_actions_and_resets_each_turn(self):
        agent, _ = make_agent([routing('learn'), routing('clarify')], replies=[reply(step=None, status='idle')])
        first = agent.chat('Explain compression')
        self.assertEqual([a['action'] for a in first['activities']], ['studio_search', 'answer_check'])
        self.assertEqual(first['activities'][0]['result_count'], 1)
        second = agent.chat('Unclear', first['session_id'])
        self.assertEqual([a['action'] for a in second['activities']], ['clarification'])

    def test_failed_web_activity_is_not_completed_research(self):
        agent, _ = make_agent([routing('discover')])
        agent.web.search.side_effect = WebSearchError('unavailable')
        result = agent.chat('Find resources')
        search = next(a for a in result['activities'] if a['action'] == 'web_search')
        self.assertEqual(search['status'], 'failed')
        self.assertFalse(any(a['action'] == 'documentation_read' for a in result['activities']))

    def test_indexed_document_fetch_is_bounded_and_does_not_enable_live_crawl(self):
        captured = []
        def handler(request):
            captured.append(request)
            return httpx.Response(200, json={'url': 'https://support.apple.com/guide/logicpro/test', 'content': '# Synthetic indexed test procedure'})
        tool = KeenableSearch('synthetic-key', client=httpx.Client(transport=httpx.MockTransport(handler)))
        result = tool.fetch('https://support.apple.com/guide/logicpro/test', product='Logic Pro')
        self.assertTrue(result['text'].startswith('# Synthetic'))
        self.assertEqual(captured[0].url.params['max_chars'], '12000')
        self.assertNotIn('live', captured[0].url.params)
        with self.assertRaises(WebSearchError):
            tool.fetch('https://support.apple.com/manual.pdf')

    def test_unsupported_draft_gets_one_repair_then_abstains(self):
        agent, chat = make_agent([routing('learn')], replies=[reply(step=None), reply(step=None)])
        original = chat.complete
        reviews = []
        def complete(messages):
            if 'Review the draft' in messages[0]['content']:
                reviews.append(1)
                return {'supported': False, 'complete': False, 'issues': ['Unsupported factual claim']}
            return original(messages)
        chat.complete = complete
        result = agent.chat('Explain compression')
        self.assertEqual(len(reviews), 2)
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertIn('could not verify', result['answer'])

    def test_procedure_citations_are_validated_after_formatting(self):
        agent, _ = make_agent([routing('learn')], replies=[reply(step=None,
            procedure=['Invented citation [W99]'], verification='A test recording appears.')])
        result = agent.chat('How do I record?')
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertNotIn('[W99]', result['answer'])

    def test_agent_uses_raw_approved_passages_not_a_generated_summary(self):
        agent, _ = make_agent([routing('learn')], replies=[reply(step=None)])
        result = agent.chat('Explain EQ')
        agent.rag.answer.assert_not_called()
        self.assertEqual(agent.session(result['session_id'])['evidence'][0]['text'], 'Synthetic conceptual evidence.')

    def test_scoped_official_procedure_does_not_require_installed_version(self):
        from app.services.evidence_evaluator import evaluate
        chat = Mock(spec=['complete'])
        row = assessment(); row.update(sufficient=False, version_relevant=False,
            clarification_needed=True, clarification_question='What version are you using?')
        chat.complete.return_value = row
        state = {'intent': 'learn', 'how_to': True, 'goal': 'Add audio track', 'messages': [],
            'version': None, 'equipment': ['Logic Pro'], 'steps': [],
            'evidence': [{'id': 'W1', 'content_scope': 'bounded_indexed_page', 'text': 'Synthetic complete procedure.'}]}
        result = evaluate(chat, state)
        self.assertFalse(result['clarification_needed'])
        self.assertTrue(result['sufficient'])

    def test_known_factual_traps_are_rejected_without_rewriting_answer(self):
        from app.graph.answers import LearnAnswer, surface_issues
        draft = LearnAnswer(takeaway='Compression controls level.',
            practical_example='A harsh high end can be fixed with a high-pass filter without changing the tone.',
            citation_ids=['K1'])
        self.assertTrue(surface_issues(draft))
        self.assertIn('high-pass filter', draft.practical_example)

    def test_discover_query_does_not_include_unrelated_saved_equipment(self):
        agent, _ = make_agent([routing('discover', goal='Find tabla loops',
            equipment=['Audio-Technica AT2035', 'Focusrite Scarlett 2i2'])], replies=[reply(
                step=None, citation_ids=['W1'], answer='A relevant resource. [W1]', status='idle')])
        agent.chat('Find tabla loops', equipment=['Audio-Technica AT2035', 'Focusrite Scarlett 2i2'])
        query = agent.web.search.call_args.args[0]
        self.assertNotIn('AT2035', query)
        self.assertNotIn('Scarlett', query)

    def test_flagged_concept_blocks_are_omitted_not_rewritten(self):
        from app.graph.answers import LearnAnswer, omit_flagged_concept_details, surface_issues
        original = LearnAnswer(takeaway='EQ shapes tone; compression controls level.',
            key_points=['EQ changes frequency balance.', 'Compression works without changing the tone.'],
            practical_example='A harsh high end can be fixed by a high-pass filter.', citation_ids=['K1'])
        cleaned, removed = omit_flagged_concept_details(original)
        self.assertEqual(removed, 2)
        self.assertEqual(cleaned.takeaway, original.takeaway)
        self.assertEqual(cleaned.key_points, ['EQ changes frequency balance.'])
        self.assertIsNone(cleaned.practical_example)
        self.assertFalse(surface_issues(cleaned))


    def test_discovery_does_not_render_unverified_model_license_claims(self):
        from app.graph.answers import resource_description
        self.assertNotIn('commercial', resource_description('Useful tabla loops. Unlimited commercial usage is allowed.'))
        agent, _ = make_agent([routing('discover')], replies=[reply(
            answer='Fabricated commercial-use permission', citation_ids=['W1'], step=None, status='idle')])
        result = agent.chat('Find tabla loops')
        self.assertNotIn('Fabricated', result['answer'])
        self.assertEqual(result['resource_cards'][0]['license'], 'License not verified.')

    def test_eq_loudness_invariance_and_interface_permission_overclaims_are_flagged(self):
        from app.graph.answers import LearnAnswer, surface_issues
        self.assertTrue(surface_issues(LearnAnswer(takeaway='EQ does not affect how loud sounds are over time.')))
        from app.graph.workflow import Reply
        self.assertTrue(surface_issues(Reply(
            answer='Check permissions.', citation_ids=['W1'], status='awaiting_outcome',
            why='This permission is required for any external interface to function.')))

    def test_empty_discovery_selection_is_an_abstention_not_a_provider_error(self):
        agent, _ = make_agent([routing('discover')], replies=[reply(citation_ids=[], step=None, status='idle')])
        result = agent.chat('Find an obscure resource')
        self.assertEqual(result['troubleshooting_status'], 'unsupported')
        self.assertEqual(result['resource_cards'], [])
