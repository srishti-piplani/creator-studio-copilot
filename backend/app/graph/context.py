"""Small context guards for the supported studio setup; no additional memory store."""
import re

SOFTWARE = ('Logic Pro', 'DaVinci Resolve')
REFERENCE_VERSIONS = {'Logic Pro': '12.3', 'DaVinci Resolve': '21.1'}
SHORT_REPLY = re.compile(r'^(?:(?:logic pro|davinci resolve|usb(?:[- ][abc])?|thunderbolt|yes|no|yeah|nope|ok|okay|that (?:did not|didn.t) work|that worked|scarlett (?:2i2|solo)(?:[ ,—-]*(?:2nd|4th) gen)?|(?:audio-technica )?at20(?:20|35))[\s,./!?—-]*)+$', re.I)


def clarification_reply(message):
    return bool(SHORT_REPLY.fullmatch(message.strip())) or bool(re.fullmatch(r"(?:i don.t know|i.?m not sure|not sure|unsure|on|off)[.! ]*", message.strip(), re.I))


def category(label):
    lower = label.lower()
    if 'at2020' in lower or 'at2035' in lower:
        return 'microphone'
    if 'scarlett' in lower:
        return 'interface'
    return None


def merge_equipment(current, routed, message):
    """An omitted model field must not erase setup; explicit changes win a category."""
    result = list(current)
    for kind, mention in [('microphone', r'\bat[ -]?20(?:20|35)\b'),
                          ('interface', r'\b(?:scarlett|2i2|solo)\b')]:
        candidates = [item for item in routed if category(item) == kind]
        existing = [item for item in current if category(item) == kind]
        if candidates and (not existing or re.search(mention, message, re.I)):
            # Retain known generation when a reply only repeats the same product name.
            selected = [next((old for old in existing if item.lower() in old.lower()), item) for item in candidates]
            result = [item for item in result if category(item) != kind] + selected
    for item in routed:
        if category(item) is None and item not in result:
            result.append(item)
    return list(dict.fromkeys(result))


def studio_context(state):
    equipment = state.get('equipment', [])
    available = [name for name in SOFTWARE if any(name.lower() in item.lower() for item in equipment)]
    goal = state.get('goal', '')
    latest = (state.get('messages') or [{}])[-1].get('content', '')
    explicit = next((name for name in available if name.lower() in latest.lower()), None)
    primary = explicit or state.get('primary_software') or next((name for name in available if name.lower() in goal.lower()), None)
    if not primary:
        primary = ('DaVinci Resolve' if re.search(r'video|color grad|timeline|footage', goal, re.I)
                   and 'DaVinci Resolve' in available else 'Logic Pro' if 'Logic Pro' in available else None)
    usb_2i2 = any('2i2' in item.lower() and '2nd' in item.lower() for item in equipment)
    return {'primary_software': primary, 'equipment': equipment,
            'documentation_versions': {name: REFERENCE_VERSIONS[name] for name in available},
            'installed_software_version': state.get('version'),
            # Verified against the already registered 2nd Gen manual, PDF p.5.
            'interface_connection': 'USB (not Thunderbolt)' if usb_2i2 else None}


def redundant_setup_question(question, state):
    question = question or ''
    context = studio_context(state)
    if context['primary_software'] and re.search(r'\b(which|what)\b.*\b(daw|software|recording (?:app|application))\b|\b(?:daw|software)\b.*\busing\b', question, re.I):
        return True
    return bool(context['interface_connection'] and re.search(
        r'usb.*thunderbolt|thunderbolt.*usb|(?:which|what).*\b(?:bus|connection type|interface connection)\b', question, re.I))


def context_issues(draft, state):
    data = draft.model_dump()
    issues = []
    if redundant_setup_question(data.get('diagnostic_question'), state):
        issues.append('The setup already answers this question. Use studio_context and ask a different discriminating question or give a supported step.')
    text = ' '.join(str(value) for key, value in data.items() if key not in ('citation_ids', 'resource_ids', 'relevance', 'diagnostic_question'))
    context = studio_context(state)
    if context['interface_connection'] and re.search(r'\bthunderbolt\b', text, re.I) and not re.search(r'not (?:a )?thunderbolt', text, re.I):
        issues.append('The selected Scarlett 2i2 2nd Gen connects using USB, not Thunderbolt. Do not suggest Thunderbolt-only actions or ask which transport it uses.')
    if data.get('step') and context['primary_software'] and re.search(r'\bmonitoring\b', data['step'], re.I) and not re.search(r'>|track header|control bar|settings|preferences|menu|mixer|channel strip|not verified|could not verify', data['step'], re.I):
        issues.append('Give the supported control location in the selected software, or explicitly state its location could not be verified; do not offer an unexplained generic monitoring toggle.')
    if data.get('step') and context['primary_software'] and re.search(r'\byour daw\b', data['step'], re.I):
        issues.append(f"Name {context['primary_software']} instead of 'your DAW'. Give exact controls only when verified; otherwise state that their location could not be verified.")
    return issues


CONTEXT_PROMPT = '''Use studio_context consistently. Its software versions are DOCUMENTATION references,
not detected installed versions. For audio work use its primary software name (e.g. Logic Pro),
not 'your DAW'. Do not ask for known software, microphone, interface generation, or connection.
The selected Scarlett 2i2 2nd Gen is USB, not Thunderbolt. A cable/hub fault can still be diagnosed;
do not confuse that with asking which transport the interface supports. Explicit user equipment
or software statements override saved defaults. Do not assume the same cause for every symptom.
Exact UI controls and locations need supporting official evidence; if missing, search or say that
the location is unverified instead of inventing it. Ask one new symptom-related question at a time.'''
