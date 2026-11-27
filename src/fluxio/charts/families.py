"""Level-2 geometric family base classes (strictly 1 level below `Visual`, 1 level above concrete charts)."""

from __future__ import annotations
import math
from collections.abc import Mapping, Sequence
from typing import Any
from .base import Visual

SERIES_PALETTE = (
    "#38bdf8",
    "#f97316",
    "#34d399",
    "#a78bfa",
    "#f43f5e",
    "#eab308",
    "#06b6d4",
)


def pick_series_color(
    explicit_color: str | None,
    index: int,
    primary_accent: str,
) -> str:
    if explicit_color:
        return explicit_color
    if index == 0:
        return primary_accent
    filtered = [c for c in SERIES_PALETTE if c.lower() != primary_accent.lower()]
    return filtered[(index - 1) % len(filtered)] if filtered else primary_accent


def _nice_num(val_range: float, round_step: bool) -> float:
    if val_range <= 0 or not math.isfinite(val_range):
        return 1.0
    exponent = math.floor(math.log10(val_range))
    fraction = val_range / (10.0**exponent)
    if round_step:
        if fraction < 1.5:
            nice_f = 1.0
        elif fraction < 3.0:
            nice_f = 2.0
        elif fraction < 7.0:
            nice_f = 5.0
        else:
            nice_f = 10.0
    else:
        if fraction <= 1.0:
            nice_f = 1.0
        elif fraction <= 2.0:
            nice_f = 2.0
        elif fraction <= 5.0:
            nice_f = 5.0
        else:
            nice_f = 10.0
    return nice_f * (10.0**exponent)


def compute_nice_ticks(
    min_val: float, max_val: float, max_ticks: int = 5
) -> list[float]:
    lo, hi = float(min_val), float(max_val)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return [0.0, 1.0]
    if lo == hi:
        pad = 1.0 if lo == 0 else abs(lo) * 0.1
        lo -= pad
        hi += pad
    if lo > hi:
        lo, hi = hi, lo

    n_ticks = max(2, int(max_ticks))
    rng = _nice_num(hi - lo, False)
    step = _nice_num(rng / (n_ticks - 1), True)
    g_min = math.floor(lo / step) * step
    g_max = math.ceil(hi / step) * step

    ticks: list[float] = []
    v = g_min
    while v <= g_max + step * 0.5 and len(ticks) <= 20:
        clean = round(v, 10)
        ticks.append(0.0 if clean == 0 else clean)
        v += step
    return ticks


def compute_axis_ticks(
    min_val: float,
    max_val: float,
    max_ticks: int = 5,
    *,
    step: float | None = None,
    explicit_min: float | None = None,
) -> list[float]:
    """Compute either Wilkinson nice ticks or exact `step`-spaced grid/tick positions."""
    if step is None or step <= 0 or not math.isfinite(step):
        return compute_nice_ticks(min_val, max_val, max_ticks)

    lo, hi = (
        (float(min_val), float(max_val))
        if min_val <= max_val
        else (float(max_val), float(min_val))
    )
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return [0.0, 1.0]

    span = max(0.0, hi - lo)
    eff_step = float(step)
    if span / eff_step > 200.0:
        eff_step *= math.ceil((span / eff_step) / 100.0)

    eps = 1e-9 * eff_step
    if explicit_min is not None and math.isfinite(explicit_min):
        start = float(explicit_min)
        if start < lo - eps:
            start += math.ceil((lo - start - eps) / eff_step) * eff_step
    else:
        start = math.ceil((lo - eps) / eff_step) * eff_step

    ticks: list[float] = []
    k = 0
    while k <= 250:
        v = start + k * eff_step
        if v > hi + eps:
            break
        clean = round(v, 10)
        ticks.append(0.0 if clean == 0 else clean)
        k += 1
    return ticks if ticks else [round(lo, 10), round(hi, 10)]


def normalize_axis_limits(
    lim: Sequence[float | None] | None,
    v_min: float | None,
    v_max: float | None,
    v_step: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Normalize `(min, max[, step])` tuple + explicit `min`/`max`/`step` kwargs."""
    lo: float | None = None
    hi: float | None = None
    st: float | None = None
    if lim is not None:
        if len(lim) < 2:
            raise ValueError("Axis limit tuple (xlim/ylim) must have 2 or 3 elements.")
        if lim[0] is not None:
            lo = float(lim[0])
        if lim[1] is not None:
            hi = float(lim[1])
        if len(lim) >= 3 and lim[2] is not None:
            st = float(lim[2])

    if v_min is not None:
        lo = float(v_min)
    if v_max is not None:
        hi = float(v_max)
    if v_step is not None:
        st = float(v_step)

    if st is not None and (not math.isfinite(st) or st <= 0.0):
        raise ValueError(f"Axis step must be > 0 (got {st!r}).")
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return (lo, hi, st)


def format_tick_number(v: float) -> str:
    av = abs(v)
    if av == 0:
        return "0"
    if av >= 1e5 or av < 1e-3:
        return f"{v:.1e}"
    if float(v).is_integer():
        return str(int(round(v)))
    decimals = 3 if av < 1 else (2 if av < 10 else 1)
    return f"{v:.{decimals}f}".rstrip("0").rstrip(".")


def compute_axis2d_bounds(
    series_list: Sequence[Mapping[str, Any]],
    xlim: Sequence[float | None] | None = None,
    ylim: Sequence[float | None] | None = None,
    *,
    xmin: float | None = None,
    xmax: float | None = None,
    ymin: float | None = None,
    ymax: float | None = None,
) -> tuple[float, float, float, float]:
    eff_xmin = (
        float(xmin)
        if xmin is not None
        else (float(xlim[0]) if xlim and len(xlim) >= 2 and xlim[0] is not None else None)
    )
    eff_xmax = (
        float(xmax)
        if xmax is not None
        else (float(xlim[1]) if xlim and len(xlim) >= 2 and xlim[1] is not None else None)
    )
    eff_ymin = (
        float(ymin)
        if ymin is not None
        else (float(ylim[0]) if ylim and len(ylim) >= 2 and ylim[0] is not None else None)
    )
    eff_ymax = (
        float(ymax)
        if ymax is not None
        else (float(ylim[1]) if ylim and len(ylim) >= 2 and ylim[1] is not None else None)
    )

    x_min, x_max = math.inf, -math.inf
    y_min, y_max = math.inf, -math.inf

    for s in series_list:
        xs = s.get("x", ())
        ys = s.get("y", ())
        for xv, yv in zip(xs, ys):
            fx_v, fy_v = float(xv), float(yv)
            if math.isfinite(fx_v) and math.isfinite(fy_v):
                x_min = min(x_min, fx_v)
                x_max = max(x_max, fx_v)
                y_min = min(y_min, fy_v)
                y_max = max(y_max, fy_v)

    if not (math.isfinite(x_min) and math.isfinite(x_max)):
        x_min, x_max = 0.0, 1.0
    if not (math.isfinite(y_min) and math.isfinite(y_max)):
        y_min, y_max = 0.0, 1.0

    # Resolve X bounds
    out_xmin = eff_xmin if eff_xmin is not None else x_min
    out_xmax = eff_xmax if eff_xmax is not None else x_max
    if out_xmin > out_xmax:
        out_xmin, out_xmax = out_xmax, out_xmin
    if out_xmin == out_xmax:
        if eff_xmin is not None and eff_xmax is None:
            out_xmax = out_xmin + 1.0
        elif eff_xmax is not None and eff_xmin is None:
            out_xmin = out_xmax - 1.0
        else:
            out_xmin -= 0.5
            out_xmax += 0.5

    # Resolve Y bounds (adding 6% headroom ONLY on open auto-scaled side(s)!)
    if y_min == y_max:
        d_y = 1.0 if y_min == 0 else abs(y_min) * 0.1
        auto_ymin, auto_ymax = y_min - d_y, y_max + d_y
    else:
        pad_y = (y_max - y_min) * 0.06
        auto_ymin, auto_ymax = y_min - pad_y, y_max + pad_y

    out_ymin = eff_ymin if eff_ymin is not None else auto_ymin
    out_ymax = eff_ymax if eff_ymax is not None else auto_ymax
    if out_ymin > out_ymax:
        out_ymin, out_ymax = out_ymax, out_ymin
    if out_ymin == out_ymax:
        out_ymax = out_ymin + 1.0

    return (out_xmin, out_xmax, out_ymin, out_ymax)


def format_number_value(
    value: float,
    precision: int | None = None,
    prefix: str = "",
) -> str:
    """Format a numeric value consistently across Python and TypeScript."""
    if precision is not None and precision >= 0:
        num_str = f"{value:.{precision}f}"
    elif float(value).is_integer():
        num_str = str(int(value))
    else:
        num_str = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{prefix}{num_str}"


class Indicator(Visual):
    """Level-2 family for KPI indicators (`Number`, `Stat`, `Gauge`, `BarGauge`)."""

    def __init__(
        self,
        *,
        unit: str = "",
        prefix: str = "",
        precision: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.unit = unit
        self.prefix = prefix
        self.precision = precision

    def format_value(self, value: float) -> str:
        return format_number_value(value, self.precision, self.prefix)


def normalize_legend_pos(legend: bool | str | None) -> str:
    """Normalize `legend` (`True`, `False`, `'top'`, `'bottom'`, `'none'`) to `'top' | 'bottom' | 'none'`."""
    if legend is False or legend is None:
        return "none" if legend is False else "top"
    if legend is True:
        return "top"
    if isinstance(legend, str):
        low = legend.strip().lower()
        if low in ("top", "bottom", "none"):
            return low
    raise ValueError(
        f"Invalid legend={legend!r}. Expected True, False, 'top', 'bottom', or 'none'."
    )


class Axis2D(Visual):
    """Level-2 family for 1D/2D Cartesian axis charts (`Plot`, `Scatter`, `Bar`, `Hist`, `Boxplot`...)."""

    def __init__(
        self,
        *,
        xlabel: str = "",
        ylabel: str = "",
        xscale: str = "linear",
        yscale: str = "linear",
        xlim: Sequence[float | None] | None = None,
        ylim: Sequence[float | None] | None = None,
        xmin: float | None = None,
        xmax: float | None = None,
        xstep: float | None = None,
        ymin: float | None = None,
        ymax: float | None = None,
        ystep: float | None = None,
        grid: bool = True,
        legend: bool | str = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.xscale = xscale
        self.yscale = yscale
        self.xmin, self.xmax, self.xstep = normalize_axis_limits(
            xlim, xmin, xmax, xstep
        )
        self.ymin, self.ymax, self.ystep = normalize_axis_limits(
            ylim, ymin, ymax, ystep
        )
        self.grid = grid
        self.legend = normalize_legend_pos(legend)

    @property
    def xlim(self) -> tuple[float, float] | None:
        if self.xmin is not None and self.xmax is not None:
            return (self.xmin, self.xmax)
        return None

    @property
    def ylim(self) -> tuple[float, float] | None:
        if self.ymin is not None and self.ymax is not None:
            return (self.ymin, self.ymax)
        return None


class Field2D(Visual):
    """Level-2 family for 2D matrices, meshes, contours & vector fields (`Imshow`, `Contour`, `Quiver`...)."""

    def __init__(
        self,
        *,
        cmap: str = "viridis",
        colorbar: bool = True,
        vmin: float | None = None,
        vmax: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.cmap = cmap
        self.colorbar = colorbar
        self.vmin = vmin
        self.vmax = vmax


class Polar2D(Visual):
    """Level-2 family for angular / radial / circular charts (`Polar`, `Pie`...)."""

    def __init__(
        self,
        *,
        start_angle: float = 90.0,
        clockwise: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.start_angle = float(start_angle)
        self.clockwise = bool(clockwise)


class Space3D(Visual):
    """Level-2 family for 3D projected visualizations (`Plot3D`, `Scatter3D`, `Surface3D`, `Voxels`...)."""

    def __init__(
        self,
        *,
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 28.0,
        azim: float = -55.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.zlabel = zlabel
        self.elev = float(elev)
        self.azim = float(azim)


class Scene(Visual):
    """Level-2 family for topologies, profiling, interactive explainers, and 2D/3D simulations."""

    def __init__(
        self,
        *,
        interactive_controls: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.interactive_controls = (
            dict(interactive_controls) if interactive_controls else {}
        )
