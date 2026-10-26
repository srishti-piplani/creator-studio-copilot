"""Server-derived source provenance and literal evidence-span checks."""
import re
import unicodedata
from urllib.parse import urlsplit
from app.tools.web_search import official_source, public_url


def plain(text):
    text = re.sub(r'!\[[^]]*\]\([^)]*\)', '', text)
    text = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', text)
    text = unicodedata.normalize('NFKC', text).translate(str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"'}))
    return ' '.join(text.replace('**', '').split())


def provenance(item, product=None):
    """A Studio reference URL is never proof that its guide is official."""
    row = dict(item)
    if row.get('kind') == 'general_concepts' or row.get('source_type') == 'original_studio_knowledge':
        row.update(evidence_type='studio_concept', source_type='original_studio_knowledge')
        return row
    url = row.get('url', '')
    identity = (row.get('title', '') + ' ' + url).lower()
    identified = bool(product and (product.lower() in identity or
        (product == 'Logic Pro' and '/logicpro/' in url) or
        (product == 'DaVinci Resolve' and 'resolve' in identity)))
    if public_url(url) and official_source(url, product) and identified:
        row.update(evidence_type='official_product_documentation', source_type='official', product=product)
        match = re.search(r'/([0-9]+(?:\.[0-9]+)+)/mac(?:/|$)', urlsplit(url).path)
        row['documentation_version'] = match.group(1) if match else None
        if product == 'Logic Pro' and ('logicpro-ipad' in url.lower() or 'for ipad' in row.get('title', '').lower()):
            row['product'] = 'Logic Pro for iPad'
            row['platform'] = 'iPad'
    else:
        row['evidence_type'] = 'community_tutorial' if row.get('source_type') == 'community' and public_url(url) else 'unknown'
        row['source_type'] = 'community' if row['evidence_type'] == 'community_tutorial' else 'unknown'
    return row


def valid_span(span, evidence, *, product=None, version=None, require_official=False):
    row = next((e for e in evidence if e['id'] == span.source_id), None)
    if not row or len(plain(span.quote)) < 12 or re.search(r'https?://', plain(span.quote)):
        return False
    if plain(span.quote) not in plain(row.get('text', '')):
        return False
    if require_official:
        row = provenance(row, product)
        if row.get('evidence_type') != 'official_product_documentation' or row.get('product') != product:
            return False
        if version and row.get('documentation_version') != version:
            return False
    return True


def has_ui_controls(text):
    return bool(re.search(r'>|\b(settings|preferences|checkbox|button|menu|slot|knob|switch|channel strip|track header|control bar)\b', text, re.I))


def concept_claim_issues(draft, state):
    """A conceptual answer cannot sneak an ungrounded UI instruction past review."""
    data = draft.model_dump()
    if 'takeaway' not in data:
        return []
    text = ' '.join([data['takeaway'], *data.get('key_points', []), data.get('practical_example') or ''])
    cited = [e for e in state['evidence'] if e['id'] in data.get('citation_ids', [])]
    product = state.get('primary_software')
    if re.search(r'official\s+(?:Apple|Focusrite|product|documentation|guide)', text, re.I) and not any(
            provenance(e, product).get('evidence_type') == 'official_product_documentation' for e in cited):
        return ['Do not label original Studio Knowledge or unverified sources as official product documentation.']
    for sentence in re.split(r'[.!?\n]', text):
        if has_ui_controls(sentence) and re.search(r'\b(click|choose|select|deselect|open|toggle|turn)\b', sentence, re.I):
            candidate = re.sub(r'\[[KW]\d+\]', '', sentence).strip()
            # Span-shaped object keeps this guard independent of generation schemas.
            from types import SimpleNamespace
            if not any(valid_span(SimpleNamespace(source_id=e['id'], quote=candidate), cited,
                       product=product, version=state.get('version'), require_official=True) for e in cited):
                return ['Omit the unrequested UI instruction: exact control wording lacks an applicable cited official source span.']
    return []
