> Historical pre-cleanup audit. Phase 5B resolved several findings; see [the cleanup report](github_cleanup_report.md) for the current repository and archive status. Paths classified below describe the audited snapshot and may now exist only in the private archive.

# GitHub readiness audit

Reviewed 2026-10-25. Analysis/documentation only: no code/configuration/README edits, deletions, index writes, package installation, commits or pushes. No live inference/search calls were made. Paths are relative to the project root unless specified.

## Executive assessment

The working application has a clear local MVP architecture: Next.js browser state, FastAPI, a bounded six-node LangGraph, Nebius structured inference, original-guide Pinecone retrieval and Keenable official/resource research. The original educational corpus and the historical manufacturer-manual corpus are separated in runtime and namespaces.

**Do not publish the directory blindly.** The project root has no Git repository; the only discovered repository is `backend/.git`, on an unborn `master` branch. It has zero tracked/staged files, zero commits, no reflog entries and zero counted objects. Publishing only that repository would omit the frontend/data/evaluations/docs. Adding the backend from a future root repository while nested metadata remains risks an embedded-repository/gitlink result rather than ordinary source files.

Two material content/reproducibility issues remain: raw evaluation artifacts outside ignored directories contain source excerpts/prompts that need a public-release review; and original-guide preparation depends on an ignored manual-derived file. Neither was changed during this audit.

## Observed structure

```text
creator-studio-copilot/          # intended publication root; not currently a Git worktree
├── .gitignore
├── backend/                    # only existing .git; no tracked files/history
│   ├── .env                    # populated credentials; local only
│   ├── .env.example
│   ├── app/                    # actual FastAPI/agent/RAG code
│   ├── scripts/                # evaluation and historical audit commands
│   ├── src/backend/            # uv starter package
│   ├── tests/fixtures/
│   ├── pyproject.toml, uv.lock, .python-version
│   └── .venv/                  # local only
├── frontend/                   # Next.js source, package-lock.json, .env.example
│   ├── app/, components/, lib/, tests/, public/
│   └── node_modules/, .next/   # local artifacts if present, excluded
├── data/
│   ├── studio_knowledge/       # original source guides + manifest/references
│   ├── studio_processed/      # ignored original generated chunks
│   ├── corpus/                # ignored third-party PDFs; only .gitkeep eligible
│   ├── processed/             # ignored manual-derived sections/chunks/quarantine metadata
│   ├── sources.json, selected_sections.json
│   └── golden_questions.json, agent_golden_questions.json
├── evaluations/               # mixed publishable reports and review-required raw traces
├── design/reference/          # source design images; provenance review needed
└── docs/                      # five documents added by this audit
```

## Active, reproducibility, legacy and cleanup classification

A = active runtime dependency; B = reproducibility/evaluation asset; C = legacy experiment; D = conditional safe cleanup candidate; E = sensitive/restricted or review-required raw artifact. An E classification for third-party text means **do not stage before rights/content review**, not a legal conclusion that every short excerpt is forbidden.

| Exact path or bounded path group | Class and evidence | Safe removal? / recommendation |
|---|---|---|
| `backend/app/main.py`, `app/graph/`, `app/tools/web_search.py`, `app/services/{chat_jobs,evidence_evaluator,resource_license,tracing}.py`, `app/storage/sessions.py` (all under backend) | A: reachable from API/agent imports | No; retain runtime code, including optional tracing module imported by the factory |
| `backend/app/rag/{generate,retrieve,pinecone_store,pinecone_records,studio}.py` | A/B: runtime service/manifest validation plus explicit build/index commands | No whole-module removal; retain |
| `backend/app/rag/{ingest,chunking,preprocessing,prepare}.py` | B/C with shared A import dependencies: `studio.py` imports loader, chunking, coverage/write helpers; chunking imports stable IDs | Not safe to delete wholesale, even though manual `prepare()` is not runtime |
| `frontend/app/`, `frontend/components/`, `frontend/lib/`, `frontend/public/images/studio-background.png` | A: Next routes, imports and referenced image | Retain source and runtime image; confirm artwork rights |
| `data/studio_knowledge/` | A/B: `validate_guides()` and retrieved guide revisions depend on manifest/content | Retain 12 originals, manifest, attribution and source registry |
| `data/golden_questions.json`, `data/agent_golden_questions.json` | B: 20 RAG questions versus 12 agent scenarios; no runtime label consumption | Retain and explain scope |
| `backend/tests/`, `backend/tests/fixtures/corpus/synthetic.md`, `backend/tests/fixtures/sources.json`, `backend/tests/fixtures/pinecone_synthetic.json` | B: offline regression and isolated five-record integration fixture | Retain synthetic labels; not real documentation |
| `backend/scripts/{golden_sets,evaluate_agent,evaluate_agent_golden}.py` | B: dataset validation and scripted graph/policy evaluation | Retain; linked checks are not live golden replays |
| `evaluations/studio_retrieval.json`, `agent_scenarios.json`, `agent_golden_regressions.json`, `phase5a_report.md`, `phase5a_baseline/` | B: current scope/metrics/comparability evidence | Retain reviewed results and baseline; preserve tests' baseline references |
| `backend/scripts/agent_live_check.py`, `phase4j_live_check.py`; `evaluations/phase4k_live_check.py`, `phase4m_live_check.py`, `answer_quality_probe.py`, `model_benchmark_run.py`, phase-specific follow-up/resource probes | B/C: opt-in provider-backed experiments, not runtime | Archive older probes if desired; do not call duplicates “unused” without preserving reproduction commands. Never run automatically |
| `backend/scripts/audit_corpus.py`, `data/selected_sections.json`, `data/sources.json`, `evaluations/corpus_audit.{md,json}`, `phase2b_report.{md,json}` | B/C: original PDF selection/extraction evidence | Retain reviewed metadata/reports as historical experiment; verify no substantial extracted text before publishing |
| `backend/app/rag/pinecone_cli.py` | B/C: synthetic test and legacy manual upload/query CLI; still executable | Do not delete casually; separate/document risky manual upsert command before public quickstart |
| `data/studio_processed/` | B: reproducible original-guide generated JSONL (36/24/12 chunks) | Ignored. Keep local or rebuild after prerequisite is fixed; do not assume safe to remove while indexing/preparation reproduction is blocked |
| `data/processed/` including `A/chunks.jsonl`, `B/chunks.jsonl`, `C/chunks.jsonl`, `sections.jsonl`, `selection_manifest.json`, `exclusions.jsonl`, `procedure_examples.jsonl` | C/E: manufacturer-derived source text/chunks and extraction/quarantine reporting; 375/232/168 chunks | Keep local. **Not safe to remove today:** Studio preparation currently reads manual A chunks for phrase comparison |
| `data/corpus/logic_pro/logic-pro-mac-user-guide.pdf` | E: downloaded manual, 45.83 MiB | Exclude; preserve original local source while historical reproduction is needed |
| `data/corpus/davinci_resolve/DaVinci_Resolve_21.1_Reference_Manual.pdf` | E: downloaded manual, 174.72 MiB | Exclude; also exceeds common Git-host large-file thresholds. Do not bypass rights review with LFS |
| `data/corpus/scarlett_solo/scarlett_solo_4th_gen_user_guide-pdf-en.pdf` | E: downloaded manual, 18.90 MiB | Exclude |
| `data/corpus/scarlett_2i2/Scarlett 2i2 2nd Gen User Guide v1.1 English - EN.pdf` | E: downloaded manual, 1.14 MiB | Exclude |
| `data/corpus/at2035/at2035_submit.pdf`, `data/corpus/at2020/at2020_english.pdf` | E: downloaded specifications/manuals, 0.36/0.11 MiB | Exclude regardless of small size |
| `backend/.env` | E: nonempty Pinecone/Nebius/Keenable credentials | Never track; ignored by nested and intended root rules. Keep `.env.example` blank-secret template |
| `evaluations/answer_quality_trace.json`, `phase4k_live_results.json`, `phase4i_source_evidence.json`, other `*live_results.json`, `*recheck*.json`, `model_benchmark_results.json`, `answer_quality_prompt_inventory.json` | B/E review: raw model/tool payloads, prompts, source excerpts and potentially identifying session/configuration data | Not ignored by current rules. Keep private until sanitized/permission-reviewed; retain public summaries rather than assuming all raw traces are safe |
| `evaluations/phase4b_browser_results.json`, `phase4h_browser_results.json`, `frontend_browser_results.json`, other browser/navigation reports | B/E review: recorded UI/session/storage evidence may contain saved text or local identifiers | Inspect/sanitize before staging; do not publish a real localStorage export |
| `evaluations/model_benchmark_catalog.json`, `model_benchmark_public_catalog.json` | B: account/public model discovery evidence; not runtime configuration | Review account-specific metadata; keep only necessary public benchmark evidence |
| `design/reference/creator-studio-concept.png`, `design/reference/studio-background.png` | B/C: design references; second duplicates frontend background bytes/size | Conditional archive of reference copy; confirm no tests/docs need it and retain runtime image. Do not infer redistribution rights from filename |
| `backend/app/storage/notebook.py` | D: placeholder only; actual Notebook persists in frontend; no active storage implementation | Candidate after a final reference check. Tiny file; deletion is low priority, not a submission requirement |
| `backend/src/backend/__init__.py` | C/D: starter greeting referenced by `[project.scripts] backend` and uv build package | **Not independently removable** without packaging/script adjustment; preserve until planned change/tests |
| `.venv/`, `node_modules/`, `.next/`, `.next-qa/`, `__pycache__/`, `frontend/tsconfig.tsbuildinfo`, coverage/build caches | D/local artifacts; excluded by current patterns | Regenerable; never stage. Stop running servers before deleting active build/env directories; no need to delete for publication |
| Historical `phase4*` Markdown reports | B/C: evidence of earlier defects/results, superseded by later fixes | Archive/index as history; do not present old pass counts as current verification |

No standalone quarantine output directory was observed in the small data inventory; the earlier pipeline's extraction exclusions/quarantine decisions are represented in processed metadata/reports. No repository-local browser profile/storage database was found in this inventory; this does not inspect browser-managed storage outside the project.

## Git, ignore rules and security checks

Read-only checks performed:

- `git rev-parse --show-toplevel` at root: not a Git repository.
- `git -C backend status --short`: source/README/lockfile directories untracked; no staged files.
- `git -C backend ls-files`: empty. `rev-list --all --count`: 0. Reflog empty; counted loose/packed objects 0.
- Repository metadata discovery excluding dependency/build trees found only `backend/.git`.
- Nested `check-ignore` confirms `.env` and `.venv` ignored; `.env.example` and `uv.lock` are eligible for tracking.
- Root rules exclude `.env` variants, venvs, dependencies, caches/builds, manual corpus content, manual outputs and original processed outputs. Directory exceptions preserve only corpus `.gitkeep` placeholders. There is no frontend-specific `.gitignore`.
- The root `.gitignore` does **not** protect parent data/evaluations inside the current backend-only repository; those paths are outside that repository entirely. Conversely it will apply from the intended future project-root worktree. Ignore rules never remove already-tracked content automatically.
- A local text scan excluding dependency/build/Git trees and large/binary files compared files against currently configured credential values. **No exact configured-key match outside `backend/.env` was found.** Private-key/GitHub/AWS token marker checks found no additional matching paths. Values were never printed. Populated secret-variable names: Pinecone, Nebius and Keenable API keys; optional Langfuse/Fireworks values are absent.

This was a scoped scan, not a certified secret scanner: it cannot rule out unknown/rotated keys, transformed encodings, excluded binary/dependency files, external backups/remotes or earlier shared artifacts. The only observed local repository has no history to scan. Before publishing, inspect the intended staged file list/diff, run a dedicated secret scanner on staged content and all history of any repository imported later, and review third-party text independently. If actual exposure is found, rotate/revoke affected credentials; rewriting history alone does not revoke them.

Current rules have **no general evaluation-trace, log, temporary-file or browser-export exclusion**. The manual directory ignores do not cover excerpts copied into `evaluations/`. Do not add all reports wholesale. Prefer an explicit public artifact list and a reviewed/sanitized release report. API keys remain backend-only; frontend template only exposes the backend URL.

The API is unauthenticated, including session inspection and paid-provider chat. CORS is not authorization. Acceptable for a localhost demo, not safe to expose as an unrestricted public service. Backend checkpoints/locks are unbounded, and simultaneous requests must stay within one worker for coherent local state. This is an operational limitation to disclose, not a recommendation to build authentication during this documentation-only task.

## Reproducibility and material quality findings

1. **Original preparation depends on private output.** `prepare_studio` unconditionally reads ignored manual A chunks for phrase-overlap comparison. A public checkout cannot run the advertised original preparation/index command without them. Separate the optional private comparison from original-guide preparation in a later approved change; keep the originality limitation explicit.
2. **Index bootstrap differs from runtime.** `get_rag_service` and `studio_cli connected` use `ensure_index(create=False)`. A clean account needs explicit compatible-index creation before original indexing; current easy creation path is in the synthetic administrative smoke test and also writes synthetic records. Document an intentional bootstrap rather than implying runtime auto-creates an index. Index creation/upserts require separate approval, not this audit.
3. **README contains historical contradictions.** `backend/README.md` still says config/external calls are not implemented, tests are future and data initially empty in early sections. Later phase sections describe the working system. Root README/license were not present. Replace the onboarding narrative only after this audit is approved; retain phase reports as history.
4. **Reproducible dependency files exist.** Keep `backend/uv.lock`, `.python-version` (3.11), `pyproject.toml`, `frontend/package-lock.json`, package/config files and templates. Node 24 is recommended in frontend README; no root unified setup or enforced Node version was observed. `backend` console command prints the uv greeting; the real server command is `uv run uvicorn app.main:app --reload --port 8000` from backend. App source is outside the starter built package; treat repository execution and packaged distribution as different paths.
5. **Evaluation claims need qualification.** Current RAG report has 1.000 guide recall for all strategies; this is not answer accuracy. Twelve agent golden rubrics have linked scripted checks, not a live quality score. Older test counts in reports are historical. No tests or live model calls were rerun for this documentation-only audit.
6. **Generation safeguards are layered and fallible.** Good metadata/span/citation guards and safe service errors exist. Multiple model reviews use the same model; provenance cannot prove semantic completeness. The dedicated Direct Monitor path is intentionally scoped; broad troubleshooting still depends on generation/evaluation. Avoid claiming general autonomous diagnosis.
7. **Data rights and privacy are separate from credential checks.** Original guides identify AI assistance and technical references. Preserve those notices. Verify rights for artwork, original prose publication and redistributed excerpts, and choose a repository code license deliberately. This audit makes no legal compliance determination.

## Recommended cleanup order — approval required

| Priority | Action | Risk / verification after approval |
|---|---|---|
| **P0** | Decide the project-root repository as publication boundary; preserve/archive the empty backend Git metadata before establishing one root repo | Metadata operations can alter Git behavior. Inspect root/nested status and staged paths afterward; no app tests needed for metadata-only changes. Do not delete `.git` blindly |
| **P0** | Define public-file exclusions/allowlist for raw traces, third-party extracts, secrets and local artifacts; inspect prospective/staged contents | Risk: accidentally hiding useful eval evidence or leaking restricted content. Check ignore matches, staged diff, file sizes, secret scanner and rights review; no inference calls needed |
| **P0** | Remove the private-manual-output prerequisite from clean original-guide reproduction in an approved targeted change, or explicitly mark preparation non-reproducible until fixed | Do not weaken provenance silently. Test preparation with original guides only and no `data/processed`; assert unchanged original content/chunk coverage. Do not publish private text as the workaround |
| **P1** | Write one current root README and correct stale backend sections; distinguish runtime, offline evaluation and potentially writing/paid commands | Documentation drift can send reviewers to legacy manual upload. Verify commands/static paths; do a clean local setup smoke check later, with any paid/indexing operations explicitly separated |
| **P1** | Document compatible index bootstrap, required namespaces, credential setup, one-worker/in-memory limits and browser-only Notebook persistence | Risk: cloud spend or duplicate/stale records if tested blindly. Review configs first; only approved read-only/live checks or synthetic writes as separately authorized |
| **P1** | Publish sanitized benchmark/evaluation summaries and reference historical experiments explicitly | Retain expected baseline assets used by tests; run dataset/linked-scenario tests after moving any paths. Do not equate mocks with model quality |
| **P1** | Review image/content attribution and select code/content licensing | Rights decision, not code refactor. Validate referenced image paths if files are archived |
| **P2** | Archive superseded probes/reports; remove placeholder/starter code only with package/import/reference updates | Run affected import/CLI/tests; do not remove shared preparation utilities or fixtures based on runtime-only analysis |
| **P2** | Review overlapping answer-policy branches and styles; plan durable sessions/auth/rate limits if hosting beyond localhost | Behavioral/UX risk; requires focused regression and deployment tests. Not needed as cosmetic cleanup before a local certification demo |

## Retain / archive / exclude summary

**Retain:** all active source, configuration and lockfiles, original Studio guides/manifests/attribution, synthetic fixtures, current golden datasets and offline tests, reviewed reproducibility metadata and current summaries, the five architecture/audit documents.

**Archive after reference review:** historical PDF audit scripts/reports, superseded paid probes and old phase outputs, optional design references. “Archive” does not grant redistribution rights; raw restricted text may need a private archive outside the public repository.

**Keep local/excluded:** credentials, environments/dependencies/builds, manufacturer PDFs/extracts/chunks, browser exports, unreviewed raw prompts/tool/source traces and logs. Preserve the existing local files until approved cleanup and reproduction dependencies are addressed.

This review created documentation only. It did not initialize a root repository, move nested Git metadata, change ignore rules, sanitize existing artifacts, rewrite READMEs or implement the proposed fixes.


## Audit verification record

Checked source entry points/imports and actual graph construction, current metadata/counts,
Git status/tracked files/history/object inventory, root/nested ignore rules and local
credential-value/pattern matches (paths/names only). All 12 original guide SHA-256 values
still match their manifest. The five new Markdown documents have balanced fenced code
blocks; Mermaid diagrams reflect actual graph edges or clearly labeled component/data
flows. No automated Mermaid rendering was performed. Existing reports were read, not
regenerated. No backend/frontend test suite was run because application code was unchanged.
