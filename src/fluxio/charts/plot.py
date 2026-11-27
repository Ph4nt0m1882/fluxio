"""Level-3 `Plot` Cartesian 2D line chart (`Visual` -> `Axis2D` -> `Plot`) and its 3 renderers."""

from __future__ import annotations
import html
import math
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from PIL import Image, ImageDraw
from ..theme import MONOSPACE_STACK, resolve_cell_style
from .base import register_chart_renderers
from .braille import BrailleCanvas, _ansi_fg
from .families import (
    Axis2D,
    compute_axis2d_bounds,
    compute_axis_ticks,
    format_tick_number,
    normalize_axis_limits,
    normalize_legend_pos,
    pick_series_color,
)

VALID_LINESTYLES = ("solid", "dashed", "dotted")
VALID_MARKERS = (None, "circle", "dot")


def _is_scalar_number(obj: Any) -> bool:
    return isinstance(obj, (int, float)) and not isinstance(obj, bool)


def _to_float_list(seq: Any) -> list[float]:
    if hasattr(seq, "tolist"):
        seq = seq.tolist()
    return [float(v) for v in seq]


@dataclass
class _PlotSeries:
    """Internal representation of one curve series inside a `Plot` cell."""

    x_or_source: Any
    y_opt: Any = None
    label: str = ""
    color: str | None = None
    linewidth: float = 2.4
    linestyle: str = "solid"
    marker: str | None = None
    fill_alpha: float = 0.12
    max_points: int = 120

    _static_x: list[float] = field(default_factory=list, init=False, repr=False)
    _static_y: list[float] = field(default_factory=list, init=False, repr=False)
    _is_callable: bool = field(default=False, init=False, repr=False)
    _is_iterator: bool = field(default=False, init=False, repr=False)

    # History caches for deterministic frame sampling & rolling windows
    _iter_items: list[Any] = field(default_factory=list, init=False, repr=False)
    _iter_exhausted: bool = field(default=False, init=False, repr=False)
    _step_cursor: int = field(default=0, init=False, repr=False)
    _callable_rolling_pts: list[tuple[float, float]] = field(
        default_factory=list, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.linestyle not in VALID_LINESTYLES:
            raise ValueError(
                f"Invalid linestyle '{self.linestyle}'. Expected one of: {', '.join(VALID_LINESTYLES)}"
            )
        if self.marker not in VALID_MARKERS:
            raise ValueError("Invalid marker. Expected None, 'circle', or 'dot'.")
        self.max_points = max(2, int(self.max_points))

        if self.y_opt is not None:
            # Explicit (x, y) static sequences
            self._static_x = _to_float_list(self.x_or_source)
            self._static_y = _to_float_list(self.y_opt)
            if len(self._static_x) != len(self._static_y):
                raise ValueError(
                    f"Plot x and y must have identical lengths (got {len(self._static_x)} vs {len(self._static_y)})."
                )
        elif callable(self.x_or_source):
            self._is_callable = True
        elif isinstance(self.x_or_source, Iterator):
            self._is_iterator = True
        elif isinstance(self.x_or_source, Iterable):
            self._static_y = _to_float_list(self.x_or_source)
            self._static_x = [float(i) for i in range(len(self._static_y))]
        else:
            raise TypeError(
                "Plot expects (x, y) sequences, a single y sequence, a callable f(t), or a Python generator."
            )

    @property
    def is_dynamic(self) -> bool:
        return self._is_callable or self._is_iterator

    def reset_cursor(self) -> None:
        self._step_cursor = 0
        self._callable_rolling_pts.clear()

    @staticmethod
    def _unpack_curve_value(
        val: Any,
        default_x_val: float,
    ) -> tuple[str, Any]:
        """Classify dynamic return into ('point', (x, y)) or ('curve', (xs, ys))."""
        if _is_scalar_number(val):
            return ("point", (float(default_x_val), float(val)))
        if isinstance(val, tuple) and len(val) == 2:
            a, b = val
            if _is_scalar_number(a) and _is_scalar_number(b):
                return ("point", (float(a), float(b)))
            return ("curve", (_to_float_list(a), _to_float_list(b)))
        ys = _to_float_list(val)
        xs = [float(i) for i in range(len(ys))]
        return ("curve", (xs, ys))

    def _pull_iter_up_to(self, index: int) -> None:
        assert isinstance(self.x_or_source, Iterator)
        while len(self._iter_items) <= index and not self._iter_exhausted:
            try:
                self._iter_items.append(next(self.x_or_source))
            except StopIteration:
                self._iter_exhausted = True
                break

    def evaluate_xy(
        self,
        t: float,
        step_index: int | None = None,
    ) -> tuple[list[float], list[float]]:
        if not self.is_dynamic:
            return (list(self._static_x), list(self._static_y))

        if self._is_callable:
            fn = self.x_or_source
            assert callable(fn)
            raw = fn(float(t))
            mode, payload = self._unpack_curve_value(raw, float(t))
            if mode == "curve":
                return payload
            pt_x, pt_y = payload
            if (
                not self._callable_rolling_pts
                or pt_x >= self._callable_rolling_pts[-1][0]
            ):
                if (
                    not self._callable_rolling_pts
                    or self._callable_rolling_pts[-1][0] != pt_x
                ):
                    self._callable_rolling_pts.append((pt_x, pt_y))
                else:
                    self._callable_rolling_pts[-1] = (pt_x, pt_y)
            else:
                # Time reset / non-monotonic sample -> restart rolling window cleanly
                self._callable_rolling_pts = [(pt_x, pt_y)]

            window = self._callable_rolling_pts[-self.max_points :]
            return ([p[0] for p in window], [p[1] for p in window])

        # Iterator / Python generator
        if step_index is None:
            idx = self._step_cursor
            self._step_cursor += 1
        else:
            idx = max(0, int(step_index))

        self._pull_iter_up_to(idx)
        if not self._iter_items:
            return ([], [])

        upto = min(idx, len(self._iter_items) - 1)
        last_item = self._iter_items[upto]
        mode, payload = self._unpack_curve_value(last_item, float(upto))
        if mode == "curve":
            return payload

        start_i = max(0, upto + 1 - self.max_points)
        xs_out: list[float] = []
        ys_out: list[float] = []
        for k in range(start_i, upto + 1):
            _, pt = self._unpack_curve_value(self._iter_items[k], float(k))
            xs_out.append(pt[0])
            ys_out.append(pt[1])
        return (xs_out, ys_out)


class Plot(Axis2D):
    """2D Cartesian line chart (`Visual` -> `Axis2D` -> `Plot`) supporting multi-series superposition."""

    kind = "plot"

    def __init__(
        self,
        x_or_y: Any = None,
        y: Any = None,
        *,
        label: str = "",
        color: str | None = None,
        linewidth: float = 2.4,
        linestyle: str = "solid",
        marker: str | None = None,
        fill: bool | None = None,
        fill_alpha: float = 0.12,
        max_points: int = 120,
        card_title: str = "",
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
        description: str = "",
        title: str = "",
        subtitle: str = "",
        theme: str = "dark",
        style: Mapping[str, Any] | None = None,
        size: tuple[int, int] = (840, 460),
        fps: int = 60,
        toolbar: bool | dict[str, bool] = True,
        row: int = 0,
        col: int = 0,
        row_span: int = 1,
        col_span: int = 1,
    ) -> None:
        super().__init__(
            xlabel=xlabel,
            ylabel=ylabel,
            xscale=xscale,
            yscale=yscale,
            xlim=xlim,
            ylim=ylim,
            xmin=xmin,
            xmax=xmax,
            xstep=xstep,
            ymin=ymin,
            ymax=ymax,
            ystep=ystep,
            grid=grid,
            legend=legend,
            label=card_title,
            description=description,
            color=color,
            title=title,
            subtitle=subtitle,
            theme=theme,
            style=style,
            size=size,
            fps=fps,
            toolbar=toolbar,
            row=row,
            col=col,
            row_span=row_span,
            col_span=col_span,
        )
        self._series: list[_PlotSeries] = []
        if x_or_y is not None:
            self.plot(
                x_or_y,
                y,
                label=label,
                color=color,
                linewidth=linewidth,
                linestyle=linestyle,
                marker=marker,
                fill=fill,
                fill_alpha=fill_alpha,
                max_points=max_points,
            )

    def plot(
        self,
        x_or_y: Any,
        y: Any = None,
        *,
        label: str = "",
        color: str | None = None,
        linewidth: float = 2.4,
        linestyle: str = "solid",
        marker: str | None = None,
        fill: bool | None = None,
        fill_alpha: float = 0.12,
        max_points: int = 120,
        xlabel: str | None = None,
        ylabel: str | None = None,
        card_title: str | None = None,
        xlim: Sequence[float | None] | None = None,
        ylim: Sequence[float | None] | None = None,
        xmin: float | None = None,
        xmax: float | None = None,
        xstep: float | None = None,
        ymin: float | None = None,
        ymax: float | None = None,
        ystep: float | None = None,
        legend: bool | str | None = None,
    ) -> Plot:
        """Superpose an additional curve series onto this `Plot` (chainable)."""
        if xlabel is not None:
            self.xlabel = xlabel
        if ylabel is not None:
            self.ylabel = ylabel
        if card_title is not None:
            self.label = card_title
        if any(v is not None for v in (xlim, xmin, xmax, xstep)):
            nx0, nx1, nxs = normalize_axis_limits(xlim, xmin, xmax, xstep)
            if nx0 is not None:
                self.xmin = nx0
            if nx1 is not None:
                self.xmax = nx1
            if nxs is not None:
                self.xstep = nxs
        if any(v is not None for v in (ylim, ymin, ymax, ystep)):
            ny0, ny1, nys = normalize_axis_limits(ylim, ymin, ymax, ystep)
            if ny0 is not None:
                self.ymin = ny0
            if ny1 is not None:
                self.ymax = ny1
            if nys is not None:
                self.ystep = nys
        if legend is not None:
            self.legend = normalize_legend_pos(legend)

        eff_fill = (
            0.0
            if fill is False
            else (
                max(0.16, float(fill_alpha))
                if fill is True
                else float(fill_alpha)
            )
        )
        self._series.append(
            _PlotSeries(
                x_or_source=x_or_y,
                y_opt=y,
                label=label,
                color=color,
                linewidth=float(linewidth),
                linestyle=linestyle,
                marker=marker,
                fill_alpha=eff_fill,
                max_points=max_points,
            )
        )
        return self

    @property
    def is_dynamic(self) -> bool:
        return any(s.is_dynamic for s in self._series)

    def reset_cursor(self) -> None:
        for s in self._series:
            s.reset_cursor()

    def evaluate_tick_update(
        self,
        t: float,
        step_index: int | None = None,
    ) -> dict[str, Any]:
        series_data: list[dict[str, list[float]]] = []
        for s in self._series:
            xs, ys = s.evaluate_xy(t, step_index=step_index)
            series_data.append({"x": xs, "y": ys})
        return {"id": self.id, "series_data": series_data}

    def to_dict(
        self,
        *,
        theme_dict: Mapping[str, Any],
        t: float = 0.0,
        step_index: int | None = 0,
        bake_duration: float | None = None,
        fps: int = 30,
    ) -> dict[str, Any]:
        resolved = resolve_cell_style(theme_dict, self._style_overrides, self.color)
        series_specs: list[dict[str, Any]] = []

        for s in self._series:
            frames: list[dict[str, list[float]]] | None = None
            if bake_duration is not None and s.is_dynamic:
                s.reset_cursor()
                n_frames = max(1, int(round(bake_duration * fps)))
                frames = []
                for i in range(n_frames):
                    fx_s, fy_s = s.evaluate_xy(i / fps, step_index=i)
                    frames.append({"x": fx_s, "y": fy_s})
                xs, ys = frames[0]["x"], frames[0]["y"]
            else:
                xs, ys = s.evaluate_xy(t, step_index=step_index)

            series_specs.append(
                {
                    "label": s.label,
                    "x": xs,
                    "y": ys,
                    "color": s.color,
                    "linewidth": s.linewidth,
                    "linestyle": s.linestyle,
                    "marker": s.marker,
                    "fill_alpha": s.fill_alpha,
                    "frames": frames,
                }
            )

        return {
            "id": self.id,
            "row": self.row,
            "col": self.col,
            "row_span": self.row_span,
            "col_span": self.col_span,
            "kind": self.kind,
            "label": self.label,
            "xlabel": self.xlabel,
            "ylabel": self.ylabel,
            "xscale": self.xscale,
            "yscale": self.yscale,
            "xlim": list(self.xlim) if self.xlim else None,
            "ylim": list(self.ylim) if self.ylim else None,
            "xmin": self.xmin,
            "xmax": self.xmax,
            "xstep": self.xstep,
            "ymin": self.ymin,
            "ymax": self.ymax,
            "ystep": self.ystep,
            "grid": self.grid,
            "legend": self.legend,
            "color": self.color,
            "style": dict(self._style_overrides) if self._style_overrides else None,
            "resolved_style": resolved,
            "description": self.description,
            "dynamic": self.is_dynamic,
            "series": series_specs,
        }


# --- Modular Renderers for `kind == "plot"` ---


def _draw_dashed_polyline_pillow(
    draw: ImageDraw.ImageDraw,
    pts: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: int,
    linestyle: str,
    s: float,
) -> None:
    if len(pts) < 2:
        return
    if linestyle == "solid":
        draw.line(pts, fill=color, width=width, joint="curve")
        return

    dash_len = (7.0 if linestyle == "dashed" else 2.2) * s
    gap_len = (5.0 if linestyle == "dashed" else 4.0) * s
    cycle = dash_len + gap_len
    dist_acc = 0.0

    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len < 1e-6:
            continue
        ux, uy = (x1 - x0) / seg_len, (y1 - y0) / seg_len
        pos = 0.0
        while pos < seg_len - 1e-6:
            phase = (dist_acc + pos) % cycle
            if phase < dash_len - 1e-6:
                step = min(dash_len - phase, seg_len - pos)
                if step > 1e-4:
                    sx0, sy0 = x0 + ux * pos, y0 + uy * pos
                    sx1, sy1 = x0 + ux * (pos + step), y0 + uy * (pos + step)
                    draw.line([(sx0, sy0), (sx1, sy1)], fill=color, width=width)
                pos += max(step, 1e-4)
            else:
                rem_gap = cycle - phase if (cycle - phase) > 1e-6 else gap_len
                pos += max(min(rem_gap, seg_len - pos), 1e-4)
        dist_acc += seg_len


def _pack_legend_rows(
    series_list: list[dict[str, Any]],
    cs: dict[str, Any],
    is_rev: bool,
    avail_w: float,
    measure_label: Callable[[str], float],
    swatch_plus_gap: float,
    item_gap: float,
) -> list[list[tuple[str, str, str, float]]]:
    """Wrap `(label, color_hex, linestyle, item_w)` items across rows without overflowing `avail_w`."""
    rows: list[list[tuple[str, str, str, float]]] = []
    cur_row: list[tuple[str, str, str, float]] = []
    cur_w = 0.0
    max_w = max(60.0, avail_w)

    for idx, sr in enumerate(series_list):
        s_lbl = str(sr.get("label", "")).strip()
        if not s_lbl:
            continue
        s_col = (
            str(cs["reverse_ink"])
            if (is_rev and idx == 0 and not sr.get("color"))
            else pick_series_color(sr.get("color"), idx, str(cs["accent"]))
        )
        ls = str(sr.get("linestyle", "solid"))
        item_w = swatch_plus_gap + measure_label(s_lbl)
        needed = item_w if not cur_row else (item_gap + item_w)
        if cur_row and (cur_w + needed) > max_w:
            rows.append(cur_row)
            cur_row = [(s_lbl, s_col, ls, item_w)]
            cur_w = item_w
        else:
            cur_row.append((s_lbl, s_col, ls, item_w))
            cur_w += needed

    if cur_row:
        rows.append(cur_row)
    return rows


def _truncate_text_pillow(
    tdraw: ImageDraw.ImageDraw,
    text: str,
    font: Any,
    max_w: float,
) -> str:
    if max_w <= 12 or tdraw.textlength(text, font=font) <= max_w:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if tdraw.textlength(text[:mid] + ell, font=font) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + ell) if lo > 0 else ell


def _render_plot_pillow(
    tdraw: ImageDraw.ImageDraw,
    cell: dict[str, Any],
    cs: dict[str, Any],
    cw_i: int,
    ch_i: int,
    rw: float,
    rh: float,
    fscale: float,
    s: float,
    helpers: dict[str, Any],
) -> None:
    load_font = helpers["load_font"]
    rgba = helpers["rgba"]
    is_mono = cs["variant"] == "text"
    is_rev = cs["variant"] == "reverse"

    r_ui = min(rw / 620.0, rh / 360.0)
    card_ui = min(2.2, 1.0 + (r_ui - 1.0) * 0.52) if r_ui > 1.05 else 1.0
    fscale = fscale * card_ui

    series_list = cell.get("series", [])
    leg_mode = normalize_legend_pos(cell.get("legend", True))
    has_any_lbl = any(str(sr.get("label", "")).strip() for sr in series_list)
    eff_leg = leg_mode if has_any_lbl else "none"

    label = str(cell.get("label", "")).strip()
    is_dyn = bool(cell.get("dynamic"))
    has_header = bool(label) or is_dyn
    xlabel = str(cell.get("xlabel", "")).strip()
    ylabel = str(cell.get("ylabel", "")).strip()

    ink_hex = cs["reverse_ink"] if is_rev else cs["muted"]
    ink_op = float(cs["muted_opacity"]) if is_rev else 0.85
    txt_hex = cs["reverse_ink"] if is_rev else cs["text"]
    txt_op = float(cs["text_opacity"])

    f_hdr = load_font(int(round(14.0 * fscale * s)), bold=True, mono=is_mono)
    f_leg = load_font(int(round(11.5 * fscale * s)), bold=True, mono=is_mono)
    f_tick = load_font(int(round(11.0 * fscale * s)), bold=False, mono=is_mono)
    f_axis = load_font(int(round(12.0 * fscale * s)), bold=True, mono=is_mono)

    pad_x = 20.0 * s
    badge_reserve = (72.0 if is_mono else 28.0) * s if is_dyn else 0.0

    # 1. Bold top card title (clipped before live indicator so it never collides)
    if label:
        hdr_raw = f"┤ {label} ├" if is_mono else label
        hdr_fit = _truncate_text_pillow(
            tdraw, hdr_raw, f_hdr, cw_i - pad_x * 2.0 - badge_reserve
        )
        tdraw.text(
            (pad_x, 13.0 * fscale * s),
            hdr_fit,
            fill=rgba(txt_hex, txt_op),
            font=f_hdr,
        )

    # 2. Wrap legend rows cleanly in dedicated top (under title) or bottom (under xlabel) band
    leg_avail_w = cw_i - pad_x * 2.0 - (
        badge_reserve if (eff_leg == "top" and not label) else 0.0
    )
    leg_rows = (
        _pack_legend_rows(
            series_list,
            cs,
            is_rev,
            leg_avail_w,
            lambda lbl: tdraw.textlength(lbl, font=f_leg),
            19.0 * fscale * s,
            16.0 * fscale * s,
        )
        if eff_leg != "none"
        else []
    )
    leg_row_h = 18.0 * fscale * s

    if eff_leg == "top" and leg_rows:
        top_leg_y0 = (35.0 if label else 13.0) * fscale * s
        top_pad = top_leg_y0 + len(leg_rows) * leg_row_h + 8.0 * fscale * s
    else:
        top_leg_y0 = 0.0
        top_pad = (38.0 if has_header else 18.0) * fscale * s

    axes_bot_h = (44.0 if xlabel else 26.0) * fscale * s
    if eff_leg == "bottom" and leg_rows:
        bot_pad = axes_bot_h + len(leg_rows) * leg_row_h + 10.0 * fscale * s
    else:
        bot_pad = (46.0 if xlabel else 30.0) * fscale * s

    # 3. Dynamic collision-free left & right margins based on actual tick widths
    x_min, x_max, y_min, y_max = compute_axis2d_bounds(
        series_list,
        cell.get("xlim"),
        cell.get("ylim"),
        xmin=cell.get("xmin"),
        xmax=cell.get("xmax"),
        ymin=cell.get("ymin"),
        ymax=cell.get("ymax"),
    )
    est_ax_h = max(32.0 * s, ch_i - top_pad - bot_pad)
    y_ticks = compute_axis_ticks(
        y_min,
        y_max,
        max(3, int(est_ax_h / (52.0 * s))),
        step=cell.get("ystep"),
        explicit_min=cell.get("ymin"),
    )
    vis_y_ticks = [yt for yt in y_ticks if y_min - 1e-9 <= yt <= y_max + 1e-9]
    max_ytick_w = max(
        (tdraw.textlength(format_tick_number(yt), font=f_tick) for yt in vis_y_ticks),
        default=20.0 * s,
    )

    left_pad = (
        max(58.0 * fscale * s, 38.0 * fscale * s + max_ytick_w)
        if ylabel
        else max(44.0 * fscale * s, 22.0 * fscale * s + max_ytick_w)
    )
    est_ax_w = max(40.0 * s, cw_i - left_pad - 22.0 * fscale * s)
    x_ticks = compute_axis_ticks(
        x_min,
        x_max,
        max(3, int(est_ax_w / (85.0 * s))),
        step=cell.get("xstep"),
        explicit_min=cell.get("xmin"),
    )
    vis_x_ticks = [xt for xt in x_ticks if x_min - 1e-9 <= xt <= x_max + 1e-9]
    half_last_xw = (
        0.5 * tdraw.textlength(format_tick_number(vis_x_ticks[-1]), font=f_tick)
        if vis_x_ticks
        else 0.0
    )
    right_pad = max(22.0 * fscale * s, half_last_xw + 14.0 * s)

    ax_x = left_pad
    ax_y = top_pad
    ax_w = max(40.0 * s, cw_i - left_pad - right_pad)
    ax_h = max(32.0 * s, ch_i - top_pad - bot_pad)

    def to_px_x(xv: float) -> float:
        return ax_x + ((xv - x_min) / (x_max - x_min or 1.0)) * ax_w

    def to_px_y(yv: float) -> float:
        return ax_y + ax_h - ((yv - y_min) / (y_max - y_min or 1.0)) * ax_h

    grid_rgba = rgba(ink_hex, 0.16)
    spine_rgba = rgba(ink_hex, 0.36)
    show_grid = bool(cell.get("grid", True))

    y_lbl_stride = max(1, math.ceil(len(vis_y_ticks) / max(2, int(ax_h / (18.0 * s)))))
    for y_i, yt in enumerate(vis_y_ticks):
        py = to_px_y(yt)
        if show_grid:
            tdraw.line(
                [(ax_x, py), (ax_x + ax_w, py)],
                fill=grid_rgba,
                width=max(1, int(round(s))),
            )
        if y_i % y_lbl_stride == 0:
            tdraw.text(
                (ax_x - 8 * s, py),
                format_tick_number(yt),
                fill=rgba(ink_hex, ink_op),
                font=f_tick,
                anchor="rm",
            )

    x_lbl_stride = max(1, math.ceil(len(vis_x_ticks) / max(2, int(ax_w / (38.0 * s)))))
    for x_i, xt in enumerate(vis_x_ticks):
        px = to_px_x(xt)
        if show_grid:
            tdraw.line(
                [(px, ax_y), (px, ax_y + ax_h)],
                fill=grid_rgba,
                width=max(1, int(round(s))),
            )
        if x_i % x_lbl_stride == 0:
            tdraw.text(
                (px, ax_y + ax_h + 7 * s),
                format_tick_number(xt),
                fill=rgba(ink_hex, ink_op),
                font=f_tick,
                anchor="mt",
            )

    # L-spine
    tdraw.line(
        [(ax_x, ax_y), (ax_x, ax_y + ax_h), (ax_x + ax_w, ax_y + ax_h)],
        fill=spine_rgba,
        width=max(1, int(round(1.2 * s))),
    )

    if xlabel:
        tdraw.text(
            (ax_x + ax_w / 2.0, ax_y + ax_h + 25 * fscale * s),
            xlabel,
            fill=rgba(ink_hex, min(1.0, ink_op + 0.12)),
            font=f_axis,
            anchor="mt",
        )
    if ylabel:
        lbl_im = Image.new("RGBA", (int(round(ax_h)), int(round(24 * fscale * s))), (0, 0, 0, 0))
        ImageDraw.Draw(lbl_im).text(
            (lbl_im.width / 2.0, lbl_im.height / 2.0),
            ylabel,
            fill=rgba(ink_hex, min(1.0, ink_op + 0.12)),
            font=f_axis,
            anchor="mm",
        )
        rot = lbl_im.rotate(90, expand=True)
        dest_x = max(
            int(round(4 * s)),
            int(round(ax_x - 14.0 * fscale * s - max_ytick_w - rot.width)),
        )
        dest_y = int(round(ax_y + (ax_h - rot.height) / 2.0))
        tdraw._image.alpha_composite(rot, dest=(dest_x, dest_y))  # type: ignore[attr-defined]

    # Plot area sub-canvas so curves & vertical area fills clip cleanly to `[ax_x..ax_x+ax_w, ax_y..ax_y+ax_h]`
    pw_i = max(4, int(round(ax_w)))
    ph_i = max(4, int(round(ax_h)))
    plot_layer = Image.new("RGBA", (pw_i, ph_i), (0, 0, 0, 0))

    base_data_y = max(y_min, min(y_max, 0.0))
    base_local_y = ph_i - ((base_data_y - y_min) / (y_max - y_min or 1.0)) * ph_i

    for idx, sr in enumerate(series_list):
        xs = sr.get("x", [])
        ys = sr.get("y", [])
        n = min(len(xs), len(ys))
        if n == 0:
            continue

        s_col = (
            cs["reverse_ink"]
            if (is_rev and idx == 0 and not sr.get("color"))
            else pick_series_color(sr.get("color"), idx, cs["accent"])
        )
        local_pts = [
            (
                ((float(xs[i]) - x_min) / (x_max - x_min or 1.0)) * pw_i,
                ph_i - ((float(ys[i]) - y_min) / (y_max - y_min or 1.0)) * ph_i,
            )
            for i in range(n)
            if math.isfinite(float(xs[i])) and math.isfinite(float(ys[i]))
        ]
        if not local_pts:
            continue

        fill_alpha = float(sr.get("fill_alpha", 0.12))
        if fill_alpha > 0 and len(local_pts) >= 2:
            min_py = min(p[1] for p in local_pts)
            poly_mask = Image.new("L", (pw_i, ph_i), 0)
            poly_pts = [
                (local_pts[0][0], base_local_y),
                *local_pts,
                (local_pts[-1][0], base_local_y),
            ]
            ImageDraw.Draw(poly_mask).polygon(poly_pts, fill=255)

            # Build vertical gradient strip of height ph_i and resize
            grad_1d = Image.new("RGBA", (1, max(2, ph_i)), (0, 0, 0, 0))
            span_h = max(1.0, base_local_y - min_py)
            for gy in range(ph_i):
                t_fade = 1.0 - max(0.0, min(1.0, (gy - min_py) / span_h))
                grad_1d.putpixel((0, gy), rgba(s_col, fill_alpha * t_fade))
            grad_full = grad_1d.resize((pw_i, ph_i), resample=Image.Resampling.BILINEAR)

            area_layer = Image.new("RGBA", (pw_i, ph_i), (0, 0, 0, 0))
            area_layer.paste(grad_full, (0, 0), mask=poly_mask)
            plot_layer = Image.alpha_composite(plot_layer, area_layer)

        pdraw = ImageDraw.Draw(plot_layer)
        lw_px = max(1, int(round(float(sr.get("linewidth", 2.4)) * s)))
        _draw_dashed_polyline_pillow(
            pdraw,
            local_pts,
            rgba(s_col, 1.0),
            lw_px,
            str(sr.get("linestyle", "solid")),
            s,
        )

        marker = sr.get("marker")
        if marker in ("circle", "dot"):
            mr = (3.5 if marker == "circle" else 2.8) * s
            center_fill = rgba(cs["accent"] if is_rev else "#0f172a", 1.0)
            for px, py in local_pts:
                if marker == "circle":
                    pdraw.ellipse(
                        [px - mr, py - mr, px + mr, py + mr],
                        fill=center_fill,
                        outline=rgba(s_col, 1.0),
                        width=max(1, int(round(1.8 * s))),
                    )
                else:
                    pdraw.ellipse(
                        [px - mr, py - mr, px + mr, py + mr], fill=rgba(s_col, 1.0)
                    )

    tdraw._image.alpha_composite(plot_layer, dest=(int(round(ax_x)), int(round(ax_y))))  # type: ignore[attr-defined]

    # Dedicated wrapped legend band (top under title, or bottom under xlabel)
    if leg_rows:
        base_leg_y = (
            top_leg_y0
            if eff_leg == "top"
            else (ax_y + ax_h + axes_bot_h)
        )
        sw_len = 14.0 * fscale * s
        sw_gap = 5.0 * fscale * s
        it_gap = 16.0 * fscale * s
        for r_i, row_items in enumerate(leg_rows):
            leg_cy = base_leg_y + (r_i + 0.5) * leg_row_h
            cur_x = pad_x
            for s_lbl, s_col, ls, item_w in row_items:
                _draw_dashed_polyline_pillow(
                    tdraw,
                    [(cur_x, leg_cy), (cur_x + sw_len, leg_cy)],
                    rgba(s_col, 1.0),
                    max(1, int(round(2.4 * s))),
                    ls,
                    s,
                )
                tdraw.text(
                    (cur_x + sw_len + sw_gap, leg_cy),
                    s_lbl,
                    fill=rgba(txt_hex, min(1.0, txt_op * 0.92)),
                    font=f_leg,
                    anchor="lm",
                )
                cur_x += item_w + it_gap


def _render_plot_svg(
    cell: dict[str, Any],
    cs: dict[str, Any],
    rx: float,
    ry: float,
    rw: float,
    rh: float,
) -> list[str]:
    variant = cs["variant"]
    is_rev = variant == "reverse"
    is_mono = variant == "text"
    cell_font = html.escape(MONOSPACE_STACK if is_mono else cs["font"], quote=True)
    r_ui = min(rw / 620.0, rh / 360.0)
    card_ui = min(2.2, 1.0 + (r_ui - 1.0) * 0.52) if r_ui > 1.05 else 1.0
    fscale = float(cs["font_scale"]) * card_ui

    series_list = cell.get("series", [])
    leg_mode = normalize_legend_pos(cell.get("legend", True))
    has_any_lbl = any(str(sr.get("label", "")).strip() for sr in series_list)
    eff_leg = leg_mode if has_any_lbl else "none"

    label = str(cell.get("label", "")).strip()
    is_dyn = bool(cell.get("dynamic"))
    has_header = bool(label) or is_dyn
    xlabel = str(cell.get("xlabel", "")).strip()
    ylabel = str(cell.get("ylabel", "")).strip()

    pad_x = 20.0
    badge_reserve = (72.0 if is_mono else 28.0) if is_dyn else 0.0
    leg_avail_w = rw - pad_x * 2.0 - (
        badge_reserve if (eff_leg == "top" and not label) else 0.0
    )
    leg_rows = (
        _pack_legend_rows(
            series_list,
            cs,
            is_rev,
            leg_avail_w,
            lambda lbl: len(lbl) * 6.8 * fscale,
            19.0 * fscale,
            16.0 * fscale,
        )
        if eff_leg != "none"
        else []
    )
    leg_row_h = 18.0 * fscale

    if eff_leg == "top" and leg_rows:
        top_leg_y0 = (35.0 if label else 13.0) * fscale
        top_pad = top_leg_y0 + len(leg_rows) * leg_row_h + 8.0 * fscale
    else:
        top_leg_y0 = 0.0
        top_pad = (38.0 if has_header else 18.0) * fscale

    axes_bot_h = (44.0 if xlabel else 26.0) * fscale
    if eff_leg == "bottom" and leg_rows:
        bot_pad = axes_bot_h + len(leg_rows) * leg_row_h + 10.0 * fscale
    else:
        bot_pad = (46.0 if xlabel else 30.0) * fscale

    x_min, x_max, y_min, y_max = compute_axis2d_bounds(
        series_list,
        cell.get("xlim"),
        cell.get("ylim"),
        xmin=cell.get("xmin"),
        xmax=cell.get("xmax"),
        ymin=cell.get("ymin"),
        ymax=cell.get("ymax"),
    )
    est_ax_h = max(32.0, rh - top_pad - bot_pad)
    y_ticks = compute_axis_ticks(
        y_min,
        y_max,
        max(3, int(est_ax_h / 52.0)),
        step=cell.get("ystep"),
        explicit_min=cell.get("ymin"),
    )
    vis_y_ticks = [yt for yt in y_ticks if y_min - 1e-9 <= yt <= y_max + 1e-9]
    max_ytick_w = max(
        (len(format_tick_number(yt)) * 6.6 * fscale for yt in vis_y_ticks),
        default=20.0,
    )
    left_pad = (
        max(58.0 * fscale, 38.0 * fscale + max_ytick_w)
        if ylabel
        else max(44.0 * fscale, 22.0 * fscale + max_ytick_w)
    )

    est_ax_w = max(40.0, rw - left_pad - 22.0 * fscale)
    x_ticks = compute_axis_ticks(
        x_min,
        x_max,
        max(3, int(est_ax_w / 85.0)),
        step=cell.get("xstep"),
        explicit_min=cell.get("xmin"),
    )
    vis_x_ticks = [xt for xt in x_ticks if x_min - 1e-9 <= xt <= x_max + 1e-9]
    half_last_xw = (
        0.5 * len(format_tick_number(vis_x_ticks[-1])) * 6.6 * fscale
        if vis_x_ticks
        else 0.0
    )
    right_pad = max(22.0 * fscale, half_last_xw + 14.0)

    ax_x = rx + left_pad
    ax_y = ry + top_pad
    ax_w = max(40.0, rw - left_pad - right_pad)
    ax_h = max(32.0, rh - top_pad - bot_pad)

    ink_hex = html.escape(cs["reverse_ink"] if is_rev else cs["muted"])
    ink_op = float(cs["muted_opacity"]) if is_rev else 0.85
    txt_hex = html.escape(cs["reverse_ink"] if is_rev else cs["text"])
    txt_op = float(cs["text_opacity"])

    parts: list[str] = []
    if label:
        hdr_txt = f"┤ {label} ├" if is_mono else label
        parts.append(
            f'  <text x="{rx + pad_x:.1f}" y="{ry + 25 * fscale:.1f}" fill="{txt_hex}" '
            f'fill-opacity="{txt_op:.2f}" font-family="{cell_font}" font-size="{14 * fscale:.1f}" '
            f'font-weight="700">{html.escape(hdr_txt)}</text>'
        )

    def to_svg_x(xv: float) -> float:
        return ax_x + ((xv - x_min) / (x_max - x_min or 1.0)) * ax_w

    def to_svg_y(yv: float) -> float:
        return ax_y + ax_h - ((yv - y_min) / (y_max - y_min or 1.0)) * ax_h

    show_grid = bool(cell.get("grid", True))
    tick_fs = 11.0 * fscale
    y_lbl_stride = max(1, math.ceil(len(vis_y_ticks) / max(2, int(ax_h / 18.0))))
    for y_i, yt in enumerate(vis_y_ticks):
        py = to_svg_y(yt)
        if show_grid:
            parts.append(
                f'  <line x1="{ax_x:.1f}" y1="{py:.1f}" x2="{ax_x + ax_w:.1f}" y2="{py:.1f}" '
                f'stroke="{ink_hex}" stroke-opacity="0.16" stroke-width="1" />'
            )
        if y_i % y_lbl_stride == 0:
            parts.append(
                f'  <text x="{ax_x - 8:.1f}" y="{py:.1f}" text-anchor="end" dominant-baseline="middle" '
                f'fill="{ink_hex}" fill-opacity="{ink_op:.2f}" font-family="{cell_font}" '
                f'font-size="{tick_fs:.1f}">{html.escape(format_tick_number(yt))}</text>'
            )

    x_lbl_stride = max(1, math.ceil(len(vis_x_ticks) / max(2, int(ax_w / 38.0))))
    for x_i, xt in enumerate(vis_x_ticks):
        px = to_svg_x(xt)
        if show_grid:
            parts.append(
                f'  <line x1="{px:.1f}" y1="{ax_y:.1f}" x2="{px:.1f}" y2="{ax_y + ax_h:.1f}" '
                f'stroke="{ink_hex}" stroke-opacity="0.16" stroke-width="1" />'
            )
        if x_i % x_lbl_stride == 0:
            parts.append(
                f'  <text x="{px:.1f}" y="{ax_y + ax_h + 16:.1f}" text-anchor="middle" '
                f'fill="{ink_hex}" fill-opacity="{ink_op:.2f}" font-family="{cell_font}" '
                f'font-size="{tick_fs:.1f}">{html.escape(format_tick_number(xt))}</text>'
            )

    parts.append(
        f'  <path d="M {ax_x:.1f} {ax_y:.1f} L {ax_x:.1f} {ax_y + ax_h:.1f} L {ax_x + ax_w:.1f} {ax_y + ax_h:.1f}" '
        f'fill="none" stroke="{ink_hex}" stroke-opacity="0.36" stroke-width="1.2" />'
    )

    if xlabel:
        parts.append(
            f'  <text x="{ax_x + ax_w / 2:.1f}" y="{ax_y + ax_h + 36 * fscale:.1f}" text-anchor="middle" '
            f'fill="{ink_hex}" font-family="{cell_font}" font-size="{12 * fscale:.1f}" '
            f'font-weight="600">{html.escape(xlabel)}</text>'
        )
    if ylabel:
        ly_x = max(rx + 12.0, ax_x - 18.0 * fscale - max_ytick_w)
        ly_y = ax_y + ax_h / 2
        parts.append(
            f'  <text x="{ly_x:.1f}" y="{ly_y:.1f}" text-anchor="middle" '
            f'transform="rotate(-90 {ly_x:.1f} {ly_y:.1f})" fill="{ink_hex}" '
            f'font-family="{cell_font}" font-size="{12 * fscale:.1f}" font-weight="600">'
            f"{html.escape(ylabel)}</text>"
        )

    clip_plot_id = f"fx_plot_area_{html.escape(str(cell['id']))}"
    parts.append(
        f'  <defs><clipPath id="{clip_plot_id}">'
        f'<rect x="{ax_x:.1f}" y="{ax_y:.1f}" width="{ax_w:.1f}" height="{ax_h:.1f}" />'
        f"</clipPath></defs>"
    )
    parts.append(f'  <g clip-path="url(#{clip_plot_id})">')

    base_data_y = max(y_min, min(y_max, 0.0))
    base_svg_y = to_svg_y(base_data_y)

    for idx, sr in enumerate(series_list):
        xs = sr.get("x", [])
        ys = sr.get("y", [])
        n = min(len(xs), len(ys))
        if n == 0:
            continue
        s_col = html.escape(
            cs["reverse_ink"]
            if (is_rev and idx == 0 and not sr.get("color"))
            else pick_series_color(sr.get("color"), idx, cs["accent"])
        )
        pts = [
            (to_svg_x(float(xs[i])), to_svg_y(float(ys[i])))
            for i in range(n)
            if math.isfinite(float(xs[i])) and math.isfinite(float(ys[i]))
        ]
        if not pts:
            continue

        fill_alpha = float(sr.get("fill_alpha", 0.12))
        if fill_alpha > 0 and len(pts) >= 2:
            grad_id = f"fx_sgrad_{html.escape(str(cell['id']))}_{idx}"
            parts.append(
                f'    <defs><linearGradient id="{grad_id}" x1="0%" y1="0%" x2="0%" y2="100%">'
                f'<stop offset="0%" stop-color="{s_col}" stop-opacity="{fill_alpha:.3f}" />'
                f'<stop offset="100%" stop-color="{s_col}" stop-opacity="0" />'
                f"</linearGradient></defs>"
            )
            area_cmds = [f"M {pts[0][0]:.2f} {base_svg_y:.2f}"]
            area_cmds.extend(f"L {px:.2f} {py:.2f}" for px, py in pts)
            area_cmds.append(f"L {pts[-1][0]:.2f} {base_svg_y:.2f} Z")
            parts.append(
                f'    <path d="{" ".join(area_cmds)}" fill="url(#{grad_id})" />'
            )

        line_cmds = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
        line_cmds.extend(f"L {px:.2f} {py:.2f}" for px, py in pts[1:])
        ls = sr.get("linestyle", "solid")
        dash_attr = (
            ' stroke-dasharray="7 5"'
            if ls == "dashed"
            else (' stroke-dasharray="2.2 4"' if ls == "dotted" else "")
        )
        parts.append(
            f'    <path d="{" ".join(line_cmds)}" fill="none" stroke="{s_col}" '
            f'stroke-width="{float(sr.get("linewidth", 2.4)):.2f}" stroke-linecap="round" '
            f'stroke-linejoin="round"{dash_attr} />'
        )

        mk = sr.get("marker")
        if mk in ("circle", "dot"):
            r_mk = 3.5 if mk == "circle" else 2.8
            for px, py in pts:
                if mk == "circle":
                    parts.append(
                        f'    <circle cx="{px:.2f}" cy="{py:.2f}" r="{r_mk}" '
                        f'fill="#0f172a" stroke="{s_col}" stroke-width="1.8" />'
                    )
                else:
                    parts.append(
                        f'    <circle cx="{px:.2f}" cy="{py:.2f}" r="{r_mk}" fill="{s_col}" />'
                    )

    parts.append("  </g>")

    if leg_rows:
        base_leg_y = (
            (ry + top_leg_y0)
            if eff_leg == "top"
            else (ax_y + ax_h + axes_bot_h)
        )
        sw_len = 14.0 * fscale
        sw_gap = 5.0 * fscale
        it_gap = 16.0 * fscale
        for r_i, row_items in enumerate(leg_rows):
            leg_cy = base_leg_y + (r_i + 0.5) * leg_row_h
            cur_x = rx + pad_x
            for s_lbl, s_col_raw, ls, item_w in row_items:
                s_col = html.escape(s_col_raw)
                dash_attr = (
                    ' stroke-dasharray="4 3"'
                    if ls == "dashed"
                    else (' stroke-dasharray="1.5 2.5"' if ls == "dotted" else "")
                )
                parts.append(
                    f'  <line x1="{cur_x:.1f}" y1="{leg_cy:.1f}" x2="{cur_x + sw_len:.1f}" y2="{leg_cy:.1f}" '
                    f'stroke="{s_col}" stroke-width="2.4"{dash_attr} />'
                )
                parts.append(
                    f'  <text x="{cur_x + sw_len + sw_gap:.1f}" y="{leg_cy:.1f}" dominant-baseline="middle" '
                    f'fill="{txt_hex}" fill-opacity="{min(1.0, txt_op * 0.92):.2f}" font-family="{cell_font}" '
                    f'font-size="{11.5 * fscale:.1f}" font-weight="600">{html.escape(s_lbl)}</text>'
                )
                cur_x += item_w + it_gap
    return parts


def _render_plot_tui(
    cell: dict[str, Any],
    inner_w: int,
    interior_h: int,
    colors: dict[str, str],
    helpers: dict[str, Any],
) -> list[str]:
    ansi = bool(helpers.get("ansi", True))
    bg_seq = str(helpers.get("bg_seq", ""))
    c_lbl = colors["lbl"]
    c_border = colors["border"]
    primary_accent = str(helpers.get("accent_hex", "#38bdf8"))

    series_list = cell.get("series", [])
    x_min, x_max, y_min, y_max = compute_axis2d_bounds(
        series_list,
        cell.get("xlim"),
        cell.get("ylim"),
        xmin=cell.get("xmin"),
        xmax=cell.get("xmax"),
        ymin=cell.get("ymin"),
        ymax=cell.get("ymax"),
    )

    leg_mode = normalize_legend_pos(cell.get("legend", True))
    has_legend = (leg_mode != "none") and any(
        str(sr.get("label", "")).strip() for sr in series_list
    )
    legend_h = 1 if (has_legend and interior_h >= 6) else 0
    bottom_h = 2 if interior_h >= 7 else 1
    canvas_h = max(2, interior_h - legend_h - bottom_h)

    y_mid_raw = (y_min + y_max) / 2.0
    if abs(y_mid_raw) < 0.01 * max(1e-9, y_max - y_min):
        y_mid_raw = 0.0
    y_lbl_top = format_tick_number(y_max)
    y_lbl_mid = format_tick_number(y_mid_raw)
    y_lbl_bot = format_tick_number(y_min)
    y_col_w = min(
        max(len(y_lbl_top), len(y_lbl_mid), len(y_lbl_bot)) + 2, max(6, inner_w // 3)
    )
    canvas_w = max(4, inner_w - y_col_w - 1)
    right_pad = max(0, inner_w - y_col_w - canvas_w)

    braille = BrailleCanvas(canvas_w, canvas_h)

    for idx, sr in enumerate(series_list):
        xs = sr.get("x", [])
        ys = sr.get("y", [])
        n = min(len(xs), len(ys))
        if n == 0:
            continue
        s_col = pick_series_color(sr.get("color"), idx, primary_accent)
        ls = str(sr.get("linestyle", "solid"))

        sub_pts: list[tuple[int, int]] = []
        for i in range(n):
            xv, yv = float(xs[i]), float(ys[i])
            if not (math.isfinite(xv) and math.isfinite(yv)):
                continue
            px = int(
                round(((xv - x_min) / (x_max - x_min or 1.0)) * (braille.px_w - 1))
            )
            py = int(
                round(
                    (braille.px_h - 1)
                    - ((yv - y_min) / (y_max - y_min or 1.0)) * (braille.px_h - 1)
                )
            )
            px = max(0, min(braille.px_w - 1, px))
            py = max(0, min(braille.px_h - 1, py))
            sub_pts.append((px, py))

        if len(sub_pts) == 1:
            braille.set_pixel(sub_pts[0][0], sub_pts[0][1], s_col)
        else:
            for i in range(len(sub_pts) - 1):
                braille.draw_line(
                    sub_pts[i][0],
                    sub_pts[i][1],
                    sub_pts[i + 1][0],
                    sub_pts[i + 1][1],
                    s_col,
                    linestyle=ls,
                )

    rows_out: list[str] = []
    legend_line = ""
    if legend_h == 1:
        vis_len = 0
        pieces: list[str] = []
        for idx, sr in enumerate(series_list):
            s_lbl = str(sr.get("label", "")).strip()
            if not s_lbl:
                continue
            s_col = pick_series_color(sr.get("color"), idx, primary_accent)
            swatch = (
                "╌"
                if sr.get("linestyle") == "dashed"
                else ("┈" if sr.get("linestyle") == "dotted" else "━")
            )
            entry_vis = f" {swatch} {s_lbl} "
            if vis_len + len(entry_vis) > inner_w:
                break
            col_seq = bg_seq + _ansi_fg(s_col, ansi, bold=True)
            pieces.append(f"{col_seq} {swatch} {c_lbl}{s_lbl} ")
            vis_len += len(entry_vis)
        pad_rem = inner_w - vis_len
        legend_line = "".join(pieces) + (" " * pad_rem)

    if legend_h == 1 and leg_mode == "top":
        rows_out.append(legend_line)

    # Braille rows with Y-axis spine & tick labels
    b_rows = braille.render_rows(ansi=ansi, restore_seq=bg_seq)
    mid_r = canvas_h // 2
    for r_idx, b_line in enumerate(b_rows):
        if r_idx == 0:
            y_txt = y_lbl_top[: y_col_w - 1].rjust(y_col_w - 1)
            spine_ch = "┤"
        elif r_idx == canvas_h - 1:
            y_txt = y_lbl_bot[: y_col_w - 1].rjust(y_col_w - 1)
            spine_ch = "┤"
        elif r_idx == mid_r and canvas_h >= 5:
            y_txt = y_lbl_mid[: y_col_w - 1].rjust(y_col_w - 1)
            spine_ch = "┤"
        else:
            y_txt = " " * (y_col_w - 1)
            spine_ch = "│"
        rows_out.append(
            f"{c_lbl}{y_txt}{c_border}{spine_ch}{bg_seq}{b_line}{' ' * right_pad}"
        )

    # X-axis baseline
    x_axis_line = f"{' ' * (y_col_w - 1)}{c_border}└{'─' * canvas_w}{' ' * right_pad}"
    rows_out.append(x_axis_line)

    # X-tick min / xlabel / max footer line
    if bottom_h >= 2:
        xl_s = format_tick_number(x_min)
        xr_s = format_tick_number(x_max)
        xlabel = str(cell.get("xlabel", "")).strip()
        avail_x = canvas_w
        if len(xl_s) + len(xr_s) + 2 <= avail_x:
            mid_space = avail_x - len(xl_s) - len(xr_s)
            if xlabel and len(xlabel) + 2 <= mid_space:
                lp = (mid_space - len(xlabel)) // 2
                rp = mid_space - len(xlabel) - lp
                mid_str = f"{' ' * lp}{xlabel}{' ' * rp}"
            else:
                mid_str = " " * mid_space
            x_lbl_row = f"{' ' * y_col_w}{c_lbl}{xl_s}{mid_str}{xr_s}{' ' * right_pad}"
        else:
            x_lbl_row = " " * inner_w
        rows_out.append(x_lbl_row)

    if legend_h == 1 and leg_mode == "bottom":
        rows_out.append(legend_line)

    while len(rows_out) < interior_h:
        rows_out.append(" " * inner_w)
    return rows_out[:interior_h]


register_chart_renderers(
    "plot",
    pillow=_render_plot_pillow,
    svg=_render_plot_svg,
    tui=_render_plot_tui,
)
