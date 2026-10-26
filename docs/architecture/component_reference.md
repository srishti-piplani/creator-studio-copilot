# Active component reference

Paths are relative to the project root. Reviewed 2026-10-25. “Runtime” means reachable from the current UI/API entry points, not merely installed or imported by a historical script.

## Frontend

| Module / main exports | Purpose and inputs → outputs | Dependencies / invoked by |
|---|---|---|
| `frontend/app/layout.tsx` — `RootLayout` | Route children → shared styles, provider, shell | Next.js App Router; mounts every route |
| `frontend/components/shell.tsx` — `Shell` | Provider history/navigation → sidebar, logo/home, Recent Conversations | Shared layout; browser state, Next navigation |
| `frontend/app/page.tsx` — Assistant | Composer text/setup/thread → requests, messages, progress, per-answer topic association | `chat-stream`, `api`, provider, `Answer`; `/` |
| `frontend/components/studio-provider.tsx` — `StudioProvider`, `useStudio` | Browser storage → setup, active thread/history, Notebook CRUD and manual title editing | Shared context; storage helpers; serializes localStorage |
| `frontend/lib/storage.ts` — `setupEquipment`, `topicTitle`, `notebookTitle`, `boundHistory`, `safeUrl` | Explicit setup/messages/saved-answer IDs → safe request context, bounded history, stable display titles/URLs | Provider, Assistant, answer cards, tests; no LLM |
| `frontend/lib/api.ts` — `sendChat`, `getSession`, `parseChatResponse`, `ApiError` | JSON HTTP requests → validated minimal response shape or recoverable error | Streaming fallback and diagnostic history refresh; default backend port 8000 |
| `frontend/lib/chat-stream.ts` — `sendChatWithProgress` | Chat request/callbacks → actual progress and one final `ChatResponse` | Fetch POST SSE; same request UUID for fallback to `sendChat` |
| `frontend/lib/activity.ts` — activity grouping | Operation events → grouped progress display | `components/live-activity.tsx`; grouping is presentation, not fabricated tool work |
| `frontend/components/answer.tsx` — `Answer`, `WebLink` | Structured answer + originating question/topic → Markdown, citations, cards, save action | ReactMarkdown, provider, resources/storage; Notebook reuses saved view |
| `frontend/lib/resources.ts` — `resourceLicenseLabel` | Resource usage/provenance → licensing label or no viewing-only label | Answer cards; does not independently verify remote terms |
| `frontend/app/notebook/page.tsx` | Saved entries/search/selection → Notebook reader and title editing | Provider and `Answer`; no backend Notebook API |
| `frontend/app/setup/page.tsx` | Equipment selections → saved optional microphone/interface | Provider; software documentation references remain distinguishable from installed versions |
| `frontend/components/landing-setup.tsx`, `studio-art.tsx`, `studio-icons.tsx`, `ui/button.tsx` | Setup/art/action props → presentation | Assistant/setup/shell; retained active UI assets |
| `frontend/lib/types.ts` | Shared TypeScript contracts, including message `topicTitle` | Compile-time clients/components; API runtime checking is intentionally narrower |
| `frontend/app/globals.css`, `premium.css` | Existing responsive/cinematic styling | Layout imports both; overlapping generations of styling warrant care before any cleanup |

The selected answer's stored `Message.topicTitle` is authoritative for new saves; fallback inference supports older threads. Saved `title` values are retained, including manual edits. Thread titles and individual answer-topic titles intentionally have different lifetimes: a conversation can contain multiple topics.

## API, graph and services

| Module / main functions or classes | Inputs → outputs / responsibility | Dependencies / caller |
|---|---|---|
| `backend/app/main.py` — `health`, `ask`, `chat`, `chat_stream`, `session` | Validated HTTP bodies/UUIDs → structured JSON/SSE | Lazy RAG/agent services, ChatJobs, FastAPI; `uvicorn app.main:app` |
| `backend/app/config.py` — `ChatSettings`, `PineconeSettings`, product constants | Backend dotenv + process environment → immutable settings | Chat/store/tool factories; secrets excluded from settings repr |
| `backend/app/graph/workflow.py` — `StudioAgent`, `get_agent_service` | User turn + checkpoint/setup → graph response and updated thread | Six graph nodes; models/tools/helpers/sessions; main API |
| `backend/app/graph/state.py` — `Route`, `AgentState` | Structured routing output and JSON-serializable thread data | Router/Pydantic and LangGraph; state is not a database schema |
| `backend/app/graph/router.py` — `route`, `structured` | Prompt, recent messages, context, schema → validated model decision | `AgentChat`; route, evaluator, generation/review helpers; up to two schema attempts |
| `backend/app/graph/model.py` — `AgentChat` | Prompt + Pydantic schema → Nebius structured object | Reuses `NebiusChat` transport/model; runtime agent factory |
| `backend/app/graph/context.py` — `studio_context`, `merge_equipment`, guards | Saved setup, explicit text, state → applicable primary software/equipment and context checks | Router, evaluator, workflow; deterministic overrides |
| `backend/app/graph/procedures.py` — `SourceSpan`, `HowToAnswer`, `generate_procedure` | Task/product/version/evidence → validated essential procedure or insufficiency | Structured extraction, literal provenance checks, completeness review; `_respond_procedure` |
| `backend/app/graph/provenance.py` — `provenance`, `valid_span`, claim checks | Source URLs/types and spans → evidence classification/applicability/validity | Tools + ordinary Python; procedure, creative and response guards |
| `backend/app/graph/creative.py` — `generate_advice` | Goal + passages → retained grounded qualitative suggestions/citations/checks | Structured model + span/claim checks; `_respond_creative` |
| `backend/app/graph/answers.py` — `LearnAnswer`, `DiscoverAnswer`, review/render helpers | Draft data/evidence → structured conceptual/resource answers and checked Markdown | Generic response path; some older procedural helpers remain alongside dedicated procedures |
| `backend/app/graph/monitoring.py` — `switch_reply`, `monitoring_outcome`, `beginner_check`, `isolation_test` | Prior diagnostic question, user reply, selected generation, official evidence, steps → scoped readiness/outcome/control observation | Workflow route/respond and web section selection; no device control |
| `backend/app/services/evidence_evaluator.py` — `Evaluation`, `evaluate` | Current goal/setup, last 12 messages, steps/evidence → sufficient/relevant/conflict/research/clarification verdict | Same Nebius model + deterministic corrections; assess/reassess |
| `backend/app/tools/web_search.py` — `KeenableSearch`, URL/domain helpers | Search query or approved URL → max-five results / max-12k-character indexed page or categorized safe error | httpx; web node. Official and resource fetch policies differ |
| `backend/app/services/resource_license.py` — `license_evidence` | Resource page text/URL → narrowly verified CC terms or no verification | Regex plus restriction exclusions; web node, not a legal guarantee |
| `backend/app/graph/progress.py` — `operation`, `tracked`, `progress_sink` | Actual operation invocation → started/completed/failed signals | ContextVar callback, job stream; source/reasoning contents omitted |
| `backend/app/services/chat_jobs.py` — `ChatJobs`, `ChatJob` | Request UUID + signature + callable → shared future, replayed SSE activity/final/error | Thread pool + condition; main API; bounded process-local cache |
| `backend/app/storage/sessions.py` — `Sessions` | Optional UUID → thread config and per-thread RLock | Agent; checkpoint data resides in LangGraph InMemorySaver |
| `backend/app/services/tracing.py` — `tracing_callbacks` | Optional Langfuse settings → redacted callbacks or empty list | Cached agent factory; optional, currently unconfigured locally |

## RAG and preparation

| Module / entry points | Inputs → outputs / responsibility | Invocation |
|---|---|---|
| `backend/app/rag/generate.py` — `NebiusChat`, `StudioRAG`, `get_rag_service` | Approved Pinecone passages → grounded standalone `/ask`; `retrieve` returns raw passages for agent | Main API/agent; `retrieve`, guide manifest, store/settings |
| `backend/app/rag/retrieve.py` — `search`, `parse_results` | Query, namespace, optional filter → validated text hits/citation metadata | StudioRAG, evaluation and administrative CLIs |
| `backend/app/rag/pinecone_store.py` — `PineconeStore`, `check_compatible`, `with_retry` | Settings/records/query closures → compatible connection, bounded operations/upserts | Runtime connection/search plus explicit indexing; runtime uses `create=False` |
| `backend/app/rag/pinecone_records.py` — `to_record`, `load_records`, `record_id` | Chunk JSONL/config → flat validated records and stable IDs | Offline indexing/tests; constants imported at runtime |
| `backend/app/rag/studio.py` — `validate_guides`, `prepare_studio` | Original Markdown/manifest → approved guide metadata or original processed sections/chunks | Validation is runtime; preparation is an explicit original-guide-only offline CLI |
| `backend/app/rag/studio_cli.py` — `index_studio`, `retrieval_evaluation`, `run_examples` | Explicit command → preparation/indexing/evaluation report or answer | Administrative/evaluation CLI; never called by `/chat` |
| `backend/app/rag/ingest.py` — `Document`, cleaning, `load_documents` | Local files/manifest/allowlist → cleaned documents and coverage | Original-guide preparation, historical pipeline, unit tests; no normal request ingestion |
| `backend/app/rag/chunking.py` — `chunk_sections`, `chunk_documents` | Documents/sections + strategy → deterministic chunks | Studio build and old manual pipeline; simple document chunking also supports ingestion CLI/tests |
| `backend/app/rag/preprocessing.py` — stable IDs, edge/section cleaning | Text/page boundaries → normalized sections/quality information | Manual preparation; `stable_id` also used by active Studio chunk builder |
| `backend/app/rag/prepare.py` — `verify_source_coverage`, `write_jsonl` | Sections/chunks → checked body coverage and deterministic JSONL | Shared by Studio preparation/tests; manual command archived in Phase 5B |
| `backend/app/rag/pinecone_cli.py` — `integration_test`, `main` | Explicit administrative command → synthetic smoke results | Not runtime; only `integration-test` is supported, manual upload CLI archived |

## Evaluation and dependency relationships

`backend/scripts/golden_sets.py` validates RAG/agent datasets. `evaluate_agent.py` executes ten scripted graph scenarios; `evaluate_agent_golden.py` executes linked tests for 12 rubrics. Tests/fixtures are genuine reproducibility assets even without runtime imports. `evaluations/*live_check.py`, probes and benchmark scripts are opt-in paid-service experiments; do not run them as ordinary offline tests.

Installed LangChain integrations and `rank-bm25` are not evidence of an active LangChain retrieval chain or BM25 search. Actual runtime orchestration uses LangGraph, direct httpx chat/search adapters and the Pinecone SDK. Dependency removal would require a separate import/test review and lockfile update; none is proposed as a cosmetic submission change.

## Complexity worth documenting, not refactoring during submission

- `workflow.py` combines orchestration with answer policy, formatting, retry/repair and device-specific exceptions. Multiple checks can transform the same answer; diagnosis must inspect actual path and checks rather than prompts alone.
- General evidence assessment, draft review, procedural review and creative review overlap but cover different contracts. Their use of the same model limits independence.
- `answers.py` retains procedural fields/helpers while early Learn-how-to dispatch now goes through `procedures.py`. Some later Learn/how-to branches look unreachable under that early dispatch. This is a **candidate for a targeted reachability review**, not permission to delete the entire helper module: conceptual/discovery helpers are active and tests still exercise compatibility paths.
- Studio code imports shared utilities from modules named for the old manual pipeline. Whole-file deletion of `prepare.py`, `preprocessing.py`, `ingest.py` or `chunking.py` would break original-guide reproducibility/imports.
- Browser history and backend sessions are separate authorities: durable display versus ephemeral diagnosis. They are not duplicate durable databases.
- `storage/notebook.py` and `src/backend/__init__.py` are starter remnants; the Notebook is frontend-owned and the packaging entrypoint prints a greeting rather than starting FastAPI.
