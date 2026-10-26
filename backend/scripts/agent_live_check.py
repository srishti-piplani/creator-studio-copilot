"""Opt-in live smoke checks. Sends user questions and original Studio knowledge only.

Run from backend: uv run python scripts/agent_live_check.py
Calls Nebius, Pinecone search, and Keenable; never performs upserts.
"""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.graph.workflow import get_agent_service
from app.rag.generate import ChatError
from app.rag.pinecone_store import PineconeOperationError


def main():
    agent = get_agent_service()
    records = []
    scenarios = [
        ('learn', 'Explain how EQ differs from compression.', None, None),
        ('troubleshoot', 'My microphone recording is silent in Logic Pro. Help me diagnose this. I use a Scarlett Solo 4th Gen and AT2020.', None, ['Logic Pro', 'Focusrite Scarlett Solo', 'Audio-Technica AT2020']),
        ('follow_up', "That didn't work. There is still no input signal.", 'previous', None),
        ('discover', 'Find two useful official Logic Pro recording tutorials.', None, ['Logic Pro']),
    ]
    previous = None
    for label, message, session, equipment in scenarios:
        started = time.perf_counter()
        try:
            result = agent.chat(message, previous if session == 'previous' else None, equipment)
            if label == 'troubleshoot':
                previous = result['session_id']
            records.append({'scenario': label, 'seconds': round(time.perf_counter() - started, 3),
                            'response': result})
            print(json.dumps({'scenario': label, 'intent': result['intent'],
                'status': result['troubleshooting_status'], 'citations': len(result['citations']),
                'cards': len(result['resource_cards']), 'seconds': records[-1]['seconds']}), flush=True)
        except (ChatError, PineconeOperationError, ValueError, KeyError) as exc:
            # These service exceptions contain sanitized messages only.
            records.append({'scenario': label, 'error': str(exc),
                            'seconds': round(time.perf_counter() - started, 3)})
            print(json.dumps({'scenario': label, 'error': str(exc)}), flush=True)
    path = Path(__file__).resolve().parents[2] / 'evaluations/agent_live_results.json'
    path.write_text(json.dumps({'kind': 'live smoke checks, not an accuracy benchmark',
                               'results': records}, indent=2) + '\n')

if __name__ == '__main__':
    main()
