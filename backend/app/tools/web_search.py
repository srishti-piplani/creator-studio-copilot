"""Bounded Keenable REST search. Never executes or follows returned content.

API verified: https://docs.keenable.ai/api-reference/search (2026-10-24).
"""
import ipaddress
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import httpx
from dotenv import dotenv_values

OFFICIAL = {
    'Logic Pro': 'support.apple.com',
    'DaVinci Resolve': 'blackmagicdesign.com',
    'Focusrite Scarlett Solo': 'focusrite.com',
    'Focusrite Scarlett 2i2': 'focusrite.com',
    'Audio-Technica AT2020': 'audio-technica.com',
    'Audio-Technica AT2035': 'audio-technica.com',
}

class WebSearchError(RuntimeError):
    def __init__(self, message, *, category='unknown', status_code=None):
        super().__init__(message)
        self.category = category
        self.status_code = status_code


def public_url(url):
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ''
        if parsed.scheme not in ('https', 'http') or parsed.username or parsed.password or not host:
            return False
        if host == 'localhost' or '.' not in host:
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return not host.endswith(('.local', '.internal'))
    except (TypeError, ValueError):
        return False


def official_source(url, product=None):
    host = (urlsplit(url).hostname or '').lower()
    domains = [OFFICIAL[product]] if product in OFFICIAL else set(OFFICIAL.values())
    return any(host == d or host.endswith('.' + d) for d in domains)


class KeenableSearch:
    def __init__(self, api_key, *, client=None, sleep=time.sleep):
        if not api_key:
            raise ValueError('KEENABLE_API_KEY is required for live search')
        self._api_key = api_key
        self.client = client or httpx.Client(timeout=httpx.Timeout(12, connect=5), follow_redirects=False)
        self.sleep = sleep

    @classmethod
    def from_env(cls):
        values = {**dotenv_values(Path(__file__).resolve().parents[2] / '.env'), **os.environ}
        return cls(values.get('KEENABLE_API_KEY'))

    def search(self, query, *, product=None, official_only=False):
        if not query.strip() or len(query) > 4000:
            raise ValueError('Invalid search query')
        body = {'query': query, 'mode': 'pro', 'max_results': 5, 'snippet_max_length': 3000}
        if official_only and product in OFFICIAL:
            body['site'] = OFFICIAL[product]
        for attempt in range(2):
            try:
                response = self.client.post('https://api.keenable.ai/v1/search',
                    headers={'X-API-Key': self._api_key}, json=body)
                if (response.status_code == 429 or response.status_code >= 500) and attempt == 0:
                    self.sleep(0.5)
                    continue
                if response.status_code != 200:
                    raise WebSearchError('Web search provider rejected the request')
                rows = response.json()['results']
                if not isinstance(rows, list):
                    raise ValueError()
                results = []
                for row in rows[:5]:
                    url = row.get('url')
                    if not public_url(url):
                        continue
                    official = official_source(url, product)
                    if official_only and not official:
                        continue
                    results.append({'title': str(row.get('title', 'Untitled'))[:300],
                        'url': url, 'source': urlsplit(url).hostname,
                        'source_type': 'official' if official else 'community',
                        'description': str(row.get('description') or row.get('snippet') or 'No description supplied by source.')[:600],
                        'text': str(row.get('snippet') or row.get('description') or '')[:3000],
                        'published_at': row.get('published_at'),
                        # Search excerpts alone do not verify a resource's licensing terms.
                        'license': 'License not verified.'})
                return results
            except httpx.TransportError:
                if attempt == 0:
                    continue
                raise WebSearchError('Web search timed out or could not connect') from None
            except (ValueError, KeyError, TypeError, AttributeError):
                raise WebSearchError('Malformed web search response') from None

    def fetch(self, url, *, product=None, resource=False):
        """Read bounded indexed HTML: official documentation or same-host resource terms.

        No live crawl or PDF fetch. Resource pages are untrusted evidence.

        Verified https://docs.keenable.ai/api-reference/fetch . No extraction LLM.
        """
        if not public_url(url) or (not resource and not official_source(url, product)) or '.pdf' in url.lower():
            raise WebSearchError('Only official HTML documentation pages may be read')
        attempts = 1 if resource else 2
        for attempt in range(attempts):
            try:
                response = self.client.get('https://api.keenable.ai/v1/fetch',
                    headers={'X-API-Key': self._api_key}, params={'url': url, 'max_chars': 12000})
                if (response.status_code == 429 or response.status_code >= 500) and attempt + 1 < attempts:
                    self.sleep(0.5)
                    continue
                if response.status_code != 200:
                    raise WebSearchError('Indexed documentation page is unavailable', category='http', status_code=response.status_code)
                data = response.json()
                returned_url = data.get('url') or url
                if not public_url(returned_url) or (not resource and not official_source(returned_url, product)) or (resource and (urlsplit(returned_url).hostname or '').removeprefix('www.') != (urlsplit(url).hostname or '').removeprefix('www.')):
                    raise WebSearchError('Documentation source changed to an unsupported domain', category='source_validation')
                content = data.get('content')
                if not isinstance(content, str) or not content.strip():
                    raise WebSearchError('Documentation page has no usable text', category='extraction')
                return {'text': content[:12000], 'url': returned_url}
            except httpx.TransportError as error:
                if attempt + 1 < attempts:
                    continue
                raise WebSearchError('Documentation request failed', category='timeout' if isinstance(error, httpx.TimeoutException) else 'transport') from None
            except (ValueError, KeyError, TypeError, AttributeError):
                raise WebSearchError('Malformed documentation response', category='parsing') from None
