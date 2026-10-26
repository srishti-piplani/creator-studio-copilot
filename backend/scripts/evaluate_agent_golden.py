"""Run linked scripted regressions, not live answer-quality scoring.

Scenario questions are a review rubric. Linked tests exercise related policy
invariants with synthetic provider fixtures; they do not replay every golden turn.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]),
               str(Path(__file__).resolve().parents[1] / 'tests')]
from scripts.golden_sets import ROOT, load_golden


def main():
    rows = load_golden('agent_golden_questions.json', 'full_agent')
    results = []
    for row in rows:
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromNames(row['regression_tests']).run(result)
        results.append({'id': row['id'], 'category': row['category'],
                        'linked_checks_passed': result.wasSuccessful(),
                        'checks_run': result.testsRun,
                        'errors': [message for _, message in result.errors],
                        'failures': [message for _, message in result.failures]})
    report = {
        'evaluation_scope': 'full_agent', 'network_calls': 0,
        'evaluation_type': 'linked scripted-provider policy regressions',
        'limitations': [
            'Not a live execution of these golden questions or an LLM quality score.',
            'Passing linked tests does not verify current source accessibility, '
            'retrieval relevance, factual completeness or every rubric criterion.',
            'Linked policy checks do not provide live answer-quality scores.',
        ],
        'scenarios_with_passing_linked_checks': sum(r['linked_checks_passed'] for r in results),
        'total_scenarios': len(results), 'results': results,
    }
    path = ROOT / 'evaluations/agent_golden_regressions.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}, indent=2))
    return 0 if all(r['linked_checks_passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
