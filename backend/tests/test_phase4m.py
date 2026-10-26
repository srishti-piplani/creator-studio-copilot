"""Targeted synthetic provider fixtures; live journeys are recorded separately."""
import unittest
from unittest.mock import Mock
import httpx
from app.graph.context import clarification_reply
from app.graph.monitoring import REFERENCE, SWITCH_QUESTION, LABEL_QUESTION, applicable_section
from app.graph.workflow import StudioAgent
from app.tools.web_search import KeenableSearch, WebSearchError
from test_agent import ScriptedChat, make_agent, routing, assessment

SECTION = '### Scarlett Solo, 2i2 (1st and 2nd Gen) and iTrack Solo\nSwitch the Direct Monitor switch to “Off” on the front of the hardware.\n### Scarlett 2i4 (1st and 2nd Gen)\nDifferent model instructions.'

class CreativeChat(ScriptedChat):
    def complete(self, messages):
        instruction=messages[0]['content']
        if 'Review each creative suggestion' in instruction:
            return {'keep_indices':[0,2]}
        if 'Offer a few practical listening experiments' in instruction:
            return {'status':'supported','suggestions':[
                {'text':'Compare a modest EQ change in the mix.', 'source':{'source_id':'K1','quote':'Compare a modest EQ change in the mix.'}},
                {'text':'Boost 100 Hz by 6 dB.', 'source':{'source_id':'K1','quote':'Compare a modest EQ change in the mix.'}},
                {'text':'Keep a bypassable version and compare at matched loudness.', 'source':{'source_id':'K1','quote':'Keep a bypassable version and compare at matched loudness.'}}], 'missing_evidence':None}
        return super().complete(messages)

class Phase4M(unittest.TestCase):
    def test_creative_goal_is_not_forced_into_ui_procedure(self):
        base,_=make_agent([])
        base.rag.retrieve.return_value['evidence'][0]['text']='Compare a modest EQ change in the mix. Keep a bypassable version and compare at matched loudness.'
        model=CreativeChat(routes=[routing('learn',goal='How do I make vocals sound warmer?',software_specific=True)])
        agent=StudioAgent(base.rag,base.web,chat=model)
        response=agent.chat('How do I make vocals sound warmer?')
        state=agent.session(response['session_id'])
        self.assertTrue(state['creative_goal'])
        self.assertFalse(state['how_to'])
        self.assertFalse(state['software_specific'])
        self.assertEqual(response['troubleshooting_status'],'idle')
        self.assertIn('matched loudness',response['answer'])
        self.assertNotIn('100 Hz',response['answer'])
        self.assertNotIn('Unsupported',response['answer'])
        base.rag.retrieve.assert_called_once()
        base.web.search.assert_not_called()

    def test_creative_advice_uses_external_fallback_when_internal_insufficient(self):
        base,_=make_agent([])
        base.rag.retrieve.return_value['evidence'][0]['text']='Compare a modest EQ change in the mix. Keep a bypassable version and compare at matched loudness.'
        model=CreativeChat(routes=[routing('learn',goal='How do I make vocals sound warmer?',software_specific=True)],
                           evaluations=[{**assessment(),'sufficient':False,'web_needed':True},assessment()])
        agent=StudioAgent(base.rag,base.web,chat=model)
        result=agent.chat('How do I make vocals sound warmer?')
        base.web.search.assert_called_once()
        self.assertFalse(base.web.search.call_args.kwargs['official_only'])
        self.assertEqual(result['troubleshooting_status'],'idle')

    def test_exact_software_request_still_uses_procedural_contract(self):
        from test_phase4k import procedural_agent
        agent,_=procedural_agent()
        result=agent.chat('How do I add a compressor in Logic Pro?')
        self.assertFalse(agent.session(result['session_id'])['creative_goal'])
        self.assertIn('## Steps',result['answer'])

    def test_hardware_check_then_unknown_reply_preserves_symptom(self):
        base,_=make_agent([])
        model=ScriptedChat([routing(goal='Voice twice while recording'),routing('clarify',goal="I don't know",new_goal=True)])
        web=Mock(spec=['search','fetch']);web.search.return_value=base.web.search.return_value
        web.fetch.side_effect=lambda url,**kw: {'url':url,'text':SECTION if url==REFERENCE else 'Generic synthetic software evidence.'}
        agent=StudioAgent(base.rag,web,chat=model)
        first=agent.chat('Why do I hear my voice twice while recording?',equipment=['Logic Pro','Focusrite Scarlett 2i2 — 2nd Gen','Audio-Technica AT2035'])
        self.assertEqual(first['diagnostic_question'],SWITCH_QUESTION)
        second=agent.chat("I don't know.",first['session_id'])
        self.assertEqual(second['diagnostic_question'],LABEL_QUESTION)
        self.assertIn('front of the Scarlett',second['answer'])
        self.assertNotIn('both monitoring paths',second['answer'])
        self.assertEqual(agent.session(first['session_id'])['goal'],'Voice twice while recording')
        self.assertEqual(agent.session(first['session_id'])['questions_asked'],[SWITCH_QUESTION,LABEL_QUESTION])
        self.assertEqual(agent.session(first['session_id'])['steps'],[])

    def test_unknown_replies_are_contextual_and_control_scope_is_generation_specific(self):
        for reply in ["I don't know.","I'm not sure",'Not sure.']:
            self.assertTrue(clarification_reply(reply))
        self.assertIn('Direct Monitor switch',applicable_section(SECTION))
        self.assertIsNone(applicable_section('Scarlett 2i2 4th Gen: press the button.'))

    def test_resource_fetch_reports_categories_without_retries(self):
        cases=[(httpx.Response(403), 'http'),(httpx.Response(200,json={'content':''}),'extraction'),
               (httpx.Response(200,content='not json'),'parsing')]
        for response,category in cases:
            client=Mock();client.get.return_value=response
            tool=KeenableSearch('synthetic-test-key',client=client,sleep=lambda _:None)
            with self.assertRaises(WebSearchError) as raised:
                tool.fetch('https://example.com/terms',resource=True)
            self.assertEqual(raised.exception.category,category)
            client.get.assert_called_once()
        client=Mock();client.get.side_effect=httpx.ReadTimeout('test')
        with self.assertRaises(WebSearchError) as raised:
            KeenableSearch('synthetic-test-key',client=client).fetch('https://example.com/terms',resource=True)
        self.assertEqual(raised.exception.category,'timeout')
        client.get.assert_called_once()

    def test_www_alias_allowed_but_other_host_denied(self):
        client=Mock();client.get.return_value=httpx.Response(200,json={'url':'https://www.example.com/terms','content':'Terms need human review.'})
        tool=KeenableSearch('synthetic-test-key',client=client)
        self.assertIn('www.example.com',tool.fetch('https://example.com/terms',resource=True)['url'])
        client.get.return_value=httpx.Response(200,json={'url':'https://other.example/terms','content':'Untrusted redirect.'})
        with self.assertRaises(WebSearchError):tool.fetch('https://example.com/terms',resource=True)
