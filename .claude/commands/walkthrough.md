---
description: Visual UI walkthrough — highlights each section in red and explains it using Chrome DevTools
allowed-tools: [mcp__chrome-devtools__list_pages, mcp__chrome-devtools__navigate_page, mcp__chrome-devtools__take_snapshot, mcp__chrome-devtools__take_screenshot, mcp__chrome-devtools__evaluate_script, mcp__chrome-devtools__wait_for, mcp__chrome-devtools__click, mcp__chrome-devtools__hover]
---

# UI Walkthrough

Walk the user through every section of the running UI using Chrome DevTools.

## Arguments

$ARGUMENTS

If arguments are provided, focus the walkthrough on that specific section (e.g., "results", "log", "holdings"). Otherwise, walk through all sections.

## Procedure

1. **Navigate** to `http://localhost:8000/` (or reload if already there).
2. **Wait** for the page to be connected (look for "Connected" text).
3. **Take a full-page screenshot** first for context.
4. **For each UI section**, in order:
   a. **Highlight it** by setting `outline: 3px solid red; outlineOffset: 4px` on the element via `evaluate_script`
   b. **Take a full-page screenshot** showing the red highlight
   c. **Explain** what the section does, how it connects to the backend, and any interactive behavior
   d. **Remove the highlight** before moving to the next section
5. **If a section is interactive** (e.g., ticker cards, analysis results), demonstrate it:
   - Click a ticker via `evaluate_script` calling `analyzeTicker("AAPL")`
   - Wait for results to stream in
   - Screenshot the populated state
## Sections to cover (in order)

| # | Section | CSS Selector | What to explain |
|---|---------|-------------|-----------------|
| 1 | Header + Status Badge | `.header` | App title, connection status dot (green/yellow/gray/red), status text |
| 2 | Portfolio Holdings | `.panel` (1st) | Ticker cards from config.json, share counts, click-to-analyze, custom ticker input |
| 3 | Analysis Results | `.panel` (2nd) | Streaming metric cards, spinner + counter, color-coded values, bar charts, cancel-on-switch |
| 4 | Activity Log | `.panel` (3rd) | Color-coded WebSocket messages (blue=sent, green=received, gray=info, red=error), auto-scroll |

## Tips

- Use `evaluate_script` to call JS functions directly (e.g., `analyzeTicker`, `createSession`) rather than clicking DOM elements.
- When demonstrating analysis, use `wait_for` with text `["5 / 5"]` and a 30s timeout.
