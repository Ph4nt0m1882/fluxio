"""Core Figure container: subplot grid, `.style(...)`, hybrid `Visual` composition, and exports."""

from __future__ import annotations

import sys
import time
import uuid
from collections.abc import Iterator, MutableMapping, Sequence
from pathlib import Path
from typing import Any

from .charts import Number, NumberSource, Plot, Visual
from .html_export import render_jupyter_html, render_standalone_html
from .protocol import ToolbarConfig
from .render_2d import save_gif, save_png, save_svg, save_video
from .text_render import (
    get_active_ipython_kernel,
    live_print_figure,
    render_ansi_to_svg,
    render_spec_to_terminal,
)
from .theme import BackgroundImage, Gradient, resolve_theme
from .window import show as _show_window


class FigureStyle(MutableMapping[str, Any]):
    """Callable style controller for `fig.style(...)` that also supports dict access."""

    def __init__(self, figure: Figure, initial: dict[str, Any] | None = None) -> None:
        self._figure = figure
        self._data: dict[str, Any] = dict(initial) if initial else {}

    def __call__(
        self,
        *,
        theme: str | None = None,
        variant: str | None = None,
        background: str | Gradient | BackgroundImage | dict[str, Any] | None = None,
        transparent: bool | None = None,
        padding: float | None = None,
        gap: float | None = None,
        hover_ms: float | None = None,
        title_color: str | None = None,
        subtitle_color: str | None = None,
        surface: str | None = None,
        surface_opacity: float | None = None,
        border: str | None = None,
        border_opacity: float | None = None,
        border_width: float | None = None,
        hover_border_width: float | None = None,
        radius: float | None = None,
        accent: str | None = None,
        accent_side: str | None = None,
        accent_width: float | None = None,
        text: str | None = None,
        text_opacity: float | None = None,
        muted: str | None = None,
        unit_color: str | None = None,
        font: str | None = None,
        font_scale: float | None = None,
        **extra: Any,
    ) -> Figure:
        if theme is not None:
            self._figure.theme_name = theme
        updates = {
            "variant": variant,
            "background": background,
            "transparent": transparent,
            "padding": padding,
            "gap": gap,
            "hover_ms": hover_ms,
            "title_color": title_color,
            "subtitle_color": subtitle_color,
            "surface": surface,
            "surface_opacity": surface_opacity,
            "border": border,
            "border_opacity": border_opacity,
            "border_width": border_width,
            "hover_border_width": hover_border_width,
            "radius": radius,
            "accent": accent,
            "accent_side": accent_side,
            "accent_width": accent_width,
            "text": text,
            "text_opacity": text_opacity,
            "muted": muted,
            "unit_color": unit_color,
            "font": font,
            "font_scale": font_scale,
            **extra,
        }
        for key, val in updates.items():
            if val is not None:
                self._data[key] = val
        resolve_theme(self._figure.theme_name, self._data)
        return self._figure

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


class SubplotSlot:
    """Proxy returned by `fig[row, col]` for cell placement and per-cell `.style(...)`."""

    def __init__(self, figure: Figure, row: int, col: int) -> None:
        self._figure = figure
        self._row = row
        self._col = col

    def style(
        self,
        *,
        variant: str | None = None,
        surface: str | None = None,
        surface_opacity: float | None = None,
        border: str | None = None,
        border_opacity: float | None = None,
        border_width: float | None = None,
        hover_border_width: float | None = None,
        radius: float | None = None,
        accent: str | None = None,
        accent_side: str | None = None,
        accent_width: float | None = None,
        text: str | None = None,
        text_opacity: float | None = None,
        muted: str | None = None,
        unit_color: str | None = None,
        font: str | None = None,
        font_scale: float | None = None,
        **extra: Any,
    ) -> SubplotSlot:
        """Configure aesthetics specifically for cell `(row, col)` (chainable)."""
        updates = {
            "variant": variant,
            "surface": surface,
            "surface_opacity": surface_opacity,
            "border": border,
            "border_opacity": border_opacity,
            "border_width": border_width,
            "hover_border_width": hover_border_width,
            "radius": radius,
            "accent": accent,
            "accent_side": accent_side,
            "accent_width": accent_width,
            "text": text,
            "text_opacity": text_opacity,
            "muted": muted,
            "unit_color": unit_color,
            "font": font,
            "font_scale": font_scale,
            **extra,
        }
        clean = {k: v for k, v in updates.items() if v is not None}
        self._figure._set_slot_style(self._row, self._col, clean)
        return self

    def add(
        self,
        visual: Visual,
        *,
        row_span: int | None = None,
        col_span: int | None = None,
    ) -> Visual:
        """Place a `Visual` instance at this `(row, col)` grid slot."""
        return self._figure.add(
            visual,
            row=self._row,
            col=self._col,
            row_span=row_span,
            col_span=col_span,
        )

    def number(
        self,
        value: NumberSource,
        *,
        label: str = "",
        unit: str = "",
        prefix: str = "",
        precision: int | None = None,
        color: str | None = None,
        description: str = "",
        row_span: int = 1,
        col_span: int = 1,
    ) -> Number:
        return self._figure.number(
            value,
            label=label,
            unit=unit,
            prefix=prefix,
            precision=precision,
            color=color,
            description=description,
            row=self._row,
            col=self._col,
            row_span=row_span,
            col_span=col_span,
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
        card_title: str = "",
        xlabel: str = "",
        ylabel: str = "",
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
        row_span: int = 1,
        col_span: int = 1,
    ) -> Plot:
        return self._figure.plot(
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
            card_title=card_title,
            xlabel=xlabel,
            ylabel=ylabel,
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
            description=description,
            row=self._row,
            col=self._col,
            row_span=row_span,
            col_span=col_span,
        )


class Figure:
    """Global Fluxio visualization container supporting grids, custom styles, terminal print, and exports."""

    def __init__(
        self,
        rows: int = 1,
        cols: int = 1,
        *,
        title: str = "",
        subtitle: str = "",
        theme: str = "dark",
        style: dict[str, Any] | None = None,
        size: tuple[int, int] = (900, 520),
        fps: int = 60,
        toolbar: bool | dict[str, bool] = True,
    ) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("Figure rows and cols must both be >= 1")
        self.id = f"fig_{uuid.uuid4().hex[:8]}"
        self.rows = int(rows)
        self.cols = int(cols)
        self.title = title
        self.subtitle = subtitle
        self.theme_name = theme
        self.style = FigureStyle(self, style)
        self.size = (int(size[0]), int(size[1]))
        self.fps = max(1, int(fps))

        if isinstance(toolbar, bool):
            self.toolbar = ToolbarConfig(enabled=toolbar)
        else:
            self.toolbar = ToolbarConfig(**toolbar)

        self.cells: list[Visual] = []
        self._occupied: set[tuple[int, int]] = set()
        self._slot_styles: dict[tuple[int, int], dict[str, Any]] = {}
        self._str_call_count: int = 0
        self._str_start_time: float | None = None
        self._str_prev_lines: int = 0
        self._str_last_ip_exec: Any = None
        _ = self.resolved_theme

    def _set_slot_style(self, row: int, col: int, updates: dict[str, Any]) -> None:
        slot = self._slot_styles.setdefault((row, col), {})
        slot.update(updates)
        for cell in self.cells:
            if cell.row == row and cell.col == col:
                cell.style(**updates)

    @property
    def resolved_theme(self) -> dict[str, Any]:
        return resolve_theme(self.theme_name, self.style)

    @property
    def is_dynamic(self) -> bool:
        return any(c.is_dynamic for c in self.cells)

    def _parse_grid_key(self, key: tuple[int, int] | int) -> tuple[int, int]:
        if isinstance(key, int):
            row, col = divmod(key, self.cols)
        else:
            row, col = key
        self._validate_bounds(row, col, 1, 1)
        return row, col

    def __getitem__(self, key: tuple[int, int] | int) -> SubplotSlot:
        row, col = self._parse_grid_key(key)
        return SubplotSlot(self, row, col)

    def __setitem__(self, key: tuple[int, int] | int, visual: Visual) -> None:
        if not isinstance(visual, Visual):
            raise TypeError(
                f"Expected a fluxio.Visual instance (e.g. fx.Number), got {type(visual).__name__}."
            )
        row, col = self._parse_grid_key(key)
        self.add(visual, row=row, col=col)

    def _validate_bounds(
        self,
        row: int,
        col: int,
        row_span: int,
        col_span: int,
    ) -> None:
        if (
            row < 0
            or col < 0
            or row + row_span > self.rows
            or col + col_span > self.cols
        ):
            raise ValueError(
                f"Cell position (row={row}, col={col}, span={row_span}x{col_span}) "
                f"is out of bounds for Figure grid ({self.rows}x{self.cols})."
            )

    def _find_next_free_slot(self) -> tuple[int, int]:
        for r in range(self.rows):
            for c in range(self.cols):
                if (r, c) not in self._occupied:
                    return (r, c)
        raise ValueError(
            f"All slots in Figure ({self.rows}x{self.cols}) are already occupied."
        )

    def add(
        self,
        visual: Visual,
        *,
        row: int | None = None,
        col: int | None = None,
        row_span: int | None = None,
        col_span: int | None = None,
    ) -> Visual:
        """Attach any `Visual` subclass instance to the Figure grid."""
        if not isinstance(visual, Visual):
            raise TypeError(
                f"Expected a fluxio.Visual instance, got {type(visual).__name__}."
            )

        if row is None and col is None:
            row, col = self._find_next_free_slot()
        elif row is None or col is None:
            raise ValueError(
                "Specify both row and col, or omit both for auto-placement."
            )

        r_span = row_span if row_span is not None else visual.row_span
        c_span = col_span if col_span is not None else visual.col_span
        self._validate_bounds(row, col, r_span, c_span)

        slots = {
            (r, c) for r in range(row, row + r_span) for c in range(col, col + c_span)
        }
        overlap = slots & self._occupied
        if overlap:
            raise ValueError(f"Grid cell(s) {sorted(overlap)} already occupied.")

        self._occupied |= slots
        visual.id = f"cell_{row}_{col}"
        visual.row = row
        visual.col = col
        visual.row_span = r_span
        visual.col_span = c_span

        pending_slot_style = self._slot_styles.get((row, col))
        if pending_slot_style:
            visual._apply_slot_defaults(pending_slot_style)

        self.cells.append(visual)
        return visual

    def number(
        self,
        value: NumberSource,
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
    ) -> Number:
        """Add a static or dynamic `Number` indicator widget to the Figure grid."""
        visual = Number(
            value,
            label=label,
            unit=unit,
            prefix=prefix,
            precision=precision,
            color=color,
            description=description,
            row_span=row_span,
            col_span=col_span,
        )
        self.add(visual, row=row, col=col, row_span=row_span, col_span=col_span)
        return visual

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
        card_title: str = "",
        xlabel: str = "",
        ylabel: str = "",
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
        row: int | None = None,
        col: int | None = None,
        row_span: int = 1,
        col_span: int = 1,
    ) -> Plot:
        """Add or superpose a 2D line series (`Plot`) on the target grid cell."""
        if row is not None and col is not None:
            for existing in self.cells:
                if existing.row == row and existing.col == col:
                    if isinstance(existing, Plot):
                        return existing.plot(
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
                            xlabel=xlabel or None,
                            ylabel=ylabel or None,
                            card_title=card_title or None,
                            xlim=xlim,
                            ylim=ylim,
                            xmin=xmin,
                            xmax=xmax,
                            xstep=xstep,
                            ymin=ymin,
                            ymax=ymax,
                            ystep=ystep,
                        )
                    break

        visual = Plot(
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
            card_title=card_title,
            xlabel=xlabel,
            ylabel=ylabel,
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
            description=description,
            row_span=row_span,
            col_span=col_span,
        )
        self.add(visual, row=row, col=col, row_span=row_span, col_span=col_span)
        return visual

    def evaluate_frame(
        self,
        t: float,
        *,
        step_index: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            cell.evaluate_tick_update(t, step_index=step_index)
            for cell in self.cells
            if cell.is_dynamic
        ]

    def to_spec(
        self,
        *,
        t: float = 0.0,
        step_index: int | None = 0,
        bake_duration: float | None = None,
    ) -> dict[str, Any]:
        theme_dict = self.resolved_theme
        return {
            "version": "0.1",
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "rows": self.rows,
            "cols": self.cols,
            "size": [self.size[0], self.size[1]],
            "fps": self.fps,
            "dynamic": self.is_dynamic,
            "theme": theme_dict,
            "toolbar": self.toolbar.to_dict(),
            "cells": [
                c.to_dict(
                    theme_dict=theme_dict,
                    t=t,
                    step_index=step_index,
                    bake_duration=bake_duration,
                    fps=self.fps,
                )
                for c in self.cells
            ],
        }

    def to_text(
        self,
        *,
        ansi: bool = True,
        width: int | None = None,
        t: float = 0.0,
        step_index: int | None = 0,
    ) -> str:
        spec = self.to_spec(t=t, step_index=step_index)
        return render_spec_to_terminal(spec, ansi=ansi, width=width)

    def reset_print(self) -> Figure:
        self._str_call_count = 0
        self._str_start_time = None
        self._str_prev_lines = 0
        self._str_last_ip_exec = None
        return self

    def print(
        self,
        *,
        duration: float | None = None,
        fps: int | None = None,
        controls: bool = True,
        ansi: bool = True,
        width: int | None = None,
    ) -> None:
        live_print_figure(
            self,
            duration=duration,
            fps=fps,
            controls=controls,
            ansi=ansi,
            width=width,
        )

    def __str__(self) -> str:
        ip = get_active_ipython_kernel()
        if ip is not None:
            exec_cnt = getattr(ip, "execution_count", None)
            if exec_cnt != self._str_last_ip_exec:
                self._str_prev_lines = 0
                self._str_last_ip_exec = exec_cnt

        now = time.monotonic()
        if self._str_call_count == 0 or self._str_start_time is None:
            self._str_start_time = now
            t = 0.0
        else:
            t = now - self._str_start_time

        step_idx = self._str_call_count
        self._str_call_count += 1

        rendered = self.to_text(ansi=True, t=t, step_index=step_idx)
        is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())

        if self._str_prev_lines > 0:
            if is_tty:
                prefix = f"\x1b[{self._str_prev_lines}A\r\x1b[J"
                self._str_prev_lines = rendered.count("\n") + 1
                return prefix + rendered
            if ip is not None:
                from IPython.display import clear_output  # type: ignore

                clear_output(wait=True)

        self._str_prev_lines = rendered.count("\n") + 1
        return rendered

    def __repr__(self) -> str:
        label = f" '{self.title}'" if self.title else ""
        return f"<fluxio.Figure{label} grid={self.rows}x{self.cols} cells={len(self.cells)}>"

    def _repr_html_(self) -> str:
        bake = 5.0 if self.is_dynamic else None
        old_fps = self.fps
        if bake is not None and self.fps > 24:
            self.fps = 24
        try:
            spec = self.to_spec(t=0.0, step_index=0, bake_duration=bake)
        finally:
            self.fps = old_fps
        return render_jupyter_html(spec)

    def show(
        self,
        *,
        backend: str = "auto",
        block: bool = True,
        host: str = "127.0.0.1",
        port: int = 0,
        close_after: float | None = None,
    ) -> str:
        return _show_window(
            self,
            backend=backend,
            block=block,
            host=host,
            port=port,
            close_after=close_after,
        )

    def save(
        self,
        path: str | Path,
        *,
        duration: float = 3.0,
        fps: int | None = None,
        scale: float = 2.0,
    ) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        ext = out.suffix.lower()
        default_export_fps = min(20, self.fps) if ext == ".gif" else min(30, self.fps)
        effective_fps = fps if fps is not None else default_export_fps

        if ext == ".png":
            save_png(self, out, scale=scale)
        elif out.name.lower().endswith(".term.svg"):
            svg_title = f"terminal — {self.title}" if self.title else "terminal — print(fig)"
            out.write_text(
                render_ansi_to_svg(self.to_text(ansi=True, width=76), title=svg_title),
                encoding="utf-8",
            )
        elif ext == ".svg":
            save_svg(self, out)
        elif ext == ".gif":
            save_gif(self, out, duration=duration, fps=effective_fps, scale=scale)
        elif ext in (".mp4", ".webm"):
            save_video(self, out, duration=duration, fps=effective_fps, scale=scale)
        elif ext in (".html", ".htm"):
            bake = duration if self.is_dynamic else None
            old_fps = self.fps
            self.fps = effective_fps
            try:
                spec = self.to_spec(t=0.0, step_index=0, bake_duration=bake)
            finally:
                self.fps = old_fps
            html_doc = render_standalone_html(spec, ws_url=None, full_viewport=True)
            out.write_text(html_doc, encoding="utf-8")
        elif ext == ".txt":
            out.write_text(self.to_text(ansi=False) + "\n", encoding="utf-8")
        elif ext == ".ans":
            out.write_text(self.to_text(ansi=True) + "\n", encoding="utf-8")
        else:
            raise ValueError(
                f"Unsupported export format '{ext}'. Supported: .png, .svg, .gif, .mp4, .webm, .html, .txt, .ans"
            )
        return out
