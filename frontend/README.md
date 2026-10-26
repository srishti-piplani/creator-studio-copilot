# Creator Studio Copilot frontend

A local Next.js App Router workspace with TypeScript, Tailwind CSS, Lucide icons,
and a locally owned shadcn/ui Button (Radix Slot/CVA). `components.json` preserves
the shadcn aliases and configuration. The Assistant is the default route; Learn,
Troubleshoot and Discover are prompt shortcuts, never frontend intent overrides.

## Run locally

Use two terminals from the project root. Existing backend dependencies stay in uv.

```sh
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

```sh
cd frontend
npm run dev
```

Alternatively, from the project root: `npm --prefix frontend run dev`.

Open http://localhost:3000 . The backend CORS configuration allows that origin.
Node 24 is recommended (the development machine uses 24.22.1). If your terminal
cannot find npm, activate your installed Node version with `nvm use 24`. Dependencies are
already installed; use `npm ci` when recreating this frontend on another checkout.
The lockfile pins the resolved versions.

The client defaults to `http://localhost:8000`. To override it, copy `.env.example`
to `.env.local` and set only `NEXT_PUBLIC_API_BASE_URL`, then restart Next.js.
**Never copy backend credentials into the frontend.** Provider keys remain in
`backend/.env`. No frontend server route proxies or logs credentials.

Development and production builds use Next's supported Webpack option because
Turbopack's local CSS worker was denied port binding in this execution environment.
No runtime feature depends on that choice. Fonts use system Arial/Helvetica and
require no remote font download.

## Features and contracts

- `/`: editable welcome shortcuts; Markdown conversations; source references;
  honest loading state; keyboard send; retry and expired-session handling.
- `/notebook`: complete saved answers, original questions, citations, resource
  cards, dates, text search, category filters, reader, and confirmed deletion.
- `/setup`: both supported software versions are displayed; one optional
  microphone and one optional interface can be selected, saved, or deselected.
- `lib/api.ts`: typed `POST /chat` and `GET /sessions/{session_id}` client. Sends
  only `message`, optional `session_id`, and optional `equipment` from the actual
  FastAPI schema. Setup hardware generations travel inside equipment labels.
- `components/studio-provider.tsx`: browser-local persistence and in-flight state.
  Notebook, setup and conversation use independent versioned localStorage keys.
- `components/answer.tsx`: Markdown, expandable sources, linked citation IDs,
  official/community labels, resource cards, and Save Answer.

Explicit equipment in a question suppresses a conflicting saved default in that
category. A small backend routing correction uses the model's complete current
equipment list rather than accumulating contradictory old products; the routing
prompt prioritizes explicit current mentions while retaining other categories.
No new API fields were required. Neither RAG nor the corpus was rewritten.

The backend has no structured diagnostic options or related-question suggestions.
The frontend therefore uses ordinary chat input, and shows 'That worked' / 'That
didn't work' only when the backend is awaiting a step outcome. These send normal
user messages to the same session. Attempted-step history comes from the actual
session endpoint, not inferred frontend activity. There are no fake tool events.

Studio Knowledge citations retain their underlying guide titles and reference
URLs; live citations open the returned source. No manufacturer text is indexed
by this frontend. Raw HTML in Markdown is not enabled. Outbound links are limited
to HTTP(S), use a new tab, and do not inherit opener access.

## Persistence and limitations

Notebook and setup persist in this browser, without another AI request. A refreshed
conversation restores its messages and session ID and checks the backend session.
Backend sessions live in memory: restarting or reloading FastAPI expires them.
An expired conversation is kept readable and a new conversation can be started;
saved Notebook entries are unaffected. Storage failures are reported explicitly.
No authentication, cross-device sync, hardware detection or streaming is claimed.

Chat errors expose retry controls; a failed-message retry does not duplicate the
visible user message. Transport failures can leave the backend request outcome
unknown, so the UI notes that retrying might resend an already processed request.
A 503 is never replaced with a fabricated answer. AI factual accuracy and source
licensing remain backend/evidence limitations; resources retain the provider's
license label or explicitly say 'License not verified.'

## Verification

```sh
npm run lint
npm run typecheck
npm test
npm run build
# Serve the production build:
npm run start
```

Eight unit tests exercise the typed API client, equipment precedence, metadata
labels, safe links, and error handling. Backend regression tests:

```sh
cd ../backend
uv run --no-sync --offline python -m unittest discover -s tests -q
```

Opt-in real browser/provider QA, with both servers running:

```sh
cd frontend
node scripts/browser-check.mjs
```

The browser script uses `playwright-core` with the existing macOS Chrome binary;
set `CHROME_PATH` for a different installation. It downloads no browser and never
mocks AI answers. It deliberately aborts one request to exercise the unavailable-
backend path. Provider 503 responses may be retried at most twice using the UI.
Reports are written to `../evaluations/frontend_browser_results.json`; screenshots
are placed in `/tmp/creator-studio-frontend/`. The run uses an isolated browser
profile and does not alter your normal Notebook or setup.

Diagnostic compatibility: when the model returns both a question and a fix, the
backend asks the question first and discards the unasked fix. A pure diagnostic
question may omit citations; factual advice still requires valid source IDs.

## Phase 4B: product polish and local history

The landing page now places the composer in normal flow after three workflow
shortcuts and a four-card **My Studio Setup** panel. Software cards show supported
**documentation** versions, not detected installed versions. New users default
to AT2035 + Scarlett 2i2 (2nd Gen); saved selections, including intentionally
cleared selections, take precedence. A small original SVG depicts an interface;
other icons are Lucide (MIT). Conversation text, labels and citations are larger.
The conversation composer alone is sticky; the end-of-conversation scroll target
sits after it so the last answer can be brought fully above the composer.

Recent Conversations are separate from Notebook answers. New Conversation keeps
existing threads; reopening a thread preserves its original backend session ID.
History uses `creator-studio:history:v1` and `creator-studio:active:v1`, migrating
the old single-conversation key without another model request. Retention is
limited to 20 threads, 80 messages per thread and 1,000,000 serialized characters
(roughly 2 MB of UTF-16 storage). Older threads/messages are trimmed. Notebook
entries remain independent. A backend restart cannot restore LangGraph memory;
expired threads remain readable, and a new conversation is required to continue.

Notebook titles use substantive user questions. Simpler-explanation follow-ups
inherit their topic, while an actual routed topic change can use the new topic.
The original question, full answer and evidence remain saved. Titles can be edited
from the reader. Previously saved entries are retained.

New responses may include `activities`, `topic_title`, and `new_topic`. The
collapsible **How I researched this** panel renders actual completed/failed
backend activities, never inferred progress or hidden reasoning. Old saved
responses without activity metadata do not get fabricated research histories.
Agent Studio citations now point directly to approved source passages rather
than to an intermediate generated synthesis. Research/check labels do not prove
claim-level factual accuracy or verify resource licensing.

### Isolated QA

A running development frontend/backend need not be stopped. In separate terminals:

```sh
# From backend/
FRONTEND_ORIGIN=http://localhost:3001 uv run uvicorn app.main:app --port 8001
```

```sh
# From project root
CREATOR_STUDIO_QA=1 NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 npm --prefix frontend run build
CREATOR_STUDIO_QA=1 npm --prefix frontend run start -- --port 3001
```

```sh
# From frontend/
node scripts/phase4b-check.mjs
```

`.next-qa` is an ignored isolated build directory. CORS defaults to port 3000;
`FRONTEND_ORIGIN` is a process-environment override for another local frontend.
The QA script uses an isolated Chrome profile and real backend responses. It
checks laptop/desktop/mobile geometry, saved setup, history, migration, expiry,
Notebook title inheritance, real how-to/troubleshooting/Discover answers and
research actions. It writes `../evaluations/phase4b_browser_results.json` and
screenshots under `/tmp/creator-studio-phase4b/`. Assertions about a response's
shape are not a substitute for the separate manual factual review in the report.

Discover uses structured selection of real resource IDs and content relevance.
The application renders a neutral introduction and consistently unverified usage
labels; it does not publish model-inferred license permissions as answer prose.
Unverified licensing/price claims are omitted from relevance descriptions. Source
page titles are retained verbatim and do not establish a license or download right.
