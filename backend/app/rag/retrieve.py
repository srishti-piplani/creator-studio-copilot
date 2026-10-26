"""Natural-language search with citation fields through integrated embeddings."""

import math

from app.config import SUPPORTED_PRODUCTS
from app.rag.pinecone_records import NAMESPACES, STUDIO_NAMESPACES
from app.rag.pinecone_store import PineconeOperationError, as_dict


def parse_results(response):
    response = as_dict(response)
    passages = []
    for hit in response.get('result', {}).get('hits', []):
        fields = hit.get('fields', {})
        text = fields.get('chunk_text')
        score = hit.get('_score')
        if (not isinstance(text, str) or not isinstance(hit.get('_id'), str)
                or not isinstance(score, (int, float)) or not math.isfinite(score)):
            raise PineconeOperationError('Malformed search result; content suppressed')
        metadata = {key: value for key,value in fields.items() if key != 'chunk_text'}
        required = ('document_id', 'source_id', 'product', 'document_title',
                    'section_title', 'section_id', 'chunk_id', 'configuration', 'chunking_strategy')
        if any(not isinstance(metadata.get(name), str) or not metadata[name] for name in required):
            raise PineconeOperationError('Missing citation metadata in search result')
        for name in ('page_start', 'page_end'):
            page = metadata.get(name)
            if type(page) not in (int, float) or not math.isfinite(page) or page < 1 or int(page) != page:
                raise PineconeOperationError('Invalid citation page range in response')
            metadata[name] = int(page)
        if metadata['page_start'] > metadata['page_end']:
            raise PineconeOperationError('Reversed citation page range in response')
        for name in ('pages', 'body_pages'):
            if name in metadata:
                try:
                    metadata[name] = [int(p) for p in metadata[name]]
                except (ValueError, TypeError):
                    raise PineconeOperationError('Invalid citation page list in response') from None
        passages.append({'record_id': hit['_id'], 'score': score, 'text': text, 'metadata': metadata})
    return passages


def search(store, query_text: str, namespace: str, *, top_k=5, product=None, synthetic_only=False):
    if namespace not in {*NAMESPACES.values(), *STUDIO_NAMESPACES.values(), 'integration-test'}:
        raise ValueError('Unsupported namespace')
    if not isinstance(query_text,str) or not query_text.strip() or len(query_text) > 4000:
        raise ValueError('Query must contain 1–4000 characters')
    if type(top_k) is not int or not 1 <= top_k <= 100:
        raise ValueError('top_k must be between 1 and 100')
    if store.index is None:
        raise ValueError('Connect to a compatible index first')
    query = {'inputs': {'text': query_text}, 'top_k': top_k}
    filters = []
    if product is not None:
        if product not in SUPPORTED_PRODUCTS:
            raise ValueError('Unsupported product filter')
        filters.append({'applies_to': {'$in': [product]}} if namespace in STUDIO_NAMESPACES.values()
                       else {'product': {'$eq': product}})
    if synthetic_only:
        filters.append({'synthetic': {'$eq': True}})
    if filters:
        query['filter'] = filters[0] if len(filters)==1 else {'$and': filters}
    response = store.call(lambda: store.index.search(namespace=namespace, query=query, fields=['*']))
    return parse_results(response)
