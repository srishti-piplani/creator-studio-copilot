# Component reference

Paths are relative to the repository root. The frontend owns presentation and browser persistence; FastAPI owns API boundaries; LangGraph owns turn orchestration. Build/evaluation commands are separate from runtime requests.

## Frontend

| Module | Responsibility and integration |
|---|---|
| `frontend/app/layout.tsx`, `components/shell.tsx` | Mount shared styling/provider, navigation, logo/home and recent threads |
| `frontend/app/page.tsx` | Composer, request lifecycle, progress, messages and per-answer topic association |
| `frontend/components/studio-provider.tsx` | Browser setup/history/Notebook persistence, thread switching and title editing |
| `frontend/lib/storage.ts` | Explicit equipment overrides, topic inheritance, selected-answer title resolution, bounded history and safe URLs |
| `frontend/lib/api.ts` | Typed JSON client, minimal response validation, errors and session refresh |
| `frontend/lib/chat-stream.ts`, `lib/activity.ts` | POST SSE parsing, same-ID fallback and honest activity grouping |
| `frontend/components/answer.tsx`, `lib/resources.ts` | Markdown, citations, resource cards, appropriate rights labels and Save Answer |
| `frontend/app/notebook/page.tsx`, `app/setup/page.tsx` | Individual saved-answer reader and selected studio equipment |
| `frontend/lib/types.ts` | Shared compile-time request/response, conversation, topic and saved-answer contracts |
| `frontend/components/landing-setup.tsx`, `studio-art.tsx`, `studio-icons.tsx`, `ui/button.tsx` | Setup rack, visual assets/icons and reusable controls |
| `frontend/app/globals.css`, `premium.css` | Current responsive cinematic styling; both are imported by layout |

Stored answer topics survive reopening/pruned history; existing saved/manual titles remain authoritative. Conversation titles and individual topic titles have different lifetimes. `next-env.d.ts` is generated locally and ignored.

## Backend and orchestration

| Module / main entry | Inputs → outputs; integration |
|---|---|
| `backend/app/main.py` | Validated HTTP input → health, grounded Q&A, agent JSON/SSE and session state |
| `app/config.py` | Backend dotenv/process values → model/index settings and product scope |
| `app/graph/workflow.py` — `StudioAgent` | Turn + setup/checkpoint → six-node graph response and updated thread |
| `app/graph/state.py`, `router.py` | Structured route + recent context → intent, goal, equipment, outcome; typed checkpoint state |
| `app/graph/model.py` — `AgentChat` | Prompt/schema → Nebius JSON Schema result using the shared transport |
| `app/graph/context.py` | Explicit statements/saved defaults → applicable setup and redundant-question/context guards |
| `app/graph/procedures.py` | Task/evidence → nonempty exact-span procedure or insufficiency, with completeness review |
| `app/graph/creative.py` | Goal/passages → individually supported qualitative suggestions and citations |
| `app/graph/answers.py` | Concept/resource contracts, reviews, formatting and output checks |
| `app/graph/provenance.py` | URLs/types/spans → provenance, literal support and product/version applicability |
| `app/graph/monitoring.py` | Pending question, answer, generation-specific evidence and steps → observable check/action readiness/outcome |
| `app/services/evidence_evaluator.py` | Goal/setup/context/evidence → sufficiency, research, relevance, conflict and clarification verdict |
| `app/tools/web_search.py` — `KeenableSearch` | Query/approved URL → bounded results/indexed HTML or categorized error |
| `app/services/resource_license.py` | Resource page text → narrowly verified scoped CC terms or no verification |
| `app/graph/progress.py`, `services/chat_jobs.py` | Real operations/request UUID → public activity, shared future and SSE final/error |
| `app/storage/sessions.py` | UUID → per-thread lock/checkpoint configuration; data stays in LangGraph memory |
| `app/services/tracing.py` | Optional credentials → redacted callbacks or no tracing |

The Notebook placeholder under `app/storage/` is not a backend persistence implementation. The uv starter package under `backend/src/backend/` remains a packaging dependency; its console greeting is not the FastAPI entrypoint.

## Knowledge and evaluation

| Module | Responsibility |
|---|---|
| `backend/app/rag/generate.py` — `NebiusChat`, `StudioRAG` | Shared inference transport; approved raw retrieval for the agent and standalone grounded `/ask` |
| `app/rag/retrieve.py` | Integrated text search, optional filters and validated citation metadata |
| `app/rag/pinecone_store.py` | Compatible index connection, bounded retries and explicit record writes |
| `app/rag/pinecone_records.py` | Flat metadata validation, namespace constants and deterministic IDs |
| `app/rag/studio.py` | Original guide manifest/hash checks and manual-independent preparation |
| `app/rag/ingest.py`, `chunking.py`, `preprocessing.py`, `prepare.py` | Generic document model/loading, deterministic chunks/IDs and shared JSONL/source-coverage helpers |
| `app/rag/studio_cli.py`, `pinecone_cli.py` | Explicit preparation/index/evaluation and synthetic-only cloud smoke commands |
| `backend/scripts/golden_sets.py`, `evaluate_agent.py`, `evaluate_agent_golden.py` | Dataset validation, ten scripted graph scenarios and linked checks for 12 agent rubrics |
| `backend/scripts/check_public_repository.py` | Read-only public-file, secret-pattern, path and guide-hash checks |

Tests and labeled synthetic fixtures are reproducibility assets, even without runtime imports. Opt-in live/browser QA scripts can incur provider usage; they are not part of ordinary offline tests. Installed LangChain integrations and `rank-bm25` do not imply an active retrieval chain or BM25 path.

## Important integration limits

`workflow.py` contains orchestration plus response policy, monitoring exceptions and rendering. General assessment, conceptual review, procedural completeness review and creative review cover different contracts but use the same model. Some older procedural compatibility helpers remain alongside dedicated early procedure dispatch; do not infer that the whole answer module is unused. Browser history and backend sessions are different authorities, not duplicate durable databases. Source/domain/span checks constrain errors without proving universal factual accuracy.
