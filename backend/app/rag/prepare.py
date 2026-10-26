"""Shared deterministic JSONL and source-coverage helpers for Studio preparation.

The historical manual-selection CLI is archived outside the public repository.
"""
import json
from pathlib import Path


def write_jsonl(path: Path, records: list[dict]):
    path.write_text(''.join(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n'
                            for record in records), encoding='utf-8')


def verify_source_coverage(sections, chunks):
    """Check complete source-body coverage, not merely equal section-ID sets."""
    lookup = {(s.metadata['section_id'], s.metadata['section_part']): s for s in sections}
    intervals = {key: [] for key in lookup}
    for chunk in chunks:
        meta = chunk.metadata
        key = (meta['section_id'], meta['section_part'])
        section = lookup[key]
        start, end = meta['body_start'], meta['body_end']
        if not 0 <= start < end <= len(section.text):
            raise ValueError('Invalid chunk source offsets')
        if not chunk.text.endswith(section.text[start:end].strip()):
            raise ValueError('Chunk body differs from its cleaned source')
        intervals[key].append((start, end))
    for key, spans in intervals.items():
        text = lookup[key].text
        cursor = 0
        for start, end in sorted(spans):
            if start > cursor and text[cursor:start].strip():
                raise ValueError('Chunk configuration omits retained source text')
            cursor = max(cursor, end)
        if text[cursor:].strip():
            raise ValueError('Chunk configuration omits the end of retained source text')
    return True
