# Hestia frontend

Svelte 5 (runes) + Vite + TypeScript, built the same way as Apollo's. `make build`
writes `frontend/dist`, which FastAPI serves at `/` (`WEB_DIR`). The same build
works standalone (`http://pi:8003/`) and behind Pantheon (`http://pi:8000/hestia/`)
because every URL is relative and routing is hash-based.

Requires Node 22.12+ (or 20.19+) at build time.

## Develop

```bash
make run-dev      # API on :8003 + Vite on http://localhost:5173/ (proxies /api, /api/ws, /health)
make test         # pytest, then vitest + svelte-check
make check        # svelte-check + tsc only
```

## Layout

- `src/lib/*.ts`: pure logic, unit-tested (`*.test.ts`, vitest, node env).
  - `api.ts`: every fetch goes through here; paths are relative (`api/...`, `./health`).
  - `route.ts`: hash routes (`#/home`, `#/devices?open=<id>`, ...).
  - `store.ts`: optimistic writes, in-flight protection, All off + Undo, live-event reducers.
  - `live.ts`: WebSocket client (`api/ws`), jittered backoff, `on(type, fn)`.
  - `preferences.ts`, `format.ts`, `icons.ts`, `dim.ts`.
- `src/lib/*.svelte.ts`: reactive wrappers (`$state`) and singletons.
- `src/components/`, `src/screens/`: UI.
- `src/styles/tokens.css`: every colour, radius, space and duration.
- `icon-source.png`: high-resolution source art the PNG icons in `public/` were made from (not bundled).

## Rules

- Relative URLs only (no leading `/` in `fetch`, `href`, `src`, `new URL`, `base`).
  `tests/test_contract.py` enforces this.
- No hex colours in components: use tokens. Light theme values live in two
  identical blocks in `tokens.css` (`tokens.test.ts` checks).
- Tap targets >= `var(--tap-min)`. Animate only `transform`/`opacity`. No
  `backdrop-filter` (slow on the Pi kiosk).
- Durations go through `dur()` (`lib/motion.ts`), which honours reduced motion.

## Adding a screen

1. Add the tab to `TABS`/`TITLES`/`Screen` in `lib/route.ts` (and a test).
2. Create `src/screens/<Name>Screen.svelte`.
3. Render it in `App.svelte`'s `{#key}` block and add an item to `NavPill.svelte`.

## Icons

Inline Lucide paths in `components/Icon.svelte`. Add a glyph by pasting the inner
SVG markup from lucide.dev under a new key.
