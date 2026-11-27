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

## 3. 3-Level OOP Class Hierarchy (`src/fluxio/charts/` & `web/src/charts/`)

All visualizations strictly follow a **maximum 3-level inheritance hierarchy** (1 concrete class = 1 dedicated file):

- **Level 1 (Root)**: `Visual` (`src/fluxio/charts/base.py`) — provides standalone `.show()`, `.save()`, `.print()`, `print(v)`, `_repr_html_()`, `.style(...)`, and attaches into multi-cell `fx.Figure(rows, cols)` via `fig.<chart>(...)` or `fig[r, c] = fx.<Chart>(...)`.
- **Level 2 (6 Geometric Families in `src/fluxio/charts/families.py`)**:
  - `Indicator(Visual)` (`Number`, `Stat`, `Gauge`, `BarGauge`)
  - `Axis2D(Visual)` (`Plot`, `Scatter`, `Bar`, `Hist`, `Boxplot`...)
  - `Field2D(Visual)` (`Imshow`, `Pcolormesh`, `Contour`, `Quiver`...)
  - `Polar2D(Visual)` (`Polar`, `Pie`...)
  - `Space3D(Visual)` (`Plot3D`, `Scatter3D`, `Surface3D`, `Voxels`...)
  - `Scene(Visual)` (`NodeGraph`, `FlameGraph`, `TileMap`, `Interactive`, `Simulation`...)
- **Level 3 (Concrete Charts)**: `src/fluxio/charts/<chart>.py` + matching TypeScript renderer in `web/src/charts/<chart>.ts`.

---

## 4. Checklist for Implementing a New Chart from `TODO.md`

We follow [`TODO.md`](TODO.md) **strictly in order, one method at a time**, developing **step-by-step (TDD)**: discuss API -> write tests -> implement -> verify. Never introduce a new transverse feature partially on one chart if it retroactively affects already-validated charts (do a dedicated global pass instead).

Whenever adding a new visualization `fx.<Chart>` / `fig.<chart>(...)`:

1. **Class & Figure API (`src/fluxio/charts/<chart>.py`, `src/fluxio/figure.py`, `web/src/protocol.ts`)**
   - Subclass the appropriate Level-2 family (`Indicator`, `Axis2D`, `Field2D`, `Polar2D`, `Space3D`, or `Scene`).
   - Support standalone usage (`fx.<Chart>(...).show()`) AND grid placement (`fig.<chart>(...)`, `fig[r, c].<chart>(...)`, `fig[r, c] = fx.<Chart>(...)`).
   - Support cascading aesthetics via `fig.style(...)`, `fig[r, c].style(...)`, and `visual.style(...)`.
   - Support both static data and dynamic time functions `f(t)` / Python generators (`yield`).
2. **All 3 Modular Renderers**
   - TypeScript `<canvas>` module (`web/src/charts/<chart>.ts`) -> run `corepack pnpm build`.
   - Headless Pillow + SVG renderer registered via `register_chart_renderers` in `src/fluxio/charts/<chart>.py`.
   - Terminal ANSI/Unicode renderer registered via `register_chart_renderers`.
3. **Documentation, Showcase Notebook & AI Context (Enforced by `tests/test_ai_docs.py`!)**
   - Create `docs/charts/<chart>.md` following the concise structure in `docs/charts/number.md` and register it under `Visualizations` in `mkdocs.yml`.
   - Create a pre-executed Jupyter notebook `examples/all_examples/<chart>.ipynb` showcasing all modes of the visualization (minimal 1-liner, styling/variants, subplot grid, live `f(t)` / generator dynamics, and `print(...)` terminal output).
   - Run `uv run python -m fluxio.ai_docs` to regenerate `llms.txt`, `llms-full.txt`, `fluxio.pyi`, and visual assets.
   - Check off the completed item in `TODO.md`.
4. **Tests**
   - Add unit & visual/pixel tests in `tests/` and `web/tests/`, then ensure `uv run pytest` and `corepack pnpm test` pass 100%.
