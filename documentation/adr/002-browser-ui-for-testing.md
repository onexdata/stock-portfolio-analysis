# ADR-002: Browser UI for Interactive Testing

**Status:** Proposed
**Date:** 2026-02-26

## Context

The project currently provides a Python demo script (`scripts/demo_client.py`) as the primary way to test the WebSocket backend. While the script demonstrates core functionality (streaming results, cancel-on-switch), it has limitations:

- **No visual feedback** — metric results appear as plain text lines in a terminal, making it hard to see the streaming behavior intuitively
- **Fixed scenario** — the script runs a hardcoded sequence (analyze AAPL, switch to GOOGL after 2 results, collect 5 GOOGL results, exit). Testing other tickers or sequences requires editing code
- **No interactivity** — the user can't explore the system freely, click different tickers at will, or observe cancel-on-switch on demand
- **Non-obvious to reviewers** — someone evaluating the project must install Python dependencies and run a script rather than just opening a browser

A browser-based UI would let reviewers and developers interact with the backend immediately and see real-time streaming behavior visually.

## Decision

### Single self-contained HTML file

**Choice:** A single `static/index.html` file with inline CSS and JavaScript, served by FastAPI at the root URL.

**Rationale:**

1. **Zero build tooling** — no npm, webpack, or framework dependencies. The file is plain HTML/CSS/JS that any browser understands natively. This keeps the project focused on the Python backend, which is the core deliverable.

2. **Inline everything** — CSS in a `<style>` tag, JS in a `<script>` tag. No external CDN dependencies, no separate `.css` or `.js` files. The UI works offline and loads instantly. This avoids introducing a build step or asset pipeline for what is fundamentally a testing/demo tool.

3. **Served by FastAPI** — the same `uvicorn` process serves both the WebSocket API and the UI. No CORS configuration needed, no separate dev server, no port conflicts. Adding a `GET /` route and a static file mount is ~5 lines of code.

### Why not a framework (React, Vue, etc.)?

- The UI is a testing/demo tool, not a production frontend. Framework overhead (build tooling, node_modules, transpilation) adds complexity disproportionate to the value.
- The entire UI interaction model is: connect to a WebSocket, send a JSON message, render incoming JSON messages. This is a few dozen lines of vanilla JS.
- Reviewers can read the entire UI in one file without needing to understand a component tree or state management library.

### Why not a separate `scripts/` file opened directly?

Opening an HTML file via `file://` would require CORS headers on the WebSocket server and would not reflect the "served by the backend" model. Serving from the same origin is simpler and more representative of a real deployment.

## UI Design

The UI provides four panels:

| Panel | Purpose |
|---|---|
| **Connection** | Session ID input (auto-generated UUID), connect/disconnect button, connection status dot |
| **Portfolio holdings** | Clickable ticker cards for the default holdings (AAPL, GOOGL, MSFT) plus a custom ticker input |
| **Analysis results** | Metric cards that animate in as results stream from the server, color-coded by value |
| **Activity log** | Scrollable raw JSON log of all messages sent and received, for transparency and debugging |

### Interaction flow

1. User opens `http://localhost:8000/` — sees the UI with a pre-filled session ID
2. Clicks "Connect" — WebSocket opens, status turns green
3. Clicks a ticker card (e.g., AAPL) — sends `{"action": "analyze", "ticker": "AAPL"}`, results stream in over 2-5 seconds
4. Clicks a different ticker while results are still arriving — sees cancel-on-switch in action (previous results cleared, new ones stream in)
5. Activity log shows all raw messages for debugging

## Changes

| File | Change |
|---|---|
| `static/index.html` | New file — self-contained HTML/CSS/JS UI |
| `app/main.py` | Add `GET /` route serving `index.html`, mount `static/` directory |

No changes to models, redis_client, portfolio, analysis, market, or config.

## Consequences

### Positive
- Reviewers can test the system by opening a browser — no Python client setup needed
- Visual streaming feedback makes the real-time behavior immediately obvious
- Cancel-on-switch is demonstrable interactively rather than through a hardcoded script
- Zero additional dependencies — no npm, no build step, no CDN
- The demo script remains available for automated/CI testing

### Negative
- Inline CSS/JS in a single file will become unwieldy if the UI grows significantly (acceptable — this is a demo tool, not a production frontend)
- No component reuse or state management beyond vanilla JS (acceptable for the scope)
- The UI is not responsive or accessibility-optimized (acceptable for a developer testing tool)

### Risks
- If the UI file grows past ~500 lines, consider splitting into separate files under `static/`. For now, a single file keeps things simple.
