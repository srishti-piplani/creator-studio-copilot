> Phase 5B publication note: referenced raw Phase 4K/4M traces now reside in a private archive. The public agent dataset points to `verified_source_inventory.json`, which preserves URLs/provenance without excerpts. Historical metrics below are unchanged.

# Phase 5A — Separate RAG and full-agent evaluation

## Scope and datasets

- **Week 2:** `data/golden_questions.json`: 20 RAG-only questions, IDs unchanged, 16 supported and four unsupported by the 12 original Studio Knowledge guides. `rag_answerable`, `relevant_source_ids`, `expected_facts`, and `evaluation_scope: rag_only` are explicit. The old generic `answerable` dataset field is removed.
- **Week 3:** `data/agent_golden_questions.json`: 12 full-agent scenarios. Each supplies turns, setup, intent, evidence status, expected tool behavior, source requirements, answer-quality criteria, clarification policy and linked regressions. There is no expected final model wording.
- Before-change golden questions and retrieval results are preserved in `evaluations/phase5a_baseline/`.

### Week 2 categories

| Category | IDs | Count |
|---|---|---:|
| Factual concepts | q01, q03, q04, q10 | 4 |
| Practical concepts | q02, q07, q08, q12 | 4 |
| Reasoning | q05, q09, q11, q13 | 4 |
| Multiple guides | q06, q14, q15, q16 | 4 |
| Unsupported by Studio Knowledge | q17–q20 | 4 |

IDs above have the `studio-` prefix. All 16 positive questions, facts and expected guide IDs are unchanged. Their expectations were checked against the named local guides; source IDs are validated against the actual Studio Knowledge manifest. No additional factual expectations or source IDs were manufactured.

Only q17 wording changed: “Using Logic Pro 12.3 documentation, explain how to choose automation modes and identify any documented commands or shortcuts that apply.” It no longer assumes a distinct menu command and shortcut for every automation mode. It remains RAG-negative because these guides contain no exact product/version instructions; it is an agent research candidate, not a mandatory refusal.

Other negatives remain meaningful: q18 asks for an absent hardware current specification; q19 requests a universal HDR delivery guarantee that should be challenged rather than accepted; q20 asks for absent current financial data. A full agent may research q18, explain/clarify q19, or handle the scope of q20. None of these RAG labels establishes global assistant answerability.

### Week 3 categories

| IDs | Category | Evidence status |
|---|---|---|
| agent-q01–02 | Phantom power; compressor versus limiter | Known supported by named guides |
| agent-q03 | Logic Pro compressor insertion | Known supported by saved official Apple evidence |
| agent-q04 | Logic Pro automation modes and documented commands | Research required; no presumption of unsupportedness |
| agent-q05 | Warmer vocals | Supported partial creative advice; conditional research |
| agent-q06 | Thin vocal after basic EQ advice | Research candidate; conditional external fallback |
| agent-q07 | Doubled voice, recording-only, uncertain hardware reply | Supported diagnostic approach; saved applicable Focusrite evidence |
| agent-q08 | Monitoring fix failed | Supported diagnostic approach; retain attempted actions |
| agent-q09 | Tutorials to watch | Discover real links; viewing differs from reuse |
| agent-q10 | Tabla loops for YouTube cover | Search and verify applicable terms; permissions not predetermined |
| agent-q11 | AT2035 current consumption | Official research candidate despite being RAG-negative |
| agent-q12 | Guaranteed exact gain position without measurement | Controlled insufficient-evidence-after-research case; supported partial advice allowed |

Known-source references identify saved Phase 4K/4M artifacts, not fresh availability checks. Search candidates have no invented expected source URL or licensing permission. q12 explicitly requires a research record lacking support for the requested guarantee; its benchmark status must never force runtime refusal. Multi-turn follow-ups are conditional on actual assistant turns: a failed fix is only recorded after an action was proposed.

## Validation and results

- **45 focused unit tests passed:** five new dataset/comparability/isolation/metric tests plus 40 existing Studio RAG, Phase 4K, Phase 4M and targeted-intelligence tests.
- Existing `scripts/evaluate_agent.py`: **10/10** scripted-provider graph scenarios passed; zero network calls.
- New `scripts/evaluate_agent_golden.py`: linked policy checks passed for **12/12 scenarios** (20 linked test executions, including repeated shared checks); zero network calls. Details: `evaluations/agent_golden_regressions.json`.
- Read-only live retrieval evaluation: **60 Pinecone searches**, 20 questions across the three existing Studio namespaces. No upsert, corpus regeneration, LLM generation or web search. Results: `evaluations/studio_retrieval.json`.

| Strategy | Previous guide recall@5 | Current guide recall@5 | Current mean / median / p95 query seconds |
|---|---:|---:|---|
| A — studio-small-300 | 1.000 | 1.000 | 0.242 / 0.163 / 0.485 |
| B — studio-medium-500 | 1.000 | 1.000 | 0.149 / 0.129 / 0.235 |
| C — studio-structure-aware | 1.000 | 1.000 | 0.143 / 0.127 / 0.203 |

Recall remains the macro average of expected **guide IDs** found in the top five **chunks**, excluding all four negatives. Positive question wording, expected IDs, denominator (16), and metric formula are identical, so positive recall is comparable. One negative query changed; its individual retrieval results and aggregate all-question latency are not strictly comparable. Network variation also prevents a latency improvement/regression conclusion.

Negative retrieval is **not** negative-answer detection: a vector search always returning related material does not prove that the corpus can answer the request. No negative refusal-accuracy score is claimed.

## Runtime separation

Static inspection and a regression guard found benchmark file/label consumption only in the explicit `studio_cli.retrieval_evaluation` command. Chat routes, routing, prompts, evidence evaluation and answer generation do not load either golden set. The runtime's independent generated `answerable` response field is unchanged. New validation and scenario tooling is evaluation-only; no application behavior, provider, frontend, corpus or Pinecone records were changed.

## Agent review rubric and remaining gaps

For a future controlled live run, record actual turns, tools, evidence, response and latency per scenario. Score each dimension 0 (fails), 1 (partial), or 2 (meets): tool/context choice; evidence applicability/provenance; factual/procedural support; completeness or useful partial answer; clarity and diagnostic progression. Use the per-scenario criteria, not exact wording. Record clarification as appropriate/inappropriate with reasons. Mark untested or unavailable dimensions **not assessed**, not zero or pass. An invented essential UI instruction or invented reuse permission fails groundedness regardless of total score. Separate evidence gaps from model omissions.

The linked runner executes existing synthetic-provider policy tests, **not these exact new conversations**. It does not establish live intent accuracy, complete golden-rubric coverage, retrieval precision, source accessibility or final-answer factuality. For example, AT2035 specification handling and automation commands still require live source review; linked generic insufficiency/version checks alone cannot prove success on those questions. No new paid agent run was necessary for this scope correction.

The small author-designed RAG benchmark has ceiling guide recall; it does not measure passage-level precision, ranking quality, semantic answer completeness or abstention accuracy. Studio guide reference status is not independent human verification. Full-agent success rates remain unmeasured on the new dataset; future live scoring should retain source excerpts and assess licensing separately from resource relevance.

## Reproduce (from backend)

```sh
uv run python -m unittest discover -s tests -p test_golden_evaluations.py
uv run python scripts/evaluate_agent.py
uv run python scripts/evaluate_agent_golden.py
uv run python -m app.rag.studio_cli evaluate
```

Only the last command makes live read-only retrieval calls. Do not run `prepare` or `index` to evaluate these datasets.
