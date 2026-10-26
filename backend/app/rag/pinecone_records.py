"""Validate and project existing chunk JSONL into flat Pinecone text records."""

import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from app.config import SUPPORTED_PRODUCTS

NAMESPACES = {'A': 'small-300', 'B': 'medium-500', 'C': 'structure-aware'}
STUDIO_NAMESPACES = {'A': 'studio-small-300', 'B': 'studio-medium-500', 'C': 'studio-structure-aware'}
REQUIRED = ('document_id', 'source_id', 'product', 'document_title', 'section_id',
            'section_title', 'chunk_id', 'chunking_strategy', 'configuration')
OPTIONAL = ('version', 'software_version', 'hardware_generation', 'topic',
            'pipeline_version', 'source_sha256', 'token_count', 'synthetic',
            'corpus', 'guide_path', 'authorship', 'page_reference_type',
            'source_line_start', 'source_line_end')


def namespace_for(configuration: str) -> str:
    if configuration not in NAMESPACES:
        raise ValueError('Configuration must be A, B, or C')
    return NAMESPACES[configuration]


def record_id(metadata: dict) -> str:
    """Keep upstream chunk identity and configuration stable across retries/reruns."""
    identity = json.dumps([metadata['source_id'], metadata['configuration'], metadata['chunk_id']],
                          separators=(',', ':'))
    return 'csc-' + hashlib.sha256(identity.encode()).hexdigest()


def to_record(chunk: dict, configuration: str, *, synthetic_only=False) -> dict:
    namespace_for(configuration)
    text, meta = chunk.get('text'), chunk.get('metadata')
    if not isinstance(text, str) or not text.strip() or not isinstance(meta, dict):
        raise ValueError('Each chunk needs nonempty text and metadata')
    if '\ufffd' in text or any(0x7f <= ord(c) <= 0x9f for c in text):
        raise ValueError('Unresolved character corruption in chunk')
    for name in REQUIRED:
        if not isinstance(meta.get(name), str) or not meta[name].strip():
            raise ValueError(f'Missing or invalid metadata field: {name}')
    studio = (meta.get('corpus') == 'studio-original' and meta['product'] == 'Studio fundamentals'
              and meta['source_id'].startswith('studio-'))
    if meta['product'] not in SUPPORTED_PRODUCTS and not studio:
        raise ValueError('Unsupported product')
    expected_strategy = 'structure' if configuration == 'C' else 'fixed'
    if meta['configuration'] != configuration or meta['chunking_strategy'] != expected_strategy:
        raise ValueError('Dataset configuration/strategy mismatch')
    if synthetic_only and (meta.get('synthetic') is not True
                           or not meta['source_id'].startswith('synthetic-')
                           or not text.startswith('SYNTHETIC TEST ONLY:')):
        raise ValueError('Integration namespace accepts labeled synthetic fixtures only')
    fields = {name: meta[name] for name in REQUIRED}
    for name in OPTIONAL:
        value = meta.get(name)
        if value is None:
            continue  # Pinecone metadata has no null type; unknown versions stay unknown.
        if not isinstance(value, (str, int, float, bool)) or isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f'Invalid scalar metadata: {name}')
        fields[name] = value
    fields['version_known'] = any(meta.get(name) for name in ('version', 'software_version', 'hardware_generation'))
    url = meta.get('source_url')
    if url is not None:
        if not isinstance(url, str) or (urlparse(url).scheme not in ('https', 'http')
                                       and not (studio and url == 'studio://' + meta['source_id'])) or not urlparse(url).netloc:
            raise ValueError('Invalid source URL')
        fields['source_url'] = url
    for name in ('reference_urls', 'applies_to'):
        if name in meta:
            values = meta[name]
            if not studio or not isinstance(values,list) or not values or any(not isinstance(v,str) for v in values):
                raise ValueError('Invalid Studio list metadata')
            if name == 'reference_urls' and any(urlparse(v).scheme not in ('http','https') or not urlparse(v).netloc for v in values):
                raise ValueError('Invalid reference URL')
            if name == 'applies_to' and any(v not in SUPPORTED_PRODUCTS for v in values):
                raise ValueError('Unsupported Studio product')
            fields[name] = values
    for name in ('page_start', 'page_end'):
        value = meta.get(name)
        if type(value) is not int or value < 1:
            raise ValueError(f'Invalid page reference: {name}')
        fields[name] = value
    if fields['page_start'] > fields['page_end']:
        raise ValueError('Invalid page range')
    for name in ('pages', 'body_pages'):
        if name in meta:
            pages = meta[name]
            if not isinstance(pages, list) or not pages or any(type(p) is not int or p < 1 for p in pages):
                raise ValueError('Invalid page list')
            if any(p < fields['page_start'] or p > fields['page_end'] for p in pages):
                raise ValueError('Page list outside cited range')
            fields[name] = [str(p) for p in pages]  # Records API permits lists of strings, not numbers.
    fields['chunk_text'] = text
    if len(json.dumps(fields, ensure_ascii=False).encode()) > 40 * 1024:
        raise ValueError('Record fields exceed conservative 40 KiB metadata limit')
    return {'_id': record_id(meta), **fields}


def load_records(path: Path, configuration: str) -> list[dict]:
    records = []
    seen = set()
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = to_record(json.loads(line), configuration)
        except (ValueError, TypeError, KeyError):
            raise ValueError(f'Invalid chunk record on line {line_number}') from None
        if record['_id'] in seen:
            raise ValueError(f'Duplicate chunk ID on line {line_number}')
        seen.add(record['_id'])
        records.append(record)
    return records
