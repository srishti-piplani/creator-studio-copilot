# Frontend developer guide

Next.js App Router, TypeScript, Tailwind CSS, Lucide icons and locally owned UI components. Run commands from `frontend/` with Node.js 24.

## Install and connect

```sh
npm ci
```

The API defaults to `http://localhost:8000`. To override it:

```sh
cp .env.example .env.local
```

Set only `NEXT_PUBLIC_API_BASE_URL`, then restart Next.js. Never put provider credentials in a `NEXT_PUBLIC_*` variable. Run FastAPI separately using the [backend guide](../backend/README.md); its allowed frontend origin defaults to `http://localhost:3000`.

## Start

```sh
npm run dev
```

Open `http://localhost:3000`. Scripts use Next's Webpack option. Production startup uses `npm run build` followed by `npm start`.

## Pages and state

| Route | Responsibility |
|---|---|
| `/` | Learn/Troubleshoot/Discover shortcuts, conversations, setup summary and live activity |
| `/setup` | Selected microphone/interface and software documentation context |
| `/notebook` | Individual saved answers, citations, filtering and editable titles |

The logo returns home without deleting history. Mode shortcuts and New Conversation create separate threads; suggested prompts prefill without sending. Setup defaults are context, not restrictions on explicit user statements.

`StudioProvider` persists setup, Notebook and bounded recent history in browser localStorage. Each assistant message retains its topic title; saved titles/manual edits remain authoritative. There is no account sync. Backend session IDs can expire after a restart even though stored messages remain visible.

## API and progress

`lib/chat-stream.ts` uses fetch-based POST SSE for `/chat/stream`, then falls back to `/chat` with the same request UUID for transport failures. Application errors are surfaced. `GET /sessions/{id}` refreshes diagnostic history. Activity describes real operations; it is not simulated progress or model-token streaming.

## Checks

```sh
npm test
npm run lint
npm run build
npm run typecheck
```

The build creates Next's generated type declarations on a clean checkout. Tests use Node's built-in runner and mocked HTTP boundaries. Browser QA scripts under `scripts/` use the installed Playwright Core and a locally installed Chrome; scripts that send chat requests incur provider usage and are opt-in. No browser automation runs during ordinary `npm test`.

[Component reference](../docs/architecture/component_reference.md) · [System architecture](../docs/architecture/system_architecture.md)
