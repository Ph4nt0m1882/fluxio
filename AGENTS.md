# AGENTS.md — Contributor & Coding Agent Guide for Fluxio

Fluxio (`import fluxio as fx`) is a lightweight, modern, real-time visualization engine in **Python + zero-dependency TypeScript `<canvas>`**, designed to run smoothly everywhere: desktop windows, Jupyter notebooks, SSH terminals, Raspberry Pi, static/animated exports, and embedded AI chatbots (Flutter / Web).

> **Note**: If you are an AI agent **using** Fluxio to generate charts for a user (rather than editing Fluxio's source code), read [`llms.txt`](llms.txt) or call `fx.llm_context("compact")` instead.

---

## 1. Architecture Overview

Every visualization in Fluxio flows through a **single declarative JSON Scene Protocol** (`Figure.to_spec()`) consumed by **three synchronized renderers**:

1. **Interactive HTML5 `<canvas>` Viewer (`web/src/`)**
   - Pure TypeScript, **0 runtime dependencies** (~28 KB minified bundle at `src/fluxio/_assets/viewer.bundle.js`).
   - Powers `fx.show(fig)` (`pywebview` native window or `--app` browser fallback connected via live WebSocket), Jupyter Notebook inline cells (`_repr_html_()`), and standalone `.html` exports.
   - Features Material SVG toolbar icons, pointer/wheel zoom & pan, play/pause/reset, PNG capture, fullscreen, and 60 FPS `smoothstep` hover transitions (0% idle CPU when settled).
2. **Headless 2D & Vector Exporter (`src/fluxio/render_2d.py`)**
   - Pure Python (`Pillow` + vector `SVG` + `ffmpeg` rawvideo pipe) — **never require Playwright or headless Chromium** so exports run in milliseconds on Raspberry Pi and mobile backends.
   - Outputs `.png` (2x supersampled), `.svg`, animated `.gif`, and `.mp4` / `.webm`.
3. **Terminal ANSI TrueColor Renderer (`src/fluxio/text_render.py`)**
   - Powers `print(fig)` (in-place stateful updates in manual loops), `fig.print()` / `fx.print(fig)` (live `btop`-style loop with keyboard controls), and `.txt` / `.ans` exports.

---

## 2. Key Commands

```bash
# 1. TypeScript viewer: typecheck, run Vitest unit tests, and rebuild bundle
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm typecheck
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm test
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm build

# 2. Rebuild AI documentation artifacts (llms.txt, llms-full.txt, fluxio.pyi)
uv run python -m fluxio.ai_docs

# 3. Verify MkDocs site in strict mode
uv run mkdocs build --strict

# 4. Run full Python test suite (unit, exports, Jupyter kernel, WebSocket, AI docs sync)
uv run pytest -v
```

---

## 3. Checklist for Implementing a New Chart from `TODO.md`

We develop **step-by-step (TDD)**: discuss API -> write tests -> implement -> verify.
Whenever adding a new visualization method `fig.<chart>(...)` from [`TODO.md`](TODO.md):

1. **Protocol & Figure API (`src/fluxio/protocol.py`, `src/fluxio/figure.py`, `web/src/protocol.ts`)**
   - Support placement via `fig.<chart>(..., row=..., col=...)` AND `fig[row, col].<chart>(...)`.
   - Support cascading aesthetics via `fig.style(...)`, `fig[row, col].style(...)`, and `cell.style(...)` (including `variant="classic" | "reverse" | "text"` and future `"lcd"` where applicable).
   - Support both static data and dynamic time functions `f(t)` / Python generators (`yield`).
2. **All 3 Renderers**
   - TypeScript `<canvas>` renderer (`web/src/renderer.ts`) -> run `corepack pnpm build`.
   - Headless Pillow + SVG renderer (`src/fluxio/render_2d.py`).
   - Terminal ANSI/Unicode renderer (`src/fluxio/text_render.py`).
3. **Documentation & AI Context (Enforced by `tests/test_ai_docs.py`!)**
   - Create `docs/charts/<chart>.md` following the concise structure in `docs/charts/number.md` and register it under `Charts` in `mkdocs.yml`.
   - Run `uv run python -m fluxio.ai_docs` to regenerate `llms.txt`, `llms-full.txt`, and `fluxio.pyi`.
   - Check off the completed item in `TODO.md`.
4. **Tests**
   - Add unit & visual/pixel tests in `tests/` and `web/tests/`, then ensure `uv run pytest` and `corepack pnpm test` pass 100%.
