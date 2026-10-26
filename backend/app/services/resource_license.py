"""Conservative extraction of explicit, resource-scoped license statements.

Never derive rights from 'free', a page footer, or a search snippet.
"""
import re


def license_evidence(text, url):
    match = re.search(r'\b(?:this (?:sample pack|sample|loop pack|resource|download)|these (?:samples|loops))\s+(?:is|are)\s+(?:released|licensed)\s+under\s+(CC0(?: 1\.0)?|CC BY(?:-(?:NC|ND|SA)){0,2}(?: 4\.0)?)\b', text, re.I)
    if not match:
        return {}
    # Conflicting restrictions require a human to review the complete terms.
    if re.search(r'except|excluding|third.party|separate licen|not covered|additional restrictions', text, re.I):
        return {}
    return {'license': match.group(1), 'license_verified': True,
            'license_source_url': url}
