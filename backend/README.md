# Backend developer guide

FastAPI serves source-grounded Q&A and a stateful LangGraph assistant. Nebius provides structured inference, Pinecone retrieves original Studio Knowledge, and Keenable researches documentation and resources.

## Requirements

Python 3.11, uv, and configured Pinecone, Nebius and Keenable accounts. Run commands below from `backend/`.

```sh
uv sync --frozen
cp .env.example .env
```

Set `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `NEBIUS_API_KEY` and `KEENABLE_API_KEY`. Optional model, endpoint and region settings are listed in `.env.example`; process environment values override dotenv values. Keep keys out of frontend configuration and Git.

## Knowledge setup

Build only the original guides, offline:

```sh
uv run --offline python -m app.rag.studio_cli prepare
```

This needs no downloaded manuals and generates A/B/C datasets under ignored `data/studio_processed/`. It does not contact Pinecone. Runtime expects an existing compatible index: `llama-text-embed-v2`, 1,024 dimensions, cosine, `text → chunk_text`, query/passage input types and `truncate=NONE`.

For a new account, these are **explicit cloud operations with usage charges**:

```sh
# Creates/reuses the compatible index and writes five labeled synthetic test records.
uv run python -m app.rag.pinecone_cli integration-test
# Indexes the original guides into all three Studio namespaces.
uv run python -m app.rag.studio_cli index
```

The synthetic namespace is retained. Indexing does not delete stale revision IDs automatically. Do not repeat it to start an already-provisioned demo. Normal chat does not create or populate an index.

## Run

```sh
uv run uvicorn app.main:app --reload --port 8000
```

Use one backend worker. The default frontend origin is `http://localhost:3000`; set the process variable `FRONTEND_ORIGIN` for another origin. Health is credential-independent; chat needs the configured services.

## API

| Endpoint | Purpose |
|---|---|
| `GET /health` | Local health status |
| `POST /ask` | Standalone Studio RAG: `question`, optional `strategy` A/B/C and `top_k` |
| `POST /chat` | Agent: `message`, optional `session_id`, `equipment`, `request_id` |
| `POST /chat/stream` | Same chat body; SSE `progress`, `final` or `error` events |
| `GET /sessions/{session_id}` | Current process-local conversation and diagnostic state |

Interactive schema: `http://localhost:8000/docs`. Same-ID streaming fallback joins the original job; it does not deliberately duplicate model work.

## Routing and grounding

Learn concepts prefer Pinecone strategy B. Product-specific how-tos prioritize applicable official web documentation. Creative goals use conceptual evidence with research fallback. Troubleshoot retains symptoms, questions and action outcomes. Discover researches real links and checks applicable reuse terms. Clarify requests missing context without inventing evidence.

Exact UI instructions require applicable source spans. General guides cannot establish manufacturer controls. Missing essential evidence, material conflicts and unsupported steps are handled explicitly. Research content is untrusted data, never instructions.

## Offline checks

```sh
uv run --offline python -m unittest discover -s tests -v
uv run --offline python scripts/evaluate_agent.py
uv run --offline python scripts/evaluate_agent_golden.py
```

Providers are mocked/scripted in these checks. They do not establish live answer accuracy. `studio_cli evaluate` separately makes live read-only Pinecone queries; `scripts/agent_live_check.py` is an opt-in paid-service smoke check, not part of offline testing.

## Local limits

Checkpoints, request jobs and locks are process-local; restarts lose session continuation. There is no authentication, durable user storage or multi-worker session coordination. Notebook persistence belongs to the browser, not the placeholder backend Notebook module. Optional Langfuse callbacks exist but require separate configuration and redact payloads.

[System architecture](../docs/architecture/system_architecture.md) · [Agent workflows](../docs/architecture/agent_workflows.md) · [RAG architecture](../docs/architecture/rag_architecture.md) · [Evaluation](../evaluations/README.md)
