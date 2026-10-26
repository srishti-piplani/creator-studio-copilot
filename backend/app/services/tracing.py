"""Optional Langfuse graph timing traces; redact all input/output payloads."""
import os
from pathlib import Path
from dotenv import dotenv_values


def tracing_callbacks():
    values = {**dotenv_values(Path(__file__).resolve().parents[2] / '.env'), **os.environ}
    if not values.get('LANGFUSE_PUBLIC_KEY') or not values.get('LANGFUSE_SECRET_KEY'):
        return []
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    # No prompts, document contents, user messages or tool payloads in traces.
    Langfuse(public_key=values['LANGFUSE_PUBLIC_KEY'], secret_key=values['LANGFUSE_SECRET_KEY'],
             base_url=values.get('LANGFUSE_BASE_URL') or 'https://cloud.langfuse.com',
             mask=lambda **kwargs: '[redacted]')
    return [CallbackHandler(public_key=values['LANGFUSE_PUBLIC_KEY'])]
