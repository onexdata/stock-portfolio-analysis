---
description: Architecture diagram walkthrough — opens the draw.io diagram in Chrome and walks through each component with highlights and explanations
allowed-tools: [mcp__chrome-devtools__list_pages, mcp__chrome-devtools__navigate_page, mcp__chrome-devtools__take_snapshot, mcp__chrome-devtools__take_screenshot, mcp__chrome-devtools__evaluate_script, mcp__chrome-devtools__wait_for, mcp__chrome-devtools__click, mcp__chrome-devtools__hover]
---

# Architecture Diagram Walkthrough

Walk the user through the system architecture diagram (`documentation/diagrams/system-architecture.drawio`) using the draw.io web editor and Chrome DevTools.

## Arguments

$ARGUMENTS

If arguments are provided, focus the walkthrough on that specific page or layer (e.g., "client", "tests", "redis", "workers"). Otherwise, walk through all three pages in order.

## Procedure

### Setup

1. **Open the diagram** by navigating to diagrams.net's viewer, passing the raw GitHub URL so it renders the `.drawio` file visually. The base URL pattern is:
   ```
   https://viewer.diagrams.net/?highlight=0000ff&layers=1&nav=1&page-id={PAGE_ID}&title=system-architecture.drawio#Uhttps%3A%2F%2Fraw.githubusercontent.com%2Fonexdata%2Fstock-portfolio-analysis%2Fmain%2Fdocumentation%2Fdiagrams%2Fsystem-architecture.drawio
   ```
   This loads the diagram directly from the GitHub repo and renders it fully in the diagrams.net viewer.

2. **Take an initial screenshot** to confirm the diagram loaded.

### Walking through the diagram

For each page (System Architecture → Tests → Client Architecture):

3. **Switch to the page** by navigating to the same viewer URL with the `page-id` query parameter set to the target page ID. The page IDs are:
   - `system-arch` — System Architecture (Page 1)
   - `tests` — Tests (Page 2)
   - `client-arch` — Client Architecture (Page 3)

   Example: to switch to the Tests page, navigate to the URL with `page-id=tests`.

4. **Take a screenshot** of the full page view.

5. **For each major component group** on the current page, in the order listed below:
   a. **Explain** what it represents, referencing the source files and line numbers shown in the blue link text
   b. **Describe the data flow** — follow the arrows connecting it to other components
   c. **Call out key design decisions** (e.g., why Lua scripts, why snapshot consistency, why cancel-on-switch)

6. **Take screenshots** between major sections to show progress.

## Pages and components to cover

### Page 1: System Architecture (top-to-bottom flow)

| # | Component | What to explain |
|---|-----------|-----------------|
| 1 | **Client layer** (Browser + WebSocket) | Single HTML page served at `/`, native WebSocket to `/ws/{session_id}` — no frameworks, no build step |
| 2 | **FastAPI Server** (yellow boxes) | Three components: WebSocket endpoint (`main.py:103`) receives `{"action":"analyze","ticker":"..."}` and streams results; Cancel-on-switch (`main.py:137`) cancels previous task group; Lifespan manager (`main.py:31`) starts Redis + market updater |
| 3 | **Analysis Engine** (purple box) | 5 parallel asyncio tasks via `asyncio.gather()` — portfolio_risk, concentration, correlation, momentum, allocation_score — each 2-5s, all share a frozen portfolio snapshot |
| 4 | **Market Updater** (green box) | Background loop every 30s, mock ±2% random walk prices, updates all active sessions |
| 5 | **Data layer** (red boxes) | `portfolio.py` is the only module touching Redis — thin CRUD API. `redis_client.py` handles connection + Lua script registration via EVALSHA |
| 6 | **Redis storage** (orange box) | RedisJSON document at `portfolio:{session_id}` with paths: `$.holdings`, `$.total_value`, `$.current_analysis`, `$.analysis_results`, `$.last_activity`. Three Lua scripts: `start_analysis` (:77), `append_result` (:93), `update_market` (:109). 24hr TTL refreshed on every write |
| 7 | **Arrow flows** | Trace the full request lifecycle: Client → WS → FastAPI → start_analysis → snapshot → Analysis Engine (5 parallel) → append_result → stream back → Client. Highlight the dashed arrows for streaming and snapshot return |

### Page 2: Tests

| # | Component | What to explain |
|---|-----------|-----------------|
| 1 | **Overview** | 100 tests, no Redis needed, all mocked — runs in <1s |
| 2 | **Test files** (left column) | conftest.py (shared fixtures), then each test file mapped to its source module |
| 3 | **Mock boundary** (red dashed line) | Everything to the right is mocked: redis_client.py (AsyncMock), Redis server (not needed), asyncio.sleep (instant), lifespan/market loop |
| 4 | **Key testing patterns** | Pure function testing (analysis metrics, mock prices), orchestration testing (gather + cancel), WebSocket integration via TestClient |

### Page 3: Client Architecture

| # | Component | What to explain |
|---|-----------|-----------------|
| 1 | **Serving layer** | FastAPI serves `static/index.html` at GET `/`, StaticFiles mount at `/static` |
| 2 | **UI Panels** | Connection (UUID session, status dot, connect/disconnect), Portfolio Holdings (3 ticker cards + custom input), Analysis Results (streaming cards with spinner, cancel-on-switch greying), Activity Log (color-coded monospace) |
| 3 | **JavaScript layer** | State management (5 variables), `connect()`/`disconnect()` lifecycle, `analyzeTicker()` with cancel logic, `handleMessage()` router, `addMetricResult()` DOM builder, `log()` activity logger |
| 4 | **WebSocket protocol** | Three message shapes: client→server request (AnalyzeRequest), server→client result (streamed x5), server→client error. Walk through the typical sequence and cancel-on-switch scenario |

## Tips

- The blue text on each component shows the source file and line number — these are clickable links to GitHub. Mention them as you walk through so viewers know exactly where to find the code.
- When explaining arrows, follow the color coding: yellow = server ops, purple = analysis flow, green = market updater, red = data layer, dashed = streaming/async responses.
- The diagrams.net viewer renders the full diagram interactively — use `evaluate_script` to interact with the diagram's DOM to highlight cells if needed, or describe components verbally while referencing the screenshot.
- Keep explanations concise — the diagram is meant to give reviewers a quick mental model, not replace reading the code.
