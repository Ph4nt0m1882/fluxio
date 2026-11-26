# `number()` — Numeric KPI & Live Value Card

Displays a single numeric metric (static value, continuous function of time `f(t)`, or Python generator `yield`) inside a `Figure` grid cell.

## Signature

```python
fig.number(
    value: int | float | Callable[[float], int | float] | Iterator[int | float],
    *,
    label: str = "",
    unit: str = "",
    prefix: str = "",
    precision: int | None = None,
    color: str | None = None,
    description: str = "",
    row: int | None = None,
    col: int | None = None,
    row_span: int = 1,
    col_span: int = 1,
) -> NumberCell
```

Can also be called via Matplotlib-like grid indexing: `fig[row, col].number(...)`.

## Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `value` | `int \| float \| Callable \| Iterator` | *required* | Static number, `fn(t_seconds)` callable, or Python generator yielding numbers. |
| `label` | `str` | `""` | Header title displayed at the top-left of the card. |
| `unit` | `str` | `""` | Unit suffix displayed next to the number (e.g. `"°C"`, `"%"`, `"ms"`). |
| `prefix` | `str` | `""` | Prefix prepended before digits (e.g. `"€"`, `"$"`). |
| `precision` | `int \| None` | `None` | Fixed decimal places (`None` auto-formats integers vs floats). |
| `color` | `str \| None` | `None` | Shorthand hex color override for this cell's accent and value. |
| `description` | `str` | `""` | Subtitle/context note displayed at the bottom of the card. |
| `row`, `col` | `int \| None` | `None` | 0-based grid coordinates (auto-placed in next free slot if omitted). |
| `row_span`, `col_span` | `int` | `1` | Number of grid rows/columns spanned by this cell. |

## Examples

### Minimal Static Number

```python
import fluxio as fx

fig = fx.Figure(title="CPU Telemetry")
fig.number(42.5, unit="°C", precision=1, label="Core Temperature")
fx.show(fig)
```

### Multi-Cell Grid with Dynamic Function, Generator & Variants

```python
import itertools
import math
import fluxio as fx

fig = fx.Figure(rows=2, cols=2, title="Live System Metrics", fps=24)
fig.style(
    background=fx.Gradient(["#090d16", "#1e1b4b"], angle=135),
    accent_side="left",
    radius=20,
)

# Top row spanning 2 columns: function of elapsed time `t` (seconds)
fig.number(
    lambda t: 65.0 + 18.0 * math.sin(t * 2.0),
    unit="%",
    precision=1,
    label="Cluster Load",
    row=0,
    col=0,
    col_span=2,
)

# Bottom-left: classic translucent card
fig[1, 0].style(accent="#34d399").number(43.2, unit="°C", precision=1, label="SoC Temp")

# Bottom-right: solid reverse card driven by a Python generator
fig[1, 1].style(variant="reverse", accent="#ea580c", accent_side="right").number(
    (i * 12 for i in itertools.count(1)),
    unit="pkt",
    precision=0,
    label="Packet Stream",
)

fx.show(fig)
```
