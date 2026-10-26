"""Small beginner check for the specifically selected Scarlett 2i2 2nd Gen.

Control/location claims are gated by the applicable live official article section.
No manual text is indexed or used to invent a device control.
"""
import re
from difflib import SequenceMatcher
from app.graph.provenance import plain

REFERENCE = 'https://support.focusrite.com/hc/en-gb/articles/206849879-Input-Signal-audible-when-not-recording-or-software-closed'
SWITCH_QUESTION = 'On your Scarlett 2i2, is the DIRECT MONITOR switch set to ON or OFF?'
LABEL_QUESTION = 'Can you see the DIRECT MONITOR label on the front of the Scarlett 2i2?'


def matches_setup(state):
    return (state.get('intent') == 'troubleshoot'
            and any('2i2' in e.lower() and '2nd' in e.lower() for e in state.get('equipment', []))
            and bool(re.search(r'twice|doubl|echo', state.get('goal', ''), re.I)))


def applicable_section(text):
    text = plain(text)
    start = re.search(r'Scarlett Solo,\s*2i2\s*\(1st and 2nd Gen\)', text, re.I)
    if not start:
        return None
    section = re.split(r'Scarlett 2i4|Interfaces that use', text[start.start():], maxsplit=1, flags=re.I)[0]
    return section if re.search(r'Direct Monitor switch.*front of the hardware', section, re.I) else None


def switch_reply(state):
    """Resolve a short answer only against the most recent pending switch question."""
    if not matches_setup(state) or state.get('status') in ('resolved', 'awaiting_outcome'):
        return None
    messages, asked = state.get('messages', []), state.get('questions_asked', [])
    if len(messages) < 2 or not asked or messages[-2]['role'] != 'assistant':
        return None
    question = plain(asked[-1])
    if (question not in plain(messages[-2]['content'])
            or not re.search(r'direct monitor.*switch', question, re.I)
            or not re.search(r'\bon\b.*\boff\b', question, re.I)):
        return None
    answer = plain(messages[-1]['content'])
    match = re.fullmatch(r"(?:yes[, ]+)?(?:(?:it(?:'s| is)|the switch is|direct monitor is) )?"
                         r"(on|off|enabled|disabled)[.! ]*", answer, re.I)
    if not match:
        return None
    return 'on' if match[1].lower() in ('on', 'enabled') else 'off'


def monitoring_outcome(state):
    """Outcome replies belong to this action, not a new troubleshooting topic."""
    if not matches_setup(state) or not any(
            s.get('action_key') == MONITORING_ACTION_KEY and s['outcome'] == 'pending'
            for s in state.get('steps', [])):
        return None
    text = plain(state['messages'][-1]['content'])
    if re.fullmatch(r'(?:that fixed it|fixed|it works now|the doubling (?:is gone|disappeared))[.! ]*', text, re.I):
        return 'resolved'
    if re.fullmatch(r"(?:still doubled|still (?:hearing|hear) (?:it|my voice) twice|that did(?: not|n't) work)[.! ]*", text, re.I):
        return 'failed'
    return None


def beginner_check(state):
    if not matches_setup(state) or state.get('status') == 'resolved':
        return None
    asked = state.get('questions_asked', [])
    def was_asked(question):
        return any(SequenceMatcher(None, question.casefold(), old.casefold()).ratio() > .82 for old in asked)
    latest = state['messages'][-1]['content'].strip()
    unknown = bool(re.fullmatch(r"(?:i don.t know|i.?m not sure|not sure|unsure)[.! ]*", latest, re.I))
    proof = next((e for e in state['evidence'] if e.get('hardware_generation') == '2nd Gen'
                  and e.get('product') == 'Focusrite Scarlett 2i2'
                  and e.get('evidence_type') == 'official_product_documentation'
                  and applicable_section(e.get('text',''))), None)
    if proof:
        if not was_asked(SWITCH_QUESTION) and not re.search(r'direct monitor.{0,30}\b(?:on|off)\b', latest, re.I):
            return ('Two copies of your voice can come from monitoring in two places; that is only a possible cause. '
                    + SWITCH_QUESTION + ' It is fine to say "I\'m not sure."', SWITCH_QUESTION, proof['id'])
        if was_asked(SWITCH_QUESTION) and not was_asked(LABEL_QUESTION) and unknown:
            return ('Look at the front of the Scarlett 2i2 for the switch labelled DIRECT MONITOR. '
                    + LABEL_QUESTION + ' You do not need to change anything yet.', LABEL_QUESTION, proof['id'])
    # No verified location, or the user still cannot identify it: observe a cable,
    # rather than asking a beginner to reason about two abstract signal paths.
    if unknown:
        for question in ['Are your headphones plugged into the Scarlett 2i2 or into your Mac?',
                         'Can you see where your headphone cable plugs in?']:
            if not was_asked(question):
                return (question + ' It is fine to say "I\'m not sure."', question, None)
    return None


MONITORING_ACTION_KEY = 'isolate_2i2_direct_monitoring'


def isolation_test(state):
    """Promote an answered switch check or delayed doubling to a reversible test.

    Only user answers establish readiness: a question mentioning delay alone is
    not confirmation. Existing steps/outcomes represent waiting and completion.
    """
    if not matches_setup(state) or state.get('status') == 'resolved':
        return None
    if (state.get('evaluation') or {}).get('contradictory'):
        return None
    messages = state.get('messages', [])
    headphones, delayed = False, False
    for index, message in enumerate(messages):
        if message['role'] != 'user':
            continue
        text = message['content'].strip()
        previous = messages[index - 1]['content'] if index and messages[index - 1]['role'] == 'assistant' else ''
        if re.search(r'headphones?', previous, re.I) and re.search(r'scarlett|interface|2i2', text, re.I):
            headphones = not bool(re.search(r'not.{0,15}(?:scarlett|interface|2i2)', text, re.I))
        if re.search(r'headphones?.{0,60}(?:scarlett|2i2)', text, re.I):
            headphones = True
        if re.search(r'delay|later', previous, re.I) and re.fullmatch(r'yes[.! ]*', text, re.I):
            delayed = True
        if re.search(r'(?:copy|voice|duplicate).{0,30}(?:is |sounds? )?(?:slightly )?delayed', text, re.I):
            delayed = True
    if not (switch_reply(state) == 'on' or (headphones and delayed)):
        return None
    steps = state.get('steps', [])
    if steps:
        # Never replace an outstanding action or retry an attempted fix.
        return None
    proof = next((e for e in state.get('evidence', [])
                  if e.get('url') == REFERENCE
                  and e.get('hardware_generation') == '2nd Gen'
                  and e.get('product') == 'Focusrite Scarlett 2i2'
                  and e.get('evidence_type') == 'official_product_documentation'
                  and applicable_section(e.get('text', ''))
                  and re.search(r'Direct Monitor switch to [\" ]*Off', applicable_section(e['text']), re.I)), None)
    if not proof:
        return None
    return proof
