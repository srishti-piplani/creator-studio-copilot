"""Agent-only schema output adapter around the existing Nebius transport.

Verified against https://docs.tokenfactory.nebius.com/ai-models-inference/json .
The working RAG generator and its JSON-object response contract are unchanged.
"""
import json
from app.rag.generate import ChatError

class AgentChat:
    def __init__(self, transport):
        self.transport = transport

    def complete_structured(self, messages, schema):
        chat = self.transport
        if not chat.verified:
            catalog = chat.request('GET', '/models')
            if chat.settings.model not in {row['id'] for row in catalog.get('data', [])}:
                raise ChatError('Configured agent model is not available')
            chat.verified = True
        result = chat.request('POST', '/chat/completions', json={
            'model': chat.settings.model, 'messages': messages, 'temperature': 0,
            'max_tokens': 2400, 'response_format': {'type': 'json_schema',
                'json_schema': {'name': schema.__name__, 'schema': schema.model_json_schema()}}})
        try:
            return json.loads(result['choices'][0]['message']['content'])
        except (KeyError, IndexError, TypeError, ValueError):
            raise ChatError('Agent model returned malformed structured output') from None
