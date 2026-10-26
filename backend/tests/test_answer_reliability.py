"""Focused Phase 4J regressions; scripted provider boundaries, real graph execution."""
import json
import unittest
from app.graph.answers import LearnAnswer, DraftReview, prepare_howto, apply_howto_review
from test_agent import make_agent, routing, assessment, reply, ScriptedChat
from app.graph.workflow import StudioAgent

class ReliabilityChat(ScriptedChat):
    def __init__(self, *args, reviews=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reviews = list(reviews or [])
        self.reviewed = []

    def complete(self, messages):
        if 'Review only whether the retained source instructions' in messages[0]['content']:
            payload = json.loads(messages[1]['content'].split('\n',1)[1])
            result = self.reviews.pop(0) if self.reviews else {'supported':True,'complete':True,'verification_supported':False}
            return {'essential_complete':result.get('essential_supported',result['supported']) and result['complete'],
                    'unresolved_conflict':False, 'keep_indices':[i for i,v in enumerate(payload['valid_spans']) if v],
                    'check_supported':result.get('verification_supported',False)}
        if 'Review the draft' in messages[0]['content']:
            self.reviewed.append(json.loads(messages[1]['content'].split('\n', 1)[1]))
            return self.reviews.pop(0) if self.reviews else {'supported':True,'complete':True,'issues':[], 'essential_supported':True,'verification_supported':False}
        return super().complete(messages)


def learn_agent(*, reviews=None, procedure=None, verification=None):
    base, _ = make_agent([])
    chat = ReliabilityChat([routing('learn',goal='How do I add a compressor to an audio track in Logic Pro?',software_specific=True)], replies=[
        reply(answer='Follow the source. [W1]', citation_ids=['W1'], step=None,status='idle',
              procedure=procedure if procedure is not None else ['Select the audio track.', 'In the channel strip Audio Effect slot, choose Dynamics > Compressor.'],
              verification=verification)] * 2, reviews=reviews)
    source = ' '.join([*(procedure if procedure is not None else ['Select the audio track.', 'In the channel strip Audio Effect slot, choose Dynamics > Compressor.']), verification or ''])
    base.web.search.return_value = [{'title':'Synthetic Logic Pro instructions', 'url':'https://support.apple.com/guide/logicpro/test/mac','source_type':'official','text':source}]
    return StudioAgent(base.rag,base.web,chat=chat), chat

class AnswerReliability(unittest.TestCase):
    def test_supported_steps_answered_without_optional_check(self):
        agent, _ = learn_agent()
        result=agent.chat('How do I add a compressor to an audio track in Logic Pro?')
        self.assertEqual(result['troubleshooting_status'],'idle')
        self.assertTrue(result['answer'].startswith('## Steps'))
        self.assertIn('Dynamics > Compressor', result['answer'])
        self.assertNotIn('Check it worked',result['answer'])
        self.assertTrue(result['citations'])

    def test_optional_failure_is_not_essential_failure(self):
        agent, _ = learn_agent(verification='Gain reduction always occurs.', reviews=[{
            'supported':False,'complete':True,'essential_supported':True,
            'verification_supported':False,'issues':['Optional success check is unsupported.']}])
        result=agent.chat('How do I add a compressor to an audio track in Logic Pro?')
        self.assertEqual(result['troubleshooting_status'],'idle')
        self.assertNotIn('Gain reduction',result['answer'])
        self.assertIn('Dynamics > Compressor',result['answer'])

    def test_supported_check_is_retained(self):
        agent, _ = learn_agent(verification='Compressor appears in the channel strip.',reviews=[{
            'supported':True,'complete':True,'essential_supported':True,'verification_supported':True,'issues':[]}])
        result=agent.chat('How do I add a compressor to an audio track in Logic Pro?')
        self.assertIn('## Check it worked',result['answer'])

    def test_unsupported_essential_procedure_still_abstains(self):
        bad={'supported':False,'complete':False,'essential_supported':False,'verification_supported':False,'issues':['Essential controls are absent from evidence.']}
        agent, _ = learn_agent(procedure=['Use a fictional control.'],reviews=[bad,bad])
        self.assertEqual(agent.chat('How do I add a compressor to an audio track in Logic Pro?')['troubleshooting_status'],'unsupported')

    def test_optional_details_removed_before_review_not_rewritten(self):
        state={'goal':'Add a compressor in Logic Pro','how_to':True,'citations':[{'id':'W1'}]}
        draft=LearnAnswer(takeaway='Unverified theory.',procedure=['Choose Dynamics > Compressor.','Set Threshold to -20 dB.'],practical_example='Invented recipe.',verification='Watch gain reduction.',citation_ids=['W1','W99'])
        retained=prepare_howto(draft,state)
        self.assertEqual(retained.procedure,['Choose Dynamics > Compressor.'])
        self.assertEqual(retained.citation_ids,['W1'])
        self.assertIsNone(retained.practical_example)
        self.assertIsNone(retained.verification)
        self.assertIsNone(apply_howto_review(retained,DraftReview(supported=True,complete=True),state)[0].verification)

    def test_recording_only_then_action_then_failed_fix_not_repeated(self):
        question='Does it happen only during recording or also during playback?'
        step='In Logic Pro, open Audio settings > General and deselect Software Monitoring.'
        agent,_=make_agent([
            routing(goal='Why do I hear my voice twice while recording?'),
            routing(goal='Only during recording.',new_goal=True,intent='learn'),
            routing(goal='Why do I hear my voice twice while recording?',outcome='failed'),
        ],replies=[reply(answer=question,diagnostic_question=question,step=None,status='diagnosing'),
                   reply(answer='Follow the documented step. [W1]',citation_ids=['W1'],step=step,action_key='disable_software_monitoring',step_evidence=[{'source_id':'W1','quote':step}]),
                   reply(answer='Follow the documented step. [W1]',citation_ids=['W1'],step=step,action_key='disable_software_monitoring',step_evidence=[{'source_id':'W1','quote':step}])])
        agent.web.search.return_value = [{'title':'Synthetic Logic Pro instructions','url':'https://support.apple.com/guide/logicpro/test/mac','source_type':'official','text':step}]
        first=agent.chat('Why do I hear my voice twice while recording?',equipment=['Logic Pro','Focusrite Scarlett 2i2 — 2nd Gen','Audio-Technica AT2035'])
        second=agent.chat('Only during recording.',first['session_id'])
        self.assertEqual(second['intent'],'troubleshoot')
        self.assertEqual(second['troubleshooting_status'],'awaiting_outcome')
        self.assertIn(step,second['answer'])
        third=agent.chat("That didn't work.",first['session_id'])
        self.assertNotIn(step,third['answer'])
        state=agent.session(first['session_id'])
        self.assertEqual(state['steps'][0]['outcome'],'failed')
        self.assertEqual(state['goal'],'Why do I hear my voice twice while recording?')

    def test_next_action_not_blocked_by_unknown_installed_version(self):
        from unittest.mock import Mock
        from app.services.evidence_evaluator import evaluate
        state={'intent':'troubleshoot','goal':'Voice twice only during recording', 'equipment':['Logic Pro'], 'messages':[], 'steps':[], 'version':None, 'evidence':[{'id':'W1','source_type':'official','text':'Synthetic documented reversible action.'}]}
        model=Mock(spec=['complete'])
        model.complete.return_value={**assessment(), 'sufficient':False, 'version_relevant':False,
            'clarification_needed':True,'clarification_question':'Which version?', 'next_action_supported':True}
        result=evaluate(model,state)
        self.assertTrue(result['sufficient'])
        self.assertFalse(result['clarification_needed'])
        model.complete.return_value={**model.complete.return_value,'contradictory':True}
        self.assertFalse(evaluate(model,state)['sufficient'])
        model.complete.return_value={**model.complete.return_value,'contradictory':False}
        self.assertFalse(evaluate(model,{**state,'version':'an explicitly incompatible version'})['sufficient'])
