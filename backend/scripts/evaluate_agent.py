"""Run deterministic agent evaluation scenarios; no network calls.

Providers are scripted, while graph execution and checkpointing are real. These
checks measure workflow behavior, not the live model's classification accuracy.
"""
import json
from pathlib import Path
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]),
               str(Path(__file__).resolve().parents[1] / 'tests')]
from test_agent import AgentScenarios

SCENARIOS = {
    'learn_citations': 'Learn a general concept with checked citation IDs',
    'diagnostic_progression': 'Ask one question, retain the answer, suggest a next step',
    'failed_fix_is_not_repeated': 'That did not work retains intent, marks failure, blocks repetition',
    'web_fallback_for_software': 'Software instructions search official documentation',
    'conflicting_sources_stop': 'Contradictory evidence stops supported-step generation',
    'discover_resource_cards': 'Discovery returns URLs and unverified-license labels',
    'timeout_bounded': 'Unavailable web tool terminates without an infinite retry loop',
    'resolved_and_session_isolation': 'Reported success closes diagnosis; other sessions stay separate',
    'missing_evidence': 'Insufficient evidence produces an explicit limitation',
    'repeated_question': 'Previously asked diagnostic question is not repeated',
}


def main():
    results = []
    for name, description in SCENARIOS.items():
        result = unittest.TestResult()
        AgentScenarios('test_' + name).run(result)
        results.append({'id': name, 'scenario': description, 'passed': result.wasSuccessful(),
                        'failures': len(result.failures), 'errors': len(result.errors)})
    report = {'evaluation_type': 'deterministic scripted-provider graph scenarios',
              'network_calls': 0, 'passed': sum(r['passed'] for r in results),
              'total': len(results), 'results': results}
    path = Path(__file__).resolve().parents[2] / 'evaluations/agent_scenarios.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'total': len(results), 'report': str(path)}))
    return 0 if all(r['passed'] for r in results) else 1

if __name__ == '__main__':
    raise SystemExit(main())
