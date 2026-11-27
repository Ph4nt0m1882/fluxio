# Architecture & 3-Level OOP Hierarchy

This section covers the non-visual engineering backbone of Fluxio: how containers, class inheritance, real-time streaming, and multi-target renderers fit together.

## 1. Hybrid Container + Standalone Objects

Every visualization in Fluxio can be instantiated and rendered **in two equivalent ways**:

1. **Standalone Object** — Every chart inherits from `fx.Visual`, giving it built-in `.style(...)`, `.show()`, `.save(...)`, `.print()`, `print(v)`, and Jupyter `_repr_html_()`:
   ```python
   import fluxio as fx

   p = fx.Plot([10, 25, 18, 32], label="Throughput", title="API Traffic")
   p.style(accent="#34d399", accent_side="left")
   p.save("traffic.png")
   ```
2. **Multi-Cell `Figure` Grid** — Compose heterogeneous charts side-by-side using Matplotlib-style `(row, col)` indexing or builder methods:
   ```python
   fig = fx.Figure(rows=1, cols=2, title="System Dashboard")
   fig[0, 0] = fx.Number(42.5, unit="°C", label="SoC Temp")
   fig[0, 1].plot([10, 25, 18, 32], label="Throughput")
   fx.show(fig)
   ```

---

## 2. Strict 3-Level Inheritance Tree

To keep the codebase modular across 50+ chart types without deep inheritance chains, Fluxio enforces **at most 3 class levels** (`1 concrete chart = 1 dedicated module`):

```text
Visual (Level 1 — style, dynamic lifecycle, standalone show/save/print/Jupyter)
├── Indicator (Level 2 — numeric formatting, units, prefixes)
│   └── Number (Level 3 — src/fluxio/charts/number.py)
├── Axis2D (Level 2 — X/Y bounds, nice ticks, gridlines, labels, Braille canvas)
│   └── Plot (Level 3 — src/fluxio/charts/plot.py)
├── Field2D (Level 2 — 2D matrices, meshes, colormaps, colorbars)
├── Polar2D (Level 2 — radial & angular coordinates)
├── Space3D (Level 2 — 3D camera elevation/azimuth & projection)
└── Scene (Level 2 — node graphs, flame graphs, interactive explainers, simulations)
```

---

## 3. Declarative Scene Protocol & 3 Synchronized Renderers

Python never embeds brittle HTML/JS strings directly per chart. Instead, `Figure.to_spec()` emits a pure **JSON Scene Specification** consumed by three lightweight engines:

| Engine | Implementation | Target Environments |
| :--- | :--- | :--- |
| **Canvas 2D Viewer** | Zero-dependency TypeScript (`web/src/`, ~38 KB minified) | `fx.show()` (`pywebview` / `--app` browser), Jupyter inline cells, standalone `.html`, Flutter/Web chatbots |
| **Headless 2D & Vector** | Pure Python (`Pillow` 2x supersampled + `SVG` + `ffmpeg` pipe) | `.png`, `.svg`, `.gif`, `.mp4`, `.webm` (runs in ms on Raspberry Pi with zero Chromium!) |
| **Terminal TUI** | Pure Python ANSI 24-bit TrueColor + Unicode Block & Braille (`2x4` subpixels) | `print(fig)`, `fig.print()` live loop, `.txt`, `.ans` |

---

## 4. Real-Time Streaming Protocol (WebSocket)

When `fx.show(fig)` opens a figure containing dynamic `Callable[[float], ...]` or Python generator (`yield`) sources, `FluxioLiveServer` runs an `asyncio` HTTP + WebSocket loop on `127.0.0.1`:

- **`snapshot`**: Sent on initial connection with the full `FigureSpec`.
- **`tick`**: Streams incremental `{ id, value, formatted }` or `{ id, series_data }` deltas at `fig.fps`.
- **`control`**: Bidirectional toolbar commands (`play`, `pause`, `reset`) sent from the viewer back to Python.
