"""Evaluation-only dataset validation. Never imported by request workflows."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_golden(filename, scope):
    rows = json.loads((ROOT / 'data' / filename).read_text())
    guides = {g['source_id'] for g in json.loads(
        (ROOT / 'data/studio_knowledge/manifest.json').read_text())['guides']}
    if not isinstance(rows, list) or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Golden records require unique IDs')
    for row in rows:
        if row['evaluation_scope'] != scope:
            raise ValueError('Mixed evaluation scopes')
        if not set(row['relevant_source_ids']) <= guides:
            raise ValueError('Unknown Studio Knowledge source ID')
        if scope == 'rag_only':
            if type(row['rag_answerable']) is not bool or not row['expected_facts']:
                raise ValueError('Explicit RAG answerability and expectations required')
            if bool(row['relevant_source_ids']) != row['rag_answerable']:
                raise ValueError('RAG positives require sources; negatives have none')
            if not row['rag_answerable'] and not row.get('answerability_scope_note'):
                raise ValueError('Negative scope must be explained')
        else:
            if row['answerability']['status'] not in {
                'known_answerable_verified', 'evidence_search_required',
                'insufficient_evidence_after_research',
            }:
                raise ValueError('Unknown agent evidence status')
            if (row['answerability']['status'] == 'insufficient_evidence_after_research'
                    and not row.get('evaluation_conditions')):
                raise ValueError('Post-research insufficiency requires explicit conditions')
            for field in ('user_turns', 'studio_setup', 'expected_tool_behavior',
                          'evidence_requirements', 'answer_quality_criteria',
                          'clarification', 'regression_tests'):
                if not row[field]:
                    raise ValueError(f'Missing {field}')
    return rows
