# Phase 5B — GitHub repository cleanup

Completed 2026-10-25. No commits, pushes, paid LLM/web/retrieval calls, dependency installation, Pinecone writes or model/runtime behavior changes were performed. Offline preparation was regenerated and verified; the production index was not contacted.

## Repository status and backup

The intended project directory `creator-studio-copilot/` is now the single Git root, on unborn branch `main`, with no remote, commits, staged files or tracked files. Public source files are intentionally **untracked pending owner review**, not silently committed/staged.

Before moving metadata, checks confirmed the nested `backend/` repository had no commits, branch refs, remotes, tracked changes or reflog entries. Its local configuration contained only standard core repository settings, not a remote or special worktree. The 18 metadata files were hashed, moved intact and verified. No application working directory or environment was moved.

Durable local backup, outside the public root:

```text
../creator-studio-copilot-local-archive-20261025/
├── SHA256.json
├── nested-backend.git/
└── project_snapshot/
```

The snapshot contains **223 files**, including all legacy files, prior source/docs and evaluation artifacts before cleanup. Dependency/build/cache directories were omitted. Secret `.env` files were deliberately not duplicated; the original `backend/.env` remains in place and ignored. Backup directory permissions are owner-only. This backup was not deleted. Every retired file was checked against both its snapshot bytes and SHA-256 manifest before removal; all 73 archived originals were verified again afterward.

## Retained public components

- FastAPI, six-node LangGraph, Nebius transport/model configuration, Pinecone integrated embedding/retrieval, Keenable research, source validation, diagnostic state and streaming.
- All frontend routes/components, Notebook/topic inheritance, Studio Setup, cinematic styling and runtime background asset. Background usage rights remain an owner verification item below.
- Twelve unchanged original Studio Knowledge guides, manifest/hashes, attribution/reference metadata and source registry.
- Generic loading/cleaning, deterministic chunking, synthetic preprocessing tests and shared stable-ID/coverage helpers. These remain because Studio preparation or relevant tests use them; they are not dead merely because some originated in the PDF experiment.
- Original-guide CLI, synthetic-only Pinecone integration command, all current backend/frontend tests and labeled fixtures, RAG/agent golden datasets and offline scenario runners.
- Python/Node package manifests and lockfiles, `.python-version`, configuration and blank-secret environment templates.
- Reviewed architecture documents, current evaluation JSON summaries, Phase 5A report/baseline, compact verified-source inventory, new evaluation methodology/history summaries and root quickstart.

`backend/src/backend/` remains because uv packaging and the starter console command reference it. The root README identifies the actual Uvicorn entrypoint; removing starter packaging was outside this controlled cleanup.

## Archived and removed from the public tree

**73 original paths** were retired after backup verification. Exact paths are listed in [`evaluations/cleanup_archive_inventory.json`](../evaluations/cleanup_archive_inventory.json). Groups:

- All six downloaded manufacturer PDFs, preserving corpus directories and `.gitkeep` files.
- All manual-derived `data/processed` sections/chunks, extraction exclusions and procedure examples.
- Manual source/selection manifests `data/sources.json` and `data/selected_sections.json`; manual-only `backend/scripts/audit_corpus.py`.
- Raw tool/model traces, full prompt/benchmark/source dumps, old browser/session captures, obsolete live probes and intermediate evaluation reports. Selected historical findings are summarized without raw excerpts.
- Design reference images, including the duplicated background reference copy. The separate runtime background remains unchanged.

The old `rag/prepare.py` manual-selection implementation and manual dataset `pinecone_cli` commands are preserved in the pre-cleanup snapshot. Public `prepare.py` now contains only the exact shared JSONL/source-coverage helpers. Public `pinecone_cli` only accepts `integration-test`, which writes five labeled synthetic records when explicitly run; no manual upload command remains. This cloud-writing smoke command was **not run during cleanup**.

The historical `evaluations/studio_preparation.json` was archived, then replaced with a clearly current original-only build report at the same public path. Its old comparison claim was not retained as a new claim. Historical retrieval results were not regenerated or edited.

## Original-only reproducibility

`prepare_studio()` no longer reads PDFs, private manual chunks or manual extraction artifacts. Removed the manual-shingle comparison; the report explicitly says no comprehensive plagiarism audit or manual comparison is performed. Guide hash/reference/structure checks remain intact.

Added `backend/tests/test_studio_reproducibility.py`. It builds twice inside a temporary tree containing only copied original guides/manifest, with **no `data/corpus` or `data/processed` directories**. It verifies 12 retained sections, unchanged guide bytes, full source coverage, deterministic JSONL and A/B/C **36/24/12**. When existing generated data is available, it also verifies byte-for-byte equality.

The actual local original-only preparation also succeeded: **12 guides, 4,640 words, 36/24/12 chunks**. Generated A/B/C files are byte-identical to the backed-up pre-cleanup Studio outputs. All 12 source-guide hashes still match their original manifest. No index regeneration occurred.

From backend:

```sh
uv run --offline python -m app.rag.studio_cli prepare
uv run --offline python -m unittest discover -s tests -p test_studio_reproducibility.py
```

Dependency restoration and explicit compatible-index bootstrap are documented in the root README, separate from paid/indexing commands. Standalone startup and full local chat still require configured cloud services and an existing compatible populated index; offline preparation is not an offline chat model.

## Evaluation sanitization and retained claims

- `studio_retrieval.json` is unchanged from the backed-up historical Phase 5A report: positive guide recall@5 **1.000 for A/B/C**. It was not remeasured during cleanup. Baseline data and the scope/comparability explanation are retained.
- `data/golden_questions.json` is unchanged: 20 RAG-only questions, 16 supported/four corpus-negative; benchmark labels do not control the live agent.
- The 12 agent scenarios retain their questions/criteria/URLs. Two raw-evidence artifact pointers now resolve to `verified_source_inventory.json`, containing URLs, historical filenames and scope notes, **not reconstructed excerpts or a claim of fresh verification**.
- Scripted graph/policy reports were rerun offline. They do not become live answer-quality evidence.
- Sanitized `evaluations/historical_results.md` preserves old chunking/benchmark methodology, selected actual recorded metrics and limits. Raw artifacts stay private; the fixed-evidence model benchmark is not fully reproducible from a URL inventory alone. No historical answer was rewritten to make it appear to pass later fixes.

## Ignore rules and security findings

Root `.gitignore` retains lockfiles, original guides, templates and corpus placeholders, while excluding secrets/keys, environments, dependencies, build caches, manuals/PDFs, extracted/generated datasets, logs, temporary files and local backup directories. Evaluation publication is an **explicit allowlist**: arbitrary raw traces and new dumps are ignored by default. The retained nested `backend/.gitignore` is a regular rules file, not a second repository.

Verified with Git that `.env`, `.venv`, `node_modules`, `.next`, raw-trace/log/key examples and downloaded PDF paths are ignored; templates, `uv.lock`, package lockfile and original guides remain eligible. No nested Git metadata remains in the public tree. Because no files are staged/tracked yet, no ignored sensitive file is secretly present in the index.

Added `backend/scripts/check_public_repository.py`, a read-only scan over Git-eligible files including untracked files. It checks exact currently configured secrets without printing them, common credential/private-key markers, actual user absolute paths, files over 10 MiB, PDFs/manual datasets and guide hashes. No findings were detected in the final public scan; the machine-readable result is in `evaluations/public_readiness_checks.json`.

A separate local-only comparison against backed-up manual A chunks found **zero matching 16-word sequences** in Git-eligible public text. It was not wired into preparation and does not reintroduce the private dependency. There are no remaining PDFs/manual-derived datasets in the public tree. The largest retained public asset is the runtime background image, approximately 1.85 MB (decimal).

Limitations: exact/pattern matching does not rule out unknown or transformed historical credentials, establish redistribution rights or replace a dedicated pre-publication secret scanner. There was no history in the retired or new repository to scan. External backups/earlier shares and browser-managed data outside this project were not inspected. Public author attribution in package metadata is retained intentionally; provider keys and local session dumps are not.

## Verification results

| Check | Result |
|---|---|
| Backend unittest discovery, offline providers | **151 passed**, including the new clean-tree preparation test |
| Existing scripted graph runner | **10/10 passed**, no network |
| Agent golden linked-policy runner | **12/12 scenario groups passed**, no network; not full golden replays |
| Frontend tests | **28 passed** |
| Frontend ESLint | Passed |
| Frontend TypeScript | Passed |
| Next.js production build | Passed; `/`, `/notebook`, `/setup` generated |
| Original guide/content hash check | 12/12 unchanged |
| Original A/B/C output comparison | Byte-identical to backed-up outputs |
| Historical retrieval JSON comparison | Unchanged |
| Backup integrity | 223-file snapshot verified; 73 retired originals reverified; Git metadata preserved |
| Public secret/large-file/path/manual-artifact scan | No findings; read limitations above |
| Manual-derived exact-text comparison | No public 16-word matches; limited overlap check only |
| Git index/history | No tracked/staged files, commits or remotes; branch `main` |

No paid LLM calls, Pinecone queries/uploads, source downloads or package installation were used. Initial frontend command lookup from a different shell working directory failed to locate npm; rerunning with the established project shell succeeded. No dependencies were installed to fix it.

## Remaining publication decisions and limits

1. **Owner must confirm rights/provenance for `frontend/public/images/studio-background.png`.** It is required by the existing UI, so it was retained to preserve behavior. The archived reference image is not proof of licensing. Do not claim artwork clearance from this audit.
2. **Choose an explicit repository/content license.** No license was invented on the owner's behalf. Original guide attribution and third-party reference links remain. Public Git hosting alone does not grant clear reuse terms.
3. Review the intended first staged diff and run a dedicated secret scanner before the first commit/push. This task intentionally left all public files untracked and unstaged.
4. The backend README is visibly marked as historical; use the new root quickstart. Some historical docs reference archived paths by design. Durable sessions, authentication and broad policy simplification remain future work, not publication-cleanup changes. Keep the demo local and single-worker.

The old nested Git backup and all private legacy material remain outside the public repository. Cleanup stops here; no commit or push was made.
