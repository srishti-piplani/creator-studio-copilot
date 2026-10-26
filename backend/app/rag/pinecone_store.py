"""SDK 7.3 integrated-embedding Records API; no manual embedding calls."""

import json
import os
from collections.abc import Mapping
from enum import Enum
from dataclasses import fields, is_dataclass
import time

from pinecone import Pinecone
from urllib3.exceptions import HTTPError

from app.config import PineconeSettings
from app.rag.pinecone_records import NAMESPACES, STUDIO_NAMESPACES


class PineconeOperationError(RuntimeError):
    """Safe error containing no API response body, request text or credentials."""


def as_dict(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: as_dict(getattr(value, field.name)) for field in fields(value)}
    if callable(getattr(value, 'to_dict', None)):
        return as_dict(value.to_dict())
    if isinstance(value, Mapping):
        return {key: as_dict(item) for key,item in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_dict(item) for item in value]
    # SDK 7.3 represents OpenAPI oneOf values (e.g. supported_metrics)
    # using lightweight objects with a public value attribute.
    if hasattr(value, 'value'):
        return as_dict(value.value)
    raise TypeError(f'Unsupported SDK response type: {type(value).__name__}')


def with_retry(operation, *, attempts=3, sleep=time.sleep):
    if not 1 <= attempts <= 5:
        raise ValueError('Retries must be between one and five attempts')
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as error:
            status = getattr(error, 'status', None)
            transient = status == 429 or isinstance(status, int) and 500 <= status <= 599
            transient = transient or isinstance(error, (HTTPError, TimeoutError, ConnectionError))
            if not transient or attempt == attempts-1:
                code = str(status) if type(status) is int else 'network-or-sdk'
                raise PineconeOperationError(f'Pinecone operation failed ({code}); request/response details suppressed') from None
            sleep(min(2**attempt, 4))


def check_compatible(description: dict, settings: PineconeSettings):
    description = as_dict(description)
    embed = description.get('embed') or {}
    if (description.get('vector_type') != 'dense'
            or description.get('dimension') != settings.dimension
            or description.get('metric') != 'cosine'
            or embed.get('model') != settings.model
            or embed.get('field_map') != {'text': 'chunk_text'}
            or not description.get('spec', {}).get('serverless')):
        raise ValueError('Existing index is incompatible; it was not modified. Choose a dedicated compatible index name.')
    for name, input_type in [('read_parameters', 'query'), ('write_parameters', 'passage')]:
        parameters = embed.get(name) or {}
        if parameters.get('truncate') != 'NONE' or parameters.get('input_type') != input_type:
            raise ValueError('Existing embedding parameters are incompatible (requires correct input_type and truncate=NONE); index unchanged.')
        if parameters.get('dimension', settings.dimension) != settings.dimension:
            raise ValueError('Embedding dimension parameters are incompatible; index unchanged.')


class PineconeStore:
    def __init__(self, settings: PineconeSettings, *, client=None, sleep=time.sleep):
        if os.environ.get('PINECONE_DEBUG_CURL'):
            raise ValueError('Disable PINECONE_DEBUG_CURL before using the client to prevent credential logging')
        self.settings = settings
        self.client = client if client is not None else Pinecone(api_key=settings.api_key)
        self.index = None
        self.sleep = sleep

    def call(self, operation):
        return with_retry(operation, sleep=self.sleep)

    def ensure_index(self, *, create=True):
        """List before creating; reject incompatible indexes without reconfiguration."""
        names = self.call(self.client.list_indexes).names()
        if self.settings.index_name not in names:
            if not create:
                raise ValueError('Configured index does not exist')
            self.call(lambda: self.client.create_index_for_model(
                name=self.settings.index_name, cloud=self.settings.cloud, region=self.settings.region,
                embed={'model': self.settings.model, 'field_map': {'text': 'chunk_text'},
                       'metric': 'cosine',
                       'read_parameters': {'input_type': 'query', 'truncate': 'NONE', 'dimension': self.settings.dimension},
                       'write_parameters': {'input_type': 'passage', 'truncate': 'NONE', 'dimension': self.settings.dimension}},
                deletion_protection='enabled', timeout=60))
        for attempt in range(30):
            description = as_dict(self.call(lambda: self.client.describe_index(self.settings.index_name)))
            check_compatible(description, self.settings)
            if description.get('status', {}).get('ready'):
                self.index = self.client.Index(host=description['host'])
                return description
            if attempt < 29:
                self.sleep(2)
        raise PineconeOperationError('Index readiness timed out; no records uploaded')

    def upsert(self, records, namespace, *, batch_size=32):
        if namespace not in {*NAMESPACES.values(), *STUDIO_NAMESPACES.values(), 'integration-test'}:
            raise ValueError('Unsupported namespace')
        if not 1 <= batch_size <= 96:
            raise ValueError('Text batches must contain 1–96 records')
        if self.index is None:
            raise ValueError('Connect to a compatible index first')
        if namespace == 'integration-test' and any(
                r.get('synthetic') is not True or not r.get('source_id', '').startswith('synthetic-')
                or not r.get('chunk_text', '').startswith('SYNTHETIC TEST ONLY:') for r in records):
            raise ValueError('Only labeled synthetic fixtures may enter integration-test')
        if namespace in STUDIO_NAMESPACES.values() and any(
                r.get('corpus')!='studio-original' or not r.get('source_id','').startswith('studio-')
                or r.get('product')!='Studio fundamentals' for r in records):
            raise ValueError('Studio namespaces reject manual-derived records')
        expected = next((c for c,n in [*NAMESPACES.items(), *STUDIO_NAMESPACES.items()]
                         if n==namespace), None)
        if expected and any(r.get('configuration') != expected for r in records):
            raise ValueError('Namespace and configuration mismatch')
        batch, size, uploaded = [], 0, 0
        for record in records:
            length = len(json.dumps(record, ensure_ascii=False).encode())
            if length > 40*1024+1024:
                raise ValueError('Oversized text record')
            if batch and (len(batch) >= batch_size or size+length > 1_900_000):
                self.call(lambda: self.index.upsert_records(namespace=namespace, records=batch))
                uploaded += len(batch)
                batch, size = [], 0
            batch.append(record)
            size += length
        if batch:
            self.call(lambda: self.index.upsert_records(namespace=namespace, records=batch))
            uploaded += len(batch)
        return uploaded
