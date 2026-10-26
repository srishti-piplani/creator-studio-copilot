> Historical phase-by-phase development record. For the current supported setup and commands, see [the project README](../README.md). Manual-processing and legacy upload commands below were archived in Phase 5B and are no longer public entry points.

# Creator Studio Copilot backend

FastAPI backend for Creator Studio Copilot with local preprocessing, original Studio knowledge RAG, and a conversational LangGraph assistant. See the phase-specific sections below for the current interfaces.

## Run locally

From the project root:

```sh
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

The existing uv environment and dependencies are already initialized.
Health check: `GET http://localhost:8000/health`

Expected response:

```json
{"status": "ok", "application": "Creator Studio Copilot"}
```

Interactive API docs: `http://localhost:8000/docs`.
CORS allows the local frontend origin `http://localhost:3000`.

## Structure

- `app/main.py`: FastAPI entry point and health endpoint.
- `app/config.py`: future environment-based configuration.
- `app/graph/`: bounded LangGraph workflow, structured routing, and session state.
- `app/rag/`: future ingestion, chunking, retrieval, and generation.
- `app/tools/`: bounded Keenable web search.
- `app/services/`: evidence evaluation and optional redacted tracing.
- `app/storage/`: local session coordination; notebook remains a placeholder.
- `tests/`: future backend tests.
- `src/backend/`: preserved uv starter package.
- `../data/`: source registry and golden evaluation questions, initially empty.
- `../evaluations/`: future evaluation scripts and results.

`.env.example` lists future configuration variables. Copy it to `.env` when
configuration is needed; no keys are required for the health endpoint.
Configuration loading and external service calls are not implemented yet.

## Phase 2A: local corpus preparation

Place permitted `.pdf`, `.md`, and UTF-8 `.txt` files in `data/corpus/`.
Files are discovered recursively. No URLs are fetched and no content is uploaded.
The default corpus is resolved relative to the project, independent of the working
directory. Override it with `CORPUS_DIR` or `--corpus-dir` (CLI takes precedence).

`data/sources.json` is a JSON array, currently empty. Add one entry per source,
with `path` relative to the corpus directory. Example format (illustrative only):

```json
[
  {
    "path": "logic-pro/permitted-excerpt.md",
    "product": "Logic Pro",
    "topic": "Audio recording",
    "source_url": "https://example.invalid/replace-with-official-source",
    "document_title": "Replace with actual document title",
    "software_version": "Replace with actual version if known"
  }
]
```

For hardware use `hardware_generation` when known; omit unknown version fields.
Only files listed in the manifest with an explicitly supported product load.
Unlisted files and products outside the MVP allowlist are skipped.
Manifest paths must be unique and stay within the corpus directory. A supplied
manifest must exist and contain valid JSON; loading/extraction errors are surfaced.

From `backend/`, load and chunk a real document after placing it at
`../data/corpus/logic-pro/permitted-excerpt.md` and adding its actual metadata:

```sh
uv run --no-sync --offline python -m app.rag.ingest --corpus-dir ../data/corpus --manifest ../data/sources.json
```

This processes all supported files in that corpus. To test only one document,
place it in its own corpus directory and pass that directory instead.

Run unit tests without installing additional packages:

```sh
uv run --no-sync --offline python -m unittest discover -s tests -v
```

### Cleaning, chunking, and identity

Cleaning normalizes whitespace and skips empty documents. PDF cleaning removes
standalone edge page numbers and identical edge headers/footers repeated on at
least three pages and at least half of all pages. This conservative heuristic
cannot identify every running header. Image-only PDFs need OCR, not included here.

Fixed chunking uses 500 approximate tokens with 75-token overlap. The local
estimate counts word pieces of up to four characters and individual punctuation;
it is not an inference provider's tokenizer. Original text offsets retain
formatting. Structure chunking recognizes Markdown headings and uppercase section
headings, keeps sections and numbered instructions together when they fit, then
uses paragraph boundaries and fixed windows for oversized content. Structural
chunks overlap only when fixed-window fallback is needed. PDF extraction does
not preserve semantic layout reliably, so structure preservation is best effort.

Document IDs hash corpus-relative paths: moving the corpus keeps IDs stable;
renaming a file changes its ID. Chunk IDs hash document ID, strategy, settings,
position, and chunk text. Unchanged reruns produce identical IDs; changed chunks
produce new IDs. A future indexing phase must handle deletion of obsolete chunks.
The current phase only returns in-memory documents/chunks and copied metadata.

### Corpus provenance review (2026-10-24)

The manifest catalogs the six PDFs currently present. Original source URLs were
recovered from each file's macOS download-origin attribute; titles and available
versions/generations were checked against local PDF content. SHA-256 fingerprints
identify the reviewed files. `retrieved_at: null` means the original download date
is unknown; `metadata_verified_at` is the review date, not a retrieval date. These
extra provenance fields remain in the manifest; the current loader copies only
its documented core metadata fields. AT2020/AT2035 have no asserted generation.
The iMovie directory currently contains no documentation file.

### Sunday MVP scope

`app/config.py` explicitly allows only Logic Pro, DaVinci Resolve, Focusrite
Scarlett Solo, Focusrite Scarlett 2i2, Audio-Technica AT2020, and Audio-Technica
AT2035. GarageBand and iMovie are out of scope: do not download or prepare their
documentation. Their existing empty folders remain; ingestion excludes them even
if files are added later. No active configuration existed before this scope lock.

Ingestion now requires manifest membership and an allowlisted product. The CLI
reports each supported product as available/unavailable based on nonempty loaded
documents, so a manifest entry alone never establishes coverage. Unit tests use
an explicit synthetic-product allowlist separate from MVP defaults.

The offline audit command, run from `backend/`, is:

```sh
uv run --no-sync --offline python -m scripts.audit_corpus
```

It writes metrics and local text inspection samples to `/tmp/creator-studio-corpus-*`;
these samples are not committed or uploaded. See the audit report in
`../evaluations/corpus_audit.md` for reviewed findings and indexing recommendations.

Verification on 2026-10-24: all six existing unit tests passed. Full local corpus
loading produced six documents, 8,510 fixed chunks, and 11,717 structure chunks.
GarageBand and iMovie are absent from these counts. pypdf reported optional
fontTools encoding warnings on some PDFs; extraction completed, but text quality
should be spot-checked before indexing. No additional packages were installed.


## Phase 2B: reproducible selected corpus

Use this command from `backend/` for the evaluation-ready preparation path:

```sh
uv run --no-sync --offline python -m app.rag.prepare
```

`data/selected_sections.json` records verified PDF bookmark/page boundaries,
printed-heading aliases, topic rationale and known coverage gaps. Source hashes
are checked against `data/sources.json`; changed PDFs require selection review.
Original PDFs are never rewritten. The older ingestion command remains available
for basic loading; use `prepare` for cleaned, selected, page-aware outputs.

The command writes `data/processed/sections.jsonl`, `exclusions.jsonl`, a resolved
`selection_manifest.json`, `procedure_examples.jsonl`, and separate `A/`, `B/`,
`C/chunks.jsonl` datasets. This whole processed directory is ignored by Git.
Reports are regenerated at `evaluations/phase2b_report.md` and `.json`.

A uses 300 estimated tokens / 45 overlap; B uses 500 / 75; C preserves structure
up to about 800 with source heading/context repeated for oversized procedures.
Whole words remain intact. The existing local token estimate is used because
installed tiktoken lacks cached vocabulary data and the pipeline must stay offline.
Word boundaries also correct the earlier fixed-window midword-splitting defect;
legacy chunk counts/IDs may therefore differ from the Phase 2A audit baseline.

Quarantines keep source/page IDs and reasons. They do not repair missing symbols.
Review the Phase 2B report before embedding: partial Resolve procedures, microphone
specification tables and missing compression documentation remain coverage limits.
No embeddings, Pinecone or other integrations are implemented.


### Approved controlled expansion

The selection manifest now includes the nine approved Logic Pro additions, three
Scarlett Solo 4th Gen additions, and safe passages from five priority Resolve
ranges. Logic boundary aliases were checked against printed headings. End pages
are trimmed at the named following headings, excluding unrelated sections.

New Resolve passages must match the page and exact-text fingerprint recorded in
`passage_review`; unknown or changed passages are quarantined. Reviews exclude
additional stray glyphs, broken procedures and ambiguous control labels that are
not caught by U+FFFD/C1 scanning. Each retained Resolve passage has its original
subheading and page in the cleaned record's `page_spans`.

The preparation report includes per-product section/record counts, passage-review
exclusions and quarantine pages. All three chunk configurations are checked
against exact source-body offsets for complete retained-text coverage. The prior
safe 2i2, AT2020 and AT2035 records remain unchanged; specification tables and
out-of-scope products are not added.

## Phase 2C: Pinecone integrated embeddings

The existing Pinecone Python SDK 7.3.0 uses the supported integrated-embedding
Records API (`create_index_for_model`, `upsert_records`, `search`). Current docs
also describe a newer Documents API; this implementation deliberately uses the
API supported by the installed SDK. No package upgrade is required.

Settings are read on demand from `backend/.env`, independent of the working
directory. Existing environment variables take precedence. Set
`PINECONE_API_KEY`; optionally set `PINECONE_INDEX_NAME`. An empty index name uses
`creator-studio-copilot`. Default deployment is AWS `us-east-1`; optional
`PINECONE_CLOUD`/`PINECONE_REGION` apply only when creating an index. The key is
excluded from configuration representations and is never printed. Do not enable
`PINECONE_DEBUG_CURL`, which would let the SDK expose authorization headers.

All strategies use `llama-text-embed-v2`, 1024 dimensions, cosine similarity,
with `embed.field_map={"text":"chunk_text"}`. Write input type is `passage` and
read input type is `query`; both set `truncate=NONE`. The live model catalog
reports a 2048-token maximum sequence length. Our local token estimate is not
that model's tokenizer: an oversized input fails instead of silently truncating.

The client lists indexes first. It creates only the configured name, with deletion
protection, or reuses an index after checking dense vector type, dimensions,
metric, model, field mapping, serverless deployment and inference parameters.
Incompatible indexes fail closed and are never reconfigured or deleted.

### Local validation and live synthetic test

Run from `backend/`:

```sh
uv run --no-sync --offline python -m app.rag.pinecone_cli validate
uv run --no-sync --offline python -m unittest discover -s tests -v
```

Validation reads the existing datasets and makes no API calls. The explicitly
invoked smoke test calls Pinecone, reads only the fixed five-record synthetic
fixture, and leaves its dedicated namespace in place:

```sh
uv run --no-sync --offline python -m app.rag.pinecone_cli integration-test
```

Here `--offline` prevents uv downloads; it does not block the application's
Pinecone requests. Results and measured latencies are saved without document text
or credentials at `evaluations/pinecone_integration.json`.

### Namespaces, records and retrieval

| Configuration | Namespace |
| --- | --- |
| A | `small-300` |
| B | `medium-500` |
| C | `structure-aware` |
| Synthetic smoke test | `integration-test` |

`pinecone_records.py` validates and projects chunk JSONL into flat text records.
It preserves source/document/chunk IDs, product, titles, original URL, section,
strategy/configuration, available versions/generation, original page range and
explicit page lists. Unknown values are omitted, with `version_known=false` when
appropriate; they are not invented. Numeric page lists are stored as string lists
for Records API metadata compatibility, then decoded on retrieval.

Deterministic record IDs hash source ID, configuration and the upstream chunk ID.
Replays overwrite the same IDs. They do not remove obsolete records when a future
corpus revision changes chunk IDs; index reconciliation is a separate step.

Text upserts use sequential batches of 32 (never more than 96), with a conservative
1.9 MB payload budget and 40 KiB record-field validation including text. Nested
metadata is not sent. All application-selected citation metadata is filterable;
`product={"$eq":...}` is sent within `query.filter`, scoped to one namespace.
Filtering is a retrieval constraint, not an authorization boundary.

`retrieve.search()` accepts natural-language text and returns passages, similarity
scores and citation-ready metadata. Query CLI output intentionally omits passage
text. For example, after approved indexing:

```sh
uv run --no-sync --offline python -m app.rag.pinecone_cli query --strategy B --text "How do I record a microphone?" --product "Logic Pro"
```

Application retries are bounded to three attempts for 429, 5xx and network errors,
with exponential backoff. Permanent errors fail immediately; request/response
bodies are suppressed. Creation/readiness and consistency polling are bounded.
The SDK also has its own HTTP transport retry behavior. Completed batches can
remain after a later batch fails; replay is safe because IDs are stable.

### Real-corpus indexing — requires separate explicit approval

No real documentation has been uploaded during Phase 2C. After explicit approval,
the exact command from `backend/` is:

```sh
uv run --no-sync --offline python -m app.rag.pinecone_cli index --strategy all --approve-real-corpus
```

This validates all three datasets before connecting, then sends 375, 232 and 168
records into their separate namespaces. It does not touch `integration-test` or
unrelated indexes. Without the approval flag, the upload command exits before
connecting. The flag is a deliberate user action, not automatic approval of uploads.

Official references checked for this phase:

- https://docs.pinecone.io/guides/index-data/create-an-index
- https://docs.pinecone.io/models/llama-text-embed-v2
- https://docs.pinecone.io/guides/index-data/upsert-data
- https://docs.pinecone.io/guides/search/semantic-search
- https://docs.pinecone.io/guides/search/filter-by-metadata
- https://docs.pinecone.io/guides/index-data/data-modeling

## Original Studio Knowledge Base and working RAG

`data/studio_knowledge/` contains 12 original AI-assisted educational guides, a
reference/review manifest and a human-readable source catalogue. They explain
fundamentals for the six supported products, not exact product specifications or
version-specific commands. References were checked through official pages or
indexed excerpts; this is explicitly not independent human verification.

The original PDF corpus and `data/processed/` remain unchanged. The Studio builder
reuses the existing loader and chunker with a separate product/corpus marker and
writes only `data/studio_processed/`. Markdown provenance uses logical page 1
plus source-line references; these are not fabricated PDF page numbers. Each chunk
carries a local guide path and checked reference URLs. A local 12-word exact-copy
check against manual-derived text is a limited originality check, not a complete
plagiarism detector.

From `backend/`:

```sh
uv run --no-sync --offline python -m app.rag.studio_cli prepare
uv run --no-sync --offline python -m app.rag.studio_cli index
uv run --no-sync --offline python -m app.rag.studio_cli evaluate
uv run --no-sync --offline python -m app.rag.studio_cli examples
uv run --no-sync --offline python -m app.rag.studio_cli ask --strategy B --question "How does EQ differ from compression?"
```

The index command is explicitly authorized for original Studio guides only. It
revalidates guide hashes/references, rebuilds all three authored-guide datasets,
and sends them only to `studio-small-300`, `studio-medium-500`, and
`studio-structure-aware`. Records lacking the Studio corpus marker are rejected
in those namespaces. No manual path option exists in this command. `--offline`
prevents uv package downloads; index/evaluate/examples/ask still call providers.
Do not use the older manual indexing command for this project phase.

`generate.py` uses the configured Nebius key. The default endpoint is the official
`https://api.tokenfactory.nebius.com/v1`; the default model
`Qwen/Qwen3-30B-A3B-Instruct-2507` was verified in authenticated discovery. Optional
`NEBIUS_MODEL` and `NEBIUS_BASE_URL` settings override it; model availability is
checked before generation. Fireworks has no configured key and is not used.
Provider/network failures are bounded and sanitized. Credentials are not included
in prompts or configuration representations. No new dependency was needed.

Start the existing server and send a question:

```sh
uv run uvicorn app.main:app --reload --port 8000
curl -X POST http://localhost:8000/ask -H 'Content-Type: application/json' -d '{"question":"What is direct monitoring?","strategy":"B","top_k":5}'
```

`POST /ask` retrieves from Studio namespaces only. Responses include `answer`,
`answerable`, trusted guide paths/reference URLs and timings. Retrieval evidence
must match the local approved guide revision before being sent to Nebius. Unknown
citation IDs/URLs, malformed answers, or missing citations for answerable responses
are rejected. When evidence is missing the service returns an explicit abstention.
Model-reported insufficiency is not a mathematically calibrated confidence score.

The 20-question golden set in `data/golden_questions.json` was written before
live model answers. Retrieval reports use macro source-level Recall@5: the
fraction of expected GUIDE IDs found in the top five CHUNKS, averaged over the
16 answerable questions. Four unsupported questions are recorded but excluded
from recall; retrieval alone cannot determine answerability. This small authored
set and sequential timing pass are not an unbiased benchmark or proof of a
winning strategy.

Live results are in `evaluations/studio_indexing.json`, `studio_retrieval.json`,
`studio_rag_examples.json`, and `studio_answer_review.json`. Citation checks do not
prove claim-level factuality. The answer review flags residual overgeneralizations
in the generated examples; this is a working RAG prototype requiring answer-quality
evaluation, not independently verified educational advice.

## Phase 3: conversational Studio agent

`POST /ask` is preserved. `POST /chat` adds a single-assistant LangGraph workflow:
route → existing Studio RAG → evidence assessment → optional Keenable search →
assessment → response. Discover goes directly to web search; ambiguous requests
ask for clarification. There is at most one search node per turn (five results),
two HTTP attempts per search, and two schema attempts per structured model call. Agent calls use Nebius native
`json_schema` output; `/ask` retains its existing JSON-object contract.
Existing Nebius transport retries remain bounded at three attempts. A complete
turn can involve several model calls and take considerably longer than `/ask`.

From `backend/`, start the server as before, then:

```sh
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"My microphone recording is silent. Help me diagnose it.","equipment":["Logic Pro","Focusrite Scarlett Solo","Audio-Technica AT2020"]}'
```

Copy the returned `session_id` into subsequent requests:

```sh
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"That did not work.","session_id":"REPLACE_WITH_RETURNED_UUID"}'
curl http://localhost:8000/sessions/REPLACE_WITH_RETURNED_UUID
```

Responses contain `answer`, `intent`, `session_id`, `citations`,
`diagnostic_question`, `resource_cards`, `troubleshooting_status`, `limitations`,
and `evidence_evaluation`. Session inspection includes messages, equipment,
version, current goal, asked questions, attempted steps with user-reported
outcomes, evidence, and web-search history. Unknown UUIDs return 404; invalid
requests return 400 (or FastAPI validation 422). Provider/schema failures return
a sanitized 503. Session IDs are opaque identifiers for this local MVP, not an
authentication system.

The LangGraph `InMemorySaver` stores sessions only in this process. **All sessions
are lost on backend restart or reload. Run one worker for the local MVP.**
Questions/steps are retained across turns. Troubleshooting renders only the
tracked question or action, preventing untracked extra fixes in generated prose. Explicit failed-fix reports trigger
web fallback; action keys and text similarity block repeated attempted fixes,
including a conservatively detected paraphrase. Semantic equivalence is still
model-dependent, so this is not a guarantee against every possible rewording.
The graph stops on unresolved contradictions, insufficient evidence, repeated
questions/actions, or explicit user-reported resolution.

Conceptual grounding calls the existing `StudioRAG.answer` in the medium Studio
namespace; it does not index, read, or upload manufacturer manuals. Citation
`K1` wraps that RAG synthesis and its checked underlying guide references.
`W1`–`W5` cite the actual returned web pages. Only known citation IDs are accepted;
URLs in generated prose are rejected. Official-domain filters are used for
instructions (Apple, Blackmagic Design, Focusrite, Audio-Technica); community
resources in Discover are labeled. Web excerpts are untrusted source data.
Product/version relevance and contradictions are assessed by the configured
Nebius model, not independently verified by a human. An official domain alone
does not prove an excerpt applies to the user's version.

Keenable uses the documented REST API `POST https://api.keenable.ai/v1/search`,
`X-API-Key`, `max_results=5`, and bounded snippets and timeouts. No SDK was added.
API reference: https://docs.keenable.ai/api-reference/search . Search excerpts
alone do not verify a resource's licensing terms; cards explicitly report
`License not verified.` Publication dates are exposed when returned, not invented.

Langfuse tracing is optional. With both `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` configured (and optional `LANGFUSE_BASE_URL`), the graph
receives a Langfuse callback. Inputs/outputs are redacted, retaining graph
execution tracing without logging user/source text. Without these keys no
Langfuse client is initialized. Tracing is currently unconfigured and has not
been live-tested.

Offline verification and opt-in live checks:

```sh
uv run --no-sync --offline python -m unittest discover -s tests -q
uv run --no-sync --offline python scripts/evaluate_agent.py
# Calls the three providers using configured keys; performs no indexing:
uv run --no-sync --offline python scripts/agent_live_check.py
```

The deterministic evaluation runs ten scenarios through the real compiled graph
with scripted providers; it tests control flow, not live LLM accuracy. Reports:
`../evaluations/agent_scenarios.json` and `../evaluations/agent_live_results.json`.

## Phase 4 frontend

The local Next.js workspace is in `../frontend/`. Run `npm run dev` there and open
`http://localhost:3000` while this backend runs on port 8000. See
`../frontend/README.md` for setup, persistence, API contracts, and verification.
The frontend sends saved hardware context through the existing `equipment` field;
no additional API fields or provider credentials are exposed. Routing now uses
the model's current equipment list rather than accumulating conflicting old
products, with explicit user mentions taking precedence over saved defaults.

Diagnostic compatibility: when the model returns both a question and a fix, the
backend asks the question first and discards the unasked fix. A pure diagnostic
question may omit citations; factual advice still requires valid source IDs.

## Phase 4B: answer quality and research metadata

The agent reuses a factored `StudioRAG.retrieve` method, which validates the same
approved guide hashes and uses the same Pinecone retrieval as `/ask`. It passes
source passages directly to the agent, eliminating a generated intermediate
summary. `/ask` still uses the shared retriever and its existing response contract.
No source guide, PDF, chunk dataset, embedding or index was changed.

Learn uses structured fields for a takeaway, short key points, an optional
example, and complete procedures with observable success checks. How-to replies
without supported complete steps disclose that limitation rather than filling
gaps. Official indexed HTML documentation can be read through Keenable's verified
`GET /v1/fetch` API: at most two pages, 12,000 characters each, no live crawl,
PDF fetching, extraction LLM, local corpus writes, or indexing. Search results and
page text remain untrusted data. Installed software versions are never inferred
from the supported documentation versions. A generic how-to can be scoped to
its cited documentation rather than demanding an unnecessary installed version.

Troubleshooting preserves the complete next action plus a short rationale. The
old regex that could cut an instruction off at a menu path was removed. A
structured evidence review allows at most one repair and one recheck. Explicit
factual-trap checks supplement that fallible model review. Flagged conceptual
Learn blocks may be omitted without rewriting them; procedures are never trimmed
by that helper. An unsupported complete draft is withheld. These checks improve
presentation and guard known mistakes; they do not certify factual correctness.

Responses also carry factual `activities`, a `topic_title`, and `new_topic`.
Activity records originate in executed nodes: Studio search, Keenable search,
indexed documentation reads, community excerpts, clarification, and draft checks.
Failed operations are marked failed, and each turn starts a fresh activity list.
No private model reasoning is displayed. Resource search no longer appends
unrelated saved microphones/interfaces to general Discover queries.

For isolated local frontend QA, set `FRONTEND_ORIGIN=http://localhost:3001` in the
process environment and run this backend on port 8001. Normal operation continues
to allow `http://localhost:3000` with no configuration change.
