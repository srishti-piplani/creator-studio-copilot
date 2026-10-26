"""Product scope and on-demand Pinecone settings."""

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import dotenv_values


SUPPORTED_PRODUCTS = (
    'Logic Pro',
    'DaVinci Resolve',
    'Focusrite Scarlett Solo',
    'Focusrite Scarlett 2i2',
    'Audio-Technica AT2020',
    'Audio-Technica AT2035',
)

EXCLUDED_CORPUS_DIRECTORIES = {'garageband', 'imovie'}


# Explicitly loaded on demand; importing the FastAPI health endpoint needs no key.

@dataclass(frozen=True)
class PineconeSettings:
    api_key: str = field(repr=False)
    index_name: str = 'creator-studio-copilot'
    model: str = 'llama-text-embed-v2'
    dimension: int = 1024
    cloud: str = 'aws'
    region: str = 'us-east-1'

    @classmethod
    def from_env(cls):
        values = {**dotenv_values(Path(__file__).resolve().parents[1] / '.env'), **os.environ}
        key = values.get('PINECONE_API_KEY')
        if not key:
            raise ValueError('PINECONE_API_KEY is required for Pinecone commands')
        return cls(api_key=key,
                   index_name=values.get('PINECONE_INDEX_NAME') or 'creator-studio-copilot',
                   cloud=values.get('PINECONE_CLOUD') or 'aws',
                   region=values.get('PINECONE_REGION') or 'us-east-1')


@dataclass(frozen=True)
class ChatSettings:
    api_key: str = field(repr=False)
    # Identifier verified through authenticated Nebius model discovery on 2026-10-24.
    model: str = 'Qwen/Qwen3-30B-A3B-Instruct-2507'
    base_url: str = 'https://api.tokenfactory.nebius.com/v1'

    @classmethod
    def from_env(cls):
        values = {**dotenv_values(Path(__file__).resolve().parents[1] / '.env'), **os.environ}
        key=values.get('NEBIUS_API_KEY')
        if not key:
            raise ValueError('NEBIUS_API_KEY is required for grounded chat; no provider key is supplied to the model')
        base=values.get('NEBIUS_BASE_URL') or cls.base_url
        if base.rstrip('/') not in ('https://api.tokenfactory.nebius.com/v1','https://api.studio.nebius.ai/v1'):
            raise ValueError('Nebius endpoint must be a verified official API URL')
        return cls(api_key=key,model=values.get('NEBIUS_MODEL') or cls.model,base_url=base.rstrip('/'))
