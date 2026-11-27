# `Plot` / `fig.plot()` — 2D Line & Time-Series Chart

Draws one or more 1D/2D continuous or discrete curves on a modern `Axis2D` coordinate system.

Inherits from **`Axis2D` -> `Visual`** (3-level hierarchy): works both **standalone** (`fx.Plot(...).show()`) and **inside a multi-cell `Figure`** (`fig.plot(...)`, `fig[r, c].plot(...)`, or `fig[r, c] = fx.Plot(...)`). Calling `.plot(...)` multiple times on the same `Plot` or `(row, col)` cell **superposes multiple curves** with automatic palette cycling and legend.

---

## Signatures

```python
# 1. Standalone or assignable object
p = fx.Plot(
    x_or_y: Any = None,
    y: Any = None,
    *,
    label: str = "",
    color: str | None = None,
    linewidth: float = 2.4,
    linestyle: str = "solid",        # "solid" | "dashed" | "dotted"
    marker: str | None = None,       # None | "circle" | "dot"
    fill_alpha: float = 0.12,        # Subtle Grafana-style gradient under curve (0.0 to disable)
    max_points: int = 120,           # Rolling window size for streaming scalar generators/callables
    card_title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
    grid: bool = True,
    legend: bool = True,
    title: str = "",
    subtitle: str = "",
    theme: str = "dark",
    size: tuple[int, int] = (840, 460),
)

# 2. Directly on a Figure or SubplotSlot (superposes if called multiple times on the same cell!)
fig.plot(x_or_y, y=None, *, label="", color=None, linewidth=2.4, linestyle="solid", marker=None, fill_alpha=0.12, xlabel="", ylabel="", row=None, col=None) -> Plot
```

## Parameters & Specificities

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `x_or_y`, `y` | `Sequence \| Callable \| Iterator` | — | Pass `(x, y)` sequences, a single `y` sequence (`x = 0..n-1`), a `fn(t)` callable, or a Python generator (`yield`). |
| `label` | `str` | `""` | Series name displayed in the top-right legend and magnetic hover tooltip. |
| `card_title` | `str` | `""` | Optional header title inside the top-left of the cell card (distinct from `label`, which names the curve). |
| `color` | `str \| None` | `None` | Hex color for this curve (cycles automatically through Fluxio's high-contrast palette if omitted). |
| `linewidth` | `float` | `2.4` | Stroke thickness in pixels. |
| `linestyle` | `str` | `"solid"` | `"solid"`, `"dashed"`, or `"dotted"`. |
| `marker` | `str \| None` | `None` | Optional point marker: `None` (clean line), `"circle"` (ring with dark center), or `"dot"` (filled circle). |
| `fill` | `bool \| None` | `None` | Shorthand toggle for the area glow (`fill=False` sets `fill_alpha=0.0`; `fill=True` enables area fill). |
| `fill_alpha` | `float` | `0.12` | Vertical gradient fill opacity from the curve down to the `0` baseline (`0.0` for plain Matplotlib-like stroke). |
| `max_points` | `int` | `120` | Sliding ring-buffer length when `x_or_y` yields or returns streaming scalar points. |
| `xlabel`, `ylabel` | `str` | `""` | Horizontal and rotated (`-90°`) vertical axis titles. |
| `xmin`, `xmax` | `float \| None` | `None` | Explicit horizontal lower and/or upper bound (supports partial locking, e.g. `xmin=0` with auto `xmax`). |
| `ymin`, `ymax` | `float \| None` | `None` | Explicit vertical lower and/or upper bound (e.g. `ymin=0` pins the floor at `0` while auto-scaling the ceiling). |
| `xstep`, `ystep` | `float \| None` | `None` | Exact gridline & tick spacing along X and Y (e.g. `xmin=0, xmax=10, xstep=2` draws grid columns at `0, 2, 4, 6, 8, 10`). |
| `xlim`, `ylim` | `tuple \| None` | `None` | Shorthand `(min, max)` or 3-tuple `(min, max, step)` (e.g. `xlim=(0, 10, 2)`). |
| `legend` | `bool \| str` | `True` | `"top"` / `True` (dedicated wrapped line right under the bold card title), `"bottom"` (below `xlabel`, Grafana-style), or `False` / `"none"`. |

!!! info "Two Automatic Real-Time Modes"
    `Plot` inspects what your `Callable[[float], ...]` or Python generator returns:

    1. **Scalar `y` or `(x, y)` point** → **Rolling Time-Series Mode** (like Grafana): appends each new sample and keeps the latest `max_points` points.
    2. **Sequence `ys` or `(xs, ys)`** → **Animated Waveform Mode**: replaces the entire curve on each frame (ideal for physics waves, FFT spectra, or moving profiles).

---

## Examples

=== "1. Minimal"

    ```python
    import fluxio as fx

    fx.Plot([12, 28, 19, 37, 31, 46]).show()
    ```

    === "2. Multi-Series & Markers"

    ```python
    import math
    import fluxio as fx

    xs = [round(i * 0.2, 2) for i in range(36)]
    p = fx.Plot(
        xs,
        [75.0 * math.exp(-0.22 * x) + 20.0 for x in xs],
        label="Model",
        xlabel="Time (s)",
        ylabel="Temp (°C)",
        title="Plot — Multi-Series & Area Glow",
    )
    p.plot(
        xs,
        [75.0 * math.exp(-0.22 * x) + 20.0 + 9.0 * math.sin(x * 2.4) for x in xs],
        label="Sensor",
        color="#f97316",
        linestyle="dashed",
        marker="circle",
        fill_alpha=0.05,
    )
    p.show()
    ```

    === "3. Animated `.gif` (Wave & Rolling Stream)"

    ```python
    import math
    import fluxio as fx

    xs = [i * 0.16 for i in range(42)]
    p = fx.Plot(
        lambda t: (
            xs,
            [math.sin(x - 2.0 * math.pi * t / 2.0) * math.cos(x * 0.28) for x in xs],
        ),
        label="Wave Mode",
        xlabel="Position (m)",
        ylabel="Displacement",
        ylim=(-1.15, 1.15),
        title="Travelling Wave Packet",
        size=(760, 380),
        fps=16,
    )
    p.plot(
        lambda t: (
            xs,
            [0.55 * math.cos(x * 1.3 + 2.0 * math.pi * t / 2.0) for x in xs],
        ),
        label="Counter-Wave",
        color="#f97316",
        linestyle="dashed",
        fill_alpha=0.04,
    )

    p.save("plot_anim.gif", duration=2.0, fps=16)
    ```

    === "4. Terminal Braille (`print`)"

    ```python
    import math
    import fluxio as fx

    xs = [i * 0.25 for i in range(28)]
    p = fx.Plot(xs, [math.sin(x) for x in xs], label="sin(x)", xlabel="x")
    p.plot(xs, [math.cos(x) for x in xs], label="cos(x)", linestyle="dashed", color="#f97316")
    print(p)    # High-resolution 2x4 Unicode Braille + ANSI TrueColor!
    ```
