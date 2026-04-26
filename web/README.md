# `web/` — touchscreen UI

The Phase 4a single-page dashboard. Served by the FastAPI core under
**`/ui/`**, opened in fullscreen Chromium kiosk mode on the Pi's
touchscreen, and works in any modern browser for development on macOS /
Linux / mobile.

## What this does

A single-page dashboard rendering the live state of every Hestia device
plus scenes and schedules. Built as **vanilla HTML + CSS + Alpine.js**
loaded from a CDN — no build step, no `npm install`, no transpiler.
Edit a file in `web/`, refresh the browser, see the change.

Three live regions:

- **Devices** — a row per registered driver with capability-aware
  controls (toggle switch, slider, play/pause, now-playing line).
- **Scenes** — a 2-column grid of large tappable cards. Tap = run.
- **Schedules** — a compact list with on/off pills.

State stays in sync via a persistent WebSocket on `/ws`. If a scene
fires from the scheduler, voice, or another tab, every connected client
updates without any user interaction. Optimistic updates make local
taps feel instant; the WS event reconciles authoritative state.

## Dev workflow

From the repo root:

```bash
make run-dev          # uvicorn main:app --reload
# in your browser:
open http://localhost:8000/ui/
```

Edit any file in `web/`. Hard-refresh in the browser
(`Cmd-Shift-R` / `Ctrl-Shift-R`). No build step.

To exercise the WebSocket while the UI is open, fire commands from a
second terminal:

```bash
curl -s -X POST http://localhost:8000/devices/relay-desk/action \
  -H 'Content-Type: application/json' -d '{"action":"toggle"}'
```

The dashboard toggle should flip on its own within a few hundred ms.

## File map

| Path | Owns |
|------|------|
| `index.html` | Page structure, inline icon `<symbol>` library, all DOM bindings |
| `style.css`  | Design tokens, layout grid, all components |
| `app.js`     | The single Alpine state object: REST + WebSocket + helpers |
| `ui/.gitkeep`| Future hook for extracted row markup (currently empty) |
| `icons/*.svg`| Lucide icons (mirror of the `<symbol>` blocks for git diff legibility) |
| `kiosk/start-kiosk.sh`   | Pi launcher: disables screen blanking, runs Chromium fullscreen |
| `kiosk/hestia-kiosk.service` | systemd unit template |

## Architecture

### One state object, no router

`app.js` exports a single `app()` factory consumed by Alpine via
`x-data="app()"` on `<body>`. Every piece of UI state lives there:

```
{
  tab,                   // 'dashboard' (room for future tabs)
  devices,               // list[DeviceInfo]
  scenes,                // list[Scene]
  schedules,             // list[Schedule]
  wsConnected,           // bool, drives the topbar dot
  boot_failures,         // list[{id, driver, error}] from /health
  clockText,             // header clock readout
}
```

Internals (prefixed with `_`) hold the WebSocket handle and reconnect
backoff. Bind helpers (`hasCap`, `iconForDevice`, `formatTime`, ...)
are methods on the same object so templates can call them directly.

### Data flow

```
   page load
       │
       ▼
   refreshAll()  ──►  GET /devices/, /scenes/, /schedules/, /health   (Promise.allSettled)
       │
       ▼
   connectWebSocket()  ──►  ws://host/ws    (exponential backoff on close)
       │
       ▼
   user taps                                  server pushes event
       │                                              │
       ▼                                              ▼
   optimistic flip       POST /devices/:id/action  applyEvent(event)
       │                          │                  │
       ▼                          ▼                  ▼
   re-sync from response     /scenes/:id/execute   patch matching device
                            PATCH /schedules/:id   flash scene card
```

Optimism is *intentional*. Every user-driven mutation flips local state
first, then `await`s the HTTP call, then reconciles from the
authoritative response (or reverts on failure). The WebSocket then
delivers the same fact a moment later — applying it is idempotent
because we just overwrite `device.state`.

### Why Alpine, not React/Vue/Svelte

The user's requirements bias hard against build tooling: a 7-inch Pi
touchscreen, kiosk Chromium, no developer machine on the Pi itself.
Vanilla HTML/CSS plus a 15kB framework is the simplest thing that meets
the spec — debuggable from DevTools, no bundler, no source map round
trip. Alpine gives us reactivity (`x-text`, `x-show`, `x-for`,
`x-model`) without leaving HTML.

If the dashboard ever outgrows Alpine, escape hatches: the `app()`
factory in `app.js` is the only stateful binding — porting to React or
Lit would mean rewriting `index.html` and `app.js`, but every endpoint
contract in `core/api.py` stays untouched.

## Theming

All colors, radii, and spacing live as CSS custom properties at
`:root` in `style.css`. To rebrand:

```css
:root {
  --color-accent: #f59e0b;        /* amber instead of green */
  --color-bg:     #050505;
  --radius-lg:    12px;            /* tighter rounding */
}
```

Light theme is **deferred** to a future tab (per the build plan). When
adding it, the cleanest path is a `[data-theme="light"]` selector
overriding the same tokens, then a body attribute toggle.

## Adding a new tab (future)

Tab dispatch is purely additive — no router, no state migration:

1. In `index.html`, add a `<button>` to `<nav class="tabs">`:
   ```html
   <button role="tab"
           :aria-selected="tab==='settings'"
           :class="{active: tab==='settings'}"
           @click="tab='settings'">Settings</button>
   ```
2. Add a sibling `<section x-show="tab==='settings'" class="settings"
   role="tabpanel">…</section>` inside `<main>`.
3. If the tab needs new fetched data, add an array on the state object
   and extend `refreshAll()` with another endpoint.

That's it. No build re-run, no router config.

## Adding a new device control (capability)

Capabilities are declared by the driver in `get_capabilities()` and
arrive as an array on `DeviceInfo.capabilities`. To wire a new one:

1. Add an inline icon `<symbol>` in `index.html` (and a mirror file in
   `icons/`).
2. Inside the `<article class="device-row">` template, add a new
   `<template x-if="hasCap(dev, 'your_cap')">…</template>` block with
   the control markup.
3. Add a handler method in `app.js` that POSTs to
   `/devices/:id/action` with the right `action` verb. Mirror the
   optimistic-flip + revert pattern of `toggleDevice` /
   `setBrightness`.
4. (Optional) Extend `iconForDevice()` to pick a more specific icon
   when this capability is present.

No CSS rule should be capability-specific unless the new control needs
its own visual treatment — drop component styles below the existing
`.toggle` / `.media-btn` / `.device-slider` blocks in `style.css`.

## Kiosk setup on the Pi

Install Chromium and the cursor-hider on the Pi:

```bash
sudo apt update
sudo apt install -y chromium-browser unclutter
```

Then install the launcher and systemd unit. The unit template assumes
the repo lives at `~/hestia` — edit the `ExecStart=` line if yours
doesn't.

```bash
mkdir -p ~/.config/systemd/user
cp ~/hestia/web/kiosk/hestia-kiosk.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now hestia-kiosk.service
```

Confirm:

```bash
systemctl --user status hestia-kiosk.service
journalctl --user -u hestia-kiosk.service -f
```

You should see a fullscreen browser pointed at
`http://localhost:8000/ui/`. To override the URL (e.g. for a remote
Pi):

```bash
HESTIA_UI_URL=http://hestia.local:8000/ui/ ~/hestia/web/kiosk/start-kiosk.sh
```

The script also disables DPMS, screen blanking, and screen saver — the
touchscreen will stay lit indefinitely.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| **Empty page at `/ui/`** | `WEB_DIR` doesn't exist or wasn't mounted | Confirm `web/index.html` exists; check server log for `"Static UI mounted at /ui/"`. The mount is silent if `WEB_DIR` is missing. |
| **`/ui` (no slash) returns 404** | StaticFiles only serves under the trailing-slash form | Always link as `/ui/`. |
| **Toggles flip but revert** | The HTTP call returned non-2xx | DevTools → Network. Check server log; expect a stack trace from the driver. |
| **No live updates** | WebSocket never connected | DevTools → Network → WS — the `/ws` row should be 101. The header dot is gray when offline. |
| **WS connects then immediately drops** | Reverse proxy stripping `Upgrade` headers | Bypass any proxy for development; or configure your proxy to forward `Upgrade` and `Connection`. |
| **CORS errors** | UI loaded from a different origin than the API | The shipped layout is same-origin (`/ui/` and `/devices/` served from one process). Cross-origin layouts need `fastapi.middleware.cors` and a different deploy story. |
| **Schedules show wrong time** | Pi clock not in sync | `timedatectl status` on the Pi; install `systemd-timesyncd` or `chrony`. |
| **Touch targets miss** | Custom Pi DPI / tablet mode | All controls are sized to ≥44px, but kiosk DPI scaling can interact oddly — try `--force-device-scale-factor=1.0` in the kiosk script. |
| **Scene flash never appears** | Server `scene_executed` event not firing | Confirm `core/scenes.py` publishes after each step; check the WS test client (`make ws-test`) for the event. |

## API surface used (read-only summary)

The UI talks to these endpoints — see `core/api_README.md` for the
authoritative spec.

| Method | Path | When |
|--------|------|------|
| GET    | `/devices/`           | page load (refreshAll) |
| POST   | `/devices/:id/action` | every toggle / play / pause / set_brightness |
| GET    | `/scenes/`            | page load |
| POST   | `/scenes/:id/execute` | scene card tap |
| GET    | `/schedules/`         | page load |
| PATCH  | `/schedules/:id`      | pill toggle |
| GET    | `/health`             | page load — boot-failure banner |
| WS     | `/ws`                 | persistent — receives `Event` JSON |

Event types consumed: `device_state_changed`, `scene_executed`,
`device_registered`, `device_error`. Other types are logged at debug
level and ignored.
