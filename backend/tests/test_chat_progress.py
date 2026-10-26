"""SSE transport with real LangGraph execution and scripted provider boundaries."""
import json
from threading import Event
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.graph.progress import operation
from app.rag.generate import ChatError
from app.services.chat_jobs import ChatJobs
from test_agent import make_agent, routing, reply


def frames(response):
    events = []
    for block in response.text.split('\n\n'):
        lines = block.splitlines()
        name = next((line[7:] for line in lines if line.startswith('event: ')), None)
        data = next((line[6:] for line in lines if line.startswith('data: ')), None)
        if name and data:
            events.append((name, json.loads(data)))
    return events


class ChatProgressTests(unittest.TestCase):
    def setUp(self):
        self.jobs = ChatJobs()
        self.addCleanup(lambda: self.jobs.pool.shutdown(wait=True))
        self.registry = patch('app.main.chat_jobs', self.jobs)
        self.registry.start()
        self.addCleanup(self.registry.stop)
        self.client = TestClient(app)

    def test_progress_order_and_final_payload_no_fabricated_web_search(self):
        agent, _ = make_agent([routing('learn', goal='Explain gain')], replies=[reply(step=None, status='idle')])
        with patch('app.main.get_agent_service', return_value=agent):
            response = self.client.post('/chat/stream', json={'message': 'Explain gain', 'request_id': str(uuid4())})
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/event-stream', response.headers['content-type'])
        events = frames(response)
        progress = [data for name, data in events if name == 'progress']
        self.assertEqual([(p['action'], p['status']) for p in progress], [
            ('understand', 'started'), ('understand', 'completed'),
            ('knowledge', 'started'), ('knowledge', 'completed'),
            ('evidence', 'started'), ('evidence', 'completed'),
            ('answer', 'started'), ('answer', 'completed')])
        self.assertEqual(events[-1][0], 'final')
        self.assertEqual(events[-1][1]['answer'], 'Check the input connection. [K1]')
        self.assertTrue(all(set(p) == {'action', 'status', 'label'} for p in progress))
        agent.web.search.assert_not_called()

    def test_web_progress_brackets_the_actual_call(self):
        agent, _ = make_agent([routing('discover', goal='Find tutorials')], replies=[reply(
            step=None, citation_ids=['W1'], answer='Relevant resource. [W1]', status='idle')])
        request_id = str(uuid4())
        def search(*args, **kwargs):
            emitted = self.jobs.jobs[request_id].events
            self.assertEqual(emitted[-1][1]['action'], 'web_search')
            self.assertEqual(emitted[-1][1]['status'], 'started')
            return agent.web.search.return_value
        agent.web.search.side_effect = search
        with patch('app.main.get_agent_service', return_value=agent):
            events = frames(self.client.post('/chat/stream', json={'message': 'Find tutorials', 'request_id': request_id}))
        web = [data['status'] for name, data in events if name == 'progress' and data['action'] == 'web_search']
        self.assertEqual(web, ['started', 'completed'])
        agent.web.search.assert_called_once()

    def test_fallback_post_joins_original_job_without_duplicate_conversation_turn(self):
        agent, _ = make_agent([routing('learn')], replies=[reply(step=None, status='idle')])
        request = {'message': 'Explain gain', 'request_id': str(uuid4())}
        with patch('app.main.get_agent_service', return_value=agent):
            events = frames(self.client.post('/chat/stream', json=request))
            fallback = self.client.post('/chat', json=request)
        self.assertEqual(fallback.status_code, 200)
        self.assertEqual(fallback.json(), events[-1][1])
        self.assertEqual(len(agent.session(fallback.json()['session_id'])['messages']), 2)
        agent.rag.retrieve.assert_called_once()

    def test_progress_is_available_before_operation_finishes(self):
        entered, release = Event(), Event()
        def work():
            def call():
                entered.set()
                self.assertTrue(release.wait(3))
                return {'answer': 'Synthetic result'}
            return operation('knowledge', 'Searching Studio Knowledge', call)
        job = self.jobs.get_or_start('test-id', (), work)
        try:
            self.assertTrue(entered.wait(3))
            iterator = job.events_since_start()
            self.assertIn('"status": "started"', next(iterator))
            self.assertFalse(job.future.done())
            joined = self.jobs.get_or_start('test-id', (), lambda: self.fail('Duplicate work started'))
            self.assertIs(joined.future, job.future)
        finally:
            release.set()
        self.assertEqual(job.future.result(3)['answer'], 'Synthetic result')

    def test_provider_error_is_sanitized_and_no_final_is_fabricated(self):
        agent, model = make_agent([routing('learn')])
        model.complete = lambda _messages: (_ for _ in ()).throw(ChatError('SECRET provider body'))
        with patch('app.main.get_agent_service', return_value=agent):
            response = self.client.post('/chat/stream', json={'message': 'Explain gain', 'request_id': str(uuid4())})
        events = frames(response)
        self.assertEqual(events[-1], ('error', {'status': 503, 'message': 'Assistant is temporarily unavailable'}))
        self.assertNotIn('SECRET', response.text)
        self.assertFalse(any(name == 'final' for name, _ in events))
        self.assertIn(('understand', 'failed'), [(data['action'], data['status']) for name, data in events if name == 'progress'])

    def test_existing_chat_without_request_id_is_unchanged(self):
        agent, _ = make_agent([routing('learn')], replies=[reply(step=None, status='idle')])
        with patch('app.main.get_agent_service', return_value=agent):
            response = self.client.post('/chat', json={'message': 'Explain gain'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['intent'], 'learn')
        self.assertEqual(len(self.jobs.jobs), 0)

    def test_reusing_request_id_for_different_input_is_rejected(self):
        agent, _ = make_agent([routing('learn')], replies=[reply(step=None, status='idle')])
        request = {'message': 'Explain gain', 'request_id': str(uuid4())}
        with patch('app.main.get_agent_service', return_value=agent):
            self.client.post('/chat/stream', json=request)
            changed = self.client.post('/chat', json={**request, 'message': 'Different question'})
        self.assertEqual(changed.status_code, 409)


    def test_official_document_progress_occurs_only_for_actual_fetches(self):
        from unittest.mock import Mock
        agent, _ = make_agent([routing('learn', goal='Logic Pro control', software_specific=True)], replies=[reply(step=None, status='idle')])
        tool = Mock(spec=['search', 'fetch'])
        tool.search.return_value = agent.web.search.return_value
        tool.fetch.return_value = {'text': 'Synthetic official documentation.', 'url': 'https://support.apple.com/synthetic-test'}
        agent.web = tool
        with patch('app.main.get_agent_service', return_value=agent):
            events = frames(self.client.post('/chat/stream', json={'message': 'Logic Pro control', 'request_id': str(uuid4())}))
        actions = [(data['action'], data['status']) for name, data in events if name == 'progress']
        self.assertIn(('official_search', 'started'), actions)
        self.assertIn(('official_search', 'completed'), actions)
        self.assertIn(('documentation', 'started'), actions)
        self.assertIn(('documentation', 'completed'), actions)
        self.assertLess(actions.index(('official_search', 'completed')), actions.index(('documentation', 'started')))
        tool.search.assert_called_once()
        tool.fetch.assert_called_once()

    def test_failed_search_is_not_reported_as_completed_research(self):
        from app.tools.web_search import WebSearchError
        agent, _ = make_agent([routing('discover')])
        agent.web.search.side_effect = WebSearchError('synthetic failure')
        with patch('app.main.get_agent_service', return_value=agent):
            events = frames(self.client.post('/chat/stream', json={'message': 'Find resources', 'request_id': str(uuid4())}))
        progress = [(data['action'], data['status']) for name, data in events if name == 'progress']
        self.assertIn(('web_search', 'failed'), progress)
        self.assertNotIn(('web_search', 'completed'), progress)
        self.assertFalse(any(action == 'documentation' for action, _ in progress))
