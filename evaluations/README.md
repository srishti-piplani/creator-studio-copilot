# Evaluation guide

Retrieval coverage, agent policy and live answer quality are separate evaluation questions. Benchmark labels are never runtime routing/refusal rules.

## Retrieval benchmark

`data/golden_questions.json` contains 20 RAG-only questions: 16 supported by the original Studio Knowledge guides and four corpus-negative examples. Each records `evaluation_scope`, `rag_answerable`, expected facts and relevant source IDs. A corpus-negative label does not mean the assistant cannot research that question.

`studio_retrieval.json` preserves the saved read-only Pinecone results: A/B/C source recall@5 **1.000/1.000/1.000**, over **36/24/12** original-guide chunks. Per positive question, recall is expected guide IDs found in the top five chunks divided by expected guide IDs; the report macro-averages over 16 questions. Negatives have null recall and do not enter the denominator.

The `retrieval_baseline/` snapshots preserve earlier comparison data. Positive queries and guide judgments are identical. One negative question was revised to avoid assuming every automation mode has its own command/shortcut. Positive recall is comparable; aggregate latency and that negative's results are not controlled comparisons.

This is a small author-designed benchmark with ceiling guide recall. It does not measure passage precision, ranking utility, final-answer accuracy or refusal correctness. Returning related chunks for a negative does not establish answerability.

To reproduce **live read-only retrieval** from `backend/`:

```sh
uv run python -m app.rag.studio_cli evaluate
```

This incurs Pinecone query usage, but does not upsert, generate answers or search the web. Do not run it just to inspect saved results.

## Agent scenarios

`data/agent_golden_questions.json` defines 12 rubrics: concepts, official procedures, creative advice, multi-turn diagnosis, discovery, licensing, official research and insufficient evidence. Each includes setup, expected tools, evidence/quality requirements and clarification policy. Evidence status distinguishes known support, research candidates and conditional post-research insufficiency; no final LLM wording is prescribed.

From `backend/`, the following are **offline**:

```sh
uv run --offline python scripts/evaluate_agent.py
uv run --offline python scripts/evaluate_agent_golden.py
```

`agent_scenarios.json` records ten real-graph scenarios with synthetic scripted providers. `agent_golden_regressions.json` records linked checks passing for 12 rubric groups. These are policy regressions, **not exact golden-conversation replays or live answer-quality scores**. They do not establish fresh source accessibility, complete rubric coverage or model accuracy.

For a controlled live evaluation, retain actual tool/evidence records privately. Score tool/context choice, source applicability, supported claims, completeness/useful partial help and clarity/progression separately, 0–2 each. Mark unassessed dimensions explicitly. An invented essential UI instruction or permission fails groundedness regardless of aggregate score. Distinguish missing evidence from model omissions.

`verified_source_inventory.json` preserves official URLs and provenance notes for source-backed scenarios. It contains no excerpts and does not claim fresh verification. Original supporting records remain private; the URL inventory alone cannot replay exact historical model inputs.

## Original-guide reproducibility

`studio_preparation.json` records **12 guides, 4,640 words and 36/24/12 chunks**. Preparation needs only original guides/manifest, not private documents. The clean-tree test builds twice, verifies complete retained source coverage/stable output and preserves guide hashes. It is not a new plagiarism or independent technical-accuracy audit.

Current meaningful evidence and safe reproducibility assets are retained here. Development diaries, raw prompts, third-party excerpts and private browser/session dumps are excluded from the public project.
