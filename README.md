# Creator Studio Copilot

A local music/video learning, troubleshooting and resource-discovery assistant. This combined Week 2 RAG / Week 3 agent project uses Next.js, FastAPI, LangGraph, Nebius, Pinecone integrated embeddings and Keenable.

## Local setup

Use Python 3.11, uv and Node 24. From a clean checkout, restore dependencies with `uv sync --frozen` in `backend/` and `npm ci` in `frontend/`. These are setup instructions, not commands automatically run by the app.

Copy `backend/.env.example` to `backend/.env`; supply Pinecone, Nebius and Keenable credentials. Keep secrets backend-only. The frontend defaults to `http://localhost:8000`; its optional `.env.local` may contain only `NEXT_PUBLIC_API_BASE_URL`.

Run in separate terminals:

```sh
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

```sh
cd frontend
npm run dev
```

Open `http://localhost:3000`; health is `/health`, API schema is `/docs`. Use **one backend worker**: diagnostic sessions/checkpoints and streaming jobs are process-local. Browser history and Notebook persist locally, but backend restarts invalidate session continuation. There is no authentication; use localhost for the demo.

## Original Studio Knowledge and Pinecone

The 12 original AI-assisted guides and reviewed references live in `data/studio_knowledge/`. They are general educational material, not official manufacturer instructions or independently human-verified technical advice. Manufacturer PDFs/text are not part of this public repository. No manual is needed for local preparation:

```sh
cd backend
uv run --offline python -m app.rag.studio_cli prepare
```

This local command generates 36 / 24 / 12 chunks for A / B / C and does **not** contact Pinecone. The app uses Studio strategy B, top five passages. Product instructions use applicable official evidence researched through Keenable; concepts use the original-guide RAG.

Chat needs a compatible existing Pinecone index: `llama-text-embed-v2`, 1024 dimensions, cosine, integrated `text → chunk_text`, query/passage inputs with `truncate=NONE`. On a new account, the explicit command below creates/reuses the compatible index and writes **only five labeled synthetic records** to `integration-test`; it makes paid cloud calls and retains that namespace:

```sh
uv run python -m app.rag.pinecone_cli integration-test
```

After reviewing credentials/index selection and approving cloud usage, `uv run python -m app.rag.studio_cli index` indexes **original guides only** into `studio-small-300`, `studio-medium-500`, `studio-structure-aware`. Do not run indexing just to start an already-provisioned demo. Normal requests do not create/repopulate an index. Reindexing does not automatically delete stale revision IDs.

## Offline verification and evaluation

```sh
cd backend
uv run --offline python -m unittest discover -s tests -v
uv run --offline python scripts/evaluate_agent.py
uv run --offline python scripts/evaluate_agent_golden.py
```

```sh
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```

The 20-question `data/golden_questions.json` is **RAG-only**, not a full-agent refusal list. The separate 12-scenario `data/agent_golden_questions.json` evaluates full-agent requirements. Saved guide recall@5 is 1.000 for A/B/C; this does not measure answer accuracy. Scripted graph/policy tests are not live answer-quality scores. See [evaluation methodology](evaluations/README.md).

## Documentation and publication scope

- [System architecture](docs/architecture/system_architecture.md)
- [Agent workflows](docs/architecture/agent_workflows.md)
- [RAG architecture](docs/architecture/rag_architecture.md)
- [Component reference](docs/architecture/component_reference.md)
- [Cleanup report](docs/github_cleanup_report.md)

The earlier PDF experiment and raw model/tool traces were backed up privately before removal. `backend/README.md` is a historical phase record; this root README is the current quickstart. Provider keys, manual text, raw traces and build/environment files are excluded from publication.

The studio background image was generated using ChatGPT's image-generation capability specifically for Creator Studio Copilot; it was not sourced from a third-party stock-image website. This is a public portfolio repository with no open-source license granted. Do not infer redistribution permissions for third-party references, samples or artwork from the code repository.
