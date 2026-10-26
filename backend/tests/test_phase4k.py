"""Intent contracts and exact-span provenance; all documentation here is synthetic."""
import json
import unittest
from pydantic import ValidationError
from app.graph.procedures import HowToAnswer, SourceSpan
from app.graph.provenance import provenance, valid_span
from app.graph.workflow import DiagnosticReply, StudioAgent
from test_agent import ScriptedChat, make_agent, routing, reply

QUOTE = 'In a Logic Pro channel strip, click an Audio Effect slot, then choose Dynamics > Compressor.'
MONITOR = 'In Logic Pro, choose Settings > Audio > General and deselect Software Monitoring.'
DOC = {'title':'Synthetic Logic Pro test instructions', 'url':'https://support.apple.com/guide/logicpro/synthetic/mac', 'source_type':'official', 'text':QUOTE + '\n' + MONITOR, 'source':'support.apple.com'}

class ContractChat(ScriptedChat):
    def __init__(self, draft=None, review=None, **kwargs):
        super().__init__(**kwargs)
        self.draft = draft or {'status':'supported','procedure':[{'source_id':'W1','quote':QUOTE}], 'success_check':None,'missing_evidence':None}
        self.review = review or {'essential_complete':True,'unresolved_conflict':False,'keep_indices':[0],'check_supported':False}
    def complete(self, messages):
        if 'Extract the shortest complete procedure' in messages[0]['content']:
            self.calls.append(messages)
            return self.draft
        if 'Review only whether the retained source instructions' in messages[0]['content']:
            self.calls.append(messages)
            self.review_payload=json.loads(messages[1]['content'].split('\n',1)[1])
            return self.review
        return super().complete(messages)


def procedural_agent(draft=None, review=None):
    base,_=make_agent([])
    base.web.search.return_value=[dict(DOC)]
    model=ContractChat(routes=[routing('learn',goal='How do I add a compressor in Logic Pro?',software_specific=True)],draft=draft,review=review)
    return StudioAgent(base.rag,base.web,chat=model),model

class Phase4K(unittest.TestCase):
    def test_takeaway_only_is_not_a_procedural_contract(self):
        with self.assertRaises(ValidationError):
            HowToAnswer.model_validate({'takeaway':'Insert a compressor.'})
        with self.assertRaises(ValidationError):
            HowToAnswer(status='supported',procedure=None,success_check=None,missing_evidence=None)
        agent,_=procedural_agent(draft={'takeaway':'Insert a compressor.'})
        self.assertEqual(agent.chat('How do I add a compressor in Logic Pro?')['troubleshooting_status'],'unsupported')

    def test_supported_procedure_and_official_first(self):
        agent,model=procedural_agent()
        response=agent.chat('How do I add a compressor in Logic Pro?')
        self.assertEqual(response['troubleshooting_status'],'idle')
        self.assertIn(QUOTE,response['answer'])
        self.assertEqual(response['citations'][0]['evidence_type'],'official_product_documentation')
        agent.rag.retrieve.assert_not_called()
        self.assertTrue(agent.web.search.call_args.kwargs['official_only'])
        self.assertEqual(len(model.calls),3)  # Router, extraction, source/completeness review.

    def test_unsupported_individual_optional_step_omitted(self):
        draft={'status':'supported','procedure':[{'source_id':'W1','quote':QUOTE},{'source_id':'W1','quote':'Right-click Add Insert to show an invented control.'}], 'success_check':None,'missing_evidence':None}
        agent,model=procedural_agent(draft=draft)
        response=agent.chat('How do I add a compressor in Logic Pro?')
        self.assertNotIn('Add Insert',response['answer'])
        self.assertIn(QUOTE,response['answer'])
        self.assertEqual(model.review_payload['valid_spans'],[True,False])

    def test_invalid_essential_span_and_unresolved_conflict_abstain(self):
        agent,_=procedural_agent(draft={'status':'supported','procedure':[{'source_id':'W1','quote':'Click a completely fictional menu control.'}], 'success_check':None,'missing_evidence':None})
        self.assertEqual(agent.chat('How do I add a compressor in Logic Pro?')['troubleshooting_status'],'unsupported')
        agent,_=procedural_agent(review={'essential_complete':True,'unresolved_conflict':True,'keep_indices':[0],'check_supported':False})
        self.assertEqual(agent.chat('How do I add a compressor in Logic Pro?')['troubleshooting_status'],'unsupported')

    def test_concepts_and_spoofed_official_sources_cannot_establish_ui(self):
        span=SourceSpan(source_id='K1',quote=QUOTE)
        concept=provenance({'id':'K1','kind':'general_concepts','text':QUOTE,'source_type':'official','url':DOC['url']},'Logic Pro')
        self.assertEqual(concept['source_type'],'original_studio_knowledge')
        self.assertFalse(valid_span(span,[concept],product='Logic Pro',require_official=True))
        fake=provenance({**DOC,'id':'K1','url':'https://example.com/logicpro'},'Logic Pro')
        self.assertEqual(fake['evidence_type'],'unknown')
        self.assertFalse(valid_span(span,[fake],product='Logic Pro',require_official=True))

    def test_version_mismatch_blocks_exact_ui(self):
        row=provenance({**DOC,'id':'W1','url':'https://support.apple.com/guide/logicpro/synthetic/10.7.5/mac/12.3'},'Logic Pro')
        self.assertEqual(row['documentation_version'],'10.7.5')
        span=SourceSpan(source_id='W1',quote=QUOTE)
        self.assertTrue(valid_span(span,[row],product='Logic Pro',require_official=True))
        self.assertFalse(valid_span(span,[row],product='Logic Pro',version='12.3',require_official=True))

    def test_conceptual_learn_stays_pinecone_first(self):
        agent,_=make_agent([routing('learn',goal='What is compression?',software_specific=False)],replies=[reply(answer='Compression reduces above-threshold peaks. [K1]',step=None,status='idle')])
        self.assertEqual(agent.chat('What is compression?')['intent'],'learn')
        agent.rag.retrieve.assert_called_once()
        agent.web.search.assert_not_called()

    def test_diagnostic_contract_requires_question_or_action(self):
        with self.assertRaises(ValidationError):
            DiagnosticReply(answer='Generic advice.',status='diagnosing')

    def test_monitoring_context_supported_action_and_failed_fix(self):
        question='Does this occur during recording or also during playback?'
        action=reply(answer='Try the documented step. [W1]',citation_ids=['W1'],step=MONITOR,action_key='disable_software_monitoring',step_evidence=[{'source_id':'W1','quote':MONITOR}])
        agent,_=make_agent([routing(goal='Voice twice during recording'),routing(goal='Only during recording.',new_goal=True,intent='learn'),routing(goal='Voice twice during recording',outcome='failed')],replies=[reply(answer=question,diagnostic_question=question,step=None,status='diagnosing'),action,action])
        agent.web.search.return_value=[dict(DOC)]
        first=agent.chat('Why do I hear my voice twice while recording?',equipment=['Logic Pro','Focusrite Scarlett 2i2 — 2nd Gen','Audio-Technica AT2035'])
        second=agent.chat('Only during recording.',first['session_id'])
        self.assertEqual(second['intent'],'troubleshoot')
        self.assertEqual(second['troubleshooting_status'],'awaiting_outcome')
        self.assertIn(MONITOR,second['answer'])
        third=agent.chat("That didn't work.",first['session_id'])
        self.assertNotIn(MONITOR,third['answer'])
        state=agent.session(first['session_id'])
        self.assertEqual(state['goal'],'Voice twice during recording')
        self.assertEqual(state['steps'][0]['outcome'],'failed')

    def test_invalid_ui_action_falls_back_without_recording_failed_claim(self):
        agent,_=make_agent([routing(goal='Voice twice during recording')], replies=[reply(
            answer='Try the source instruction. [W1]',citation_ids=['W1'],
            step='Click a fictional Software Monitoring checkbox in the track header.',
            step_evidence=[{'source_id':'W1','quote':MONITOR}])])
        agent.web.search.return_value=[dict(DOC)]
        result=agent.chat('Voice twice during recording',equipment=['Logic Pro','Focusrite Scarlett 2i2 — 2nd Gen'])
        self.assertEqual(result['troubleshooting_status'],'diagnosing')
        self.assertNotIn('fictional',result['answer'])
        self.assertIn('headphones plugged',result['diagnostic_question'])
        self.assertEqual(agent.session(result['session_id'])['steps'],[])

    def test_ipad_documentation_cannot_establish_mac_controls(self):
        row=provenance({**DOC,'id':'W1','url':'https://support.apple.com/guide/logicpro-ipad/synthetic/ipados'},'Logic Pro')
        self.assertEqual(row['product'],'Logic Pro for iPad')
        self.assertFalse(valid_span(SourceSpan(source_id='W1',quote=QUOTE),[row],product='Logic Pro',require_official=True))

    def test_optional_unmatched_check_does_not_discard_core(self):
        draft={'status':'supported','procedure':[{'source_id':'W1','quote':QUOTE}],
               'success_check':{'source_id':'W1','quote':'A fictional screen proves everything worked.'},'missing_evidence':None}
        agent,_=procedural_agent(draft=draft,review={'essential_complete':True,'unresolved_conflict':False,'keep_indices':[0],'check_supported':True})
        response=agent.chat('How do I add a compressor in Logic Pro?')
        self.assertEqual(response['troubleshooting_status'],'idle')
        self.assertNotIn('fictional',response['answer'])
        self.assertNotIn('Check it worked',response['answer'])

    def test_task_link_is_followed_only_when_returned_by_official_page(self):
        from unittest.mock import Mock
        agent,_=procedural_agent()
        tool=Mock(spec=['search','fetch'])
        url='https://support.apple.com/guide/logicpro/linked-test/mac'
        tool.search.return_value=[{**DOC,'text':'To add an effect, choose its documented menu.'}]
        tool.fetch.side_effect=[{'url':DOC['url'],'text':'To add an effect, choose its documented menu. [Add plug-ins in Logic Pro]('+url+')'},
                                {'url':url,'text':QUOTE}]
        agent.web=tool
        response=agent.chat('How do I add a compressor in Logic Pro?')
        self.assertEqual(response['troubleshooting_status'],'idle')
        self.assertEqual(tool.fetch.call_count,2)
        self.assertEqual(response['citations'][0]['url'],url)
        agent.rag.retrieve.assert_not_called()

    def test_concept_review_cannot_approve_invented_ui_or_official_label(self):
        for text in ['Click the fictional Insert slot in the mixer. [K1]', 'Official Apple documentation recommends this approach. [K1]']:
            agent,_=make_agent([routing('learn',goal='What is compression?')],replies=[reply(answer=text,step=None,status='idle')]*2)
            result=agent.chat('What is compression?')
            self.assertEqual(result['troubleshooting_status'],'unsupported')
            self.assertNotIn('fictional',result['answer'])
