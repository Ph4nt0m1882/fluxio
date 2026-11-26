# Fluxio

**Fluxio** (`import fluxio as fx`) is a modern, lightweight, real-time visualization engine built on **Python + zero-dependency TypeScript `<canvas>`** (~28 KB bundle).

It allows a **single `Figure` object** to render seamlessly across desktop windows, Jupyter notebooks, ANSI TrueColor terminals, static/animated presentation exports, and embedded AI chatbot WebViews.

## Quickstart

```python
import fluxio as fx

fig = fx.Figure(rows=1, cols=2, title="System Overview", size=(900, 420))
fig.style(accent="#38bdf8", accent_side="left", radius=20)

fig[0, 0].number(42.5, unit="°C", precision=1, label="SoC Temp")
fig[0, 1].style(variant="reverse", accent="#059669", accent_side="right").number(
    99.95, unit="%", precision=2, label="Availability"
)

# 1. Interactive desktop window (zoom/pan, play/pause, PNG capture)
fx.show(fig)

# 2. Terminal ANSI TrueColor output (replaces plotext!)
print(fig)

# 3. Headless exports (no Chromium required)
fig.save("slide.png")
fig.save("standalone.html")
```

## Documentation Sections

- **[Styling & Themes](styling.md)**: Cascading `fig.style(...)` and `fig[row, col].style(...)`, `Gradient`, `BackgroundImage`, adaptive translucent veils, tapered crescent borders, and `classic` / `reverse` / `text` variants.
- **[Outputs & Exports](outputs.md)**: Desktop windows, persistent Jupyter cells, static & live terminal rendering (`print(fig)`, `fig.print()`), and multi-format exports (`PNG`, `SVG`, `GIF`, `MP4`, `HTML`, `TXT`).
- **[Charts — `number()`](charts/number.md)**: Static, time-function `f(t)`, and Python generator (`yield`) numeric KPI widgets.
- **[AI & LLM Integration](ai-integration.md)**: Token-efficient `llms.txt`, `llms-full.txt`, condensed `fluxio.pyi` type stubs, and runtime `fx.llm_context()`.
