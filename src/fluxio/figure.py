"""Core Figure container: subplot grid, `.style(...)`, `print(fig)` terminal TUI, Jupyter, and exports."""

from __future__ import annotations
import uuid
from collections.abc import Iterator, MutableMapping
from pathlib import Path
from typing import Any
from .html_export import render_jupyter_html, render_standalone_html
from .protocol import (
    NumberCell,
    NumberSource,
    ToolbarConfig,
    format_number_value,
)
from .render_2d import save_gif, save_png, save_svg, save_video
from .text_render import render_spec_to_terminal
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
    ) -> NumberCell:
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
        fps: int = 30,
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

        self.cells: list[NumberCell] = []
        self._occupied: set[tuple[int, int]] = set()
        self._slot_styles: dict[tuple[int, int], dict[str, Any]] = {}
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

    def __getitem__(self, key: tuple[int, int] | int) -> SubplotSlot:
        if isinstance(key, int):
            row, col = divmod(key, self.cols)
        else:
            row, col = key
        self._validate_bounds(row, col, 1, 1)
        return SubplotSlot(self, row, col)

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
    ) -> NumberCell:
        """Add a static or dynamic numeric display widget to the Figure grid."""
        if row is None and col is None:
            row, col = self._find_next_free_slot()
        elif row is None or col is None:
            raise ValueError("Specify both row and col, or omit both for auto-placement.")

        self._validate_bounds(row, col, row_span, col_span)
        slots = {
            (r, c)
            for r in range(row, row + row_span)
            for c in range(col, col + col_span)
        }
        overlap = slots & self._occupied
        if overlap:
            raise ValueError(f"Grid cell(s) {sorted(overlap)} already occupied.")

        self._occupied |= slots
        pending_style = dict(self._slot_styles.get((row, col), {}))
        cell = NumberCell(
            id=f"cell_{row}_{col}",
            row=row,
            col=col,
            source=value,
            label=label,
            unit=unit,
            prefix=prefix,
            precision=precision,
            color=color,
            description=description,
            row_span=row_span,
            col_span=col_span,
            _style_overrides=pending_style,
        )
        self.cells.append(cell)
        return cell

    def evaluate_frame(
        self,
        t: float,
        *,
        step_index: int | None = None,
    ) -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []
        for cell in self.cells:
            val = cell.evaluate_at(t, step_index=step_index)
            updates.append(
                {
                    "id": cell.id,
                    "value": val,
                    "formatted": format_number_value(val, cell.precision, cell.prefix),
                }
            )
        return updates

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

    def to_text(self, *, ansi: bool = True, width: int | None = None) -> str:
        """Render the Figure as a formatted Unicode TUI string (with optional ANSI TrueColor)."""
        spec = self.to_spec(t=0.0, step_index=0)
        return render_spec_to_terminal(spec, ansi=ansi, width=width)

    def __str__(self) -> str:
        """Support `print(fig)` natively in any terminal with ANSI TrueColor & Unicode box-drawing."""
        return self.to_text(ansi=True)

    def __repr__(self) -> str:
        label = f" '{self.title}'" if self.title else ""
        return f"<fluxio.Figure{label} grid={self.rows}x{self.cols} cells={len(self.cells)}>"

    def _repr_html_(self) -> str:
        """Automatic rich inline rendering in Jupyter Notebooks (persists across cells & saves)."""
        bake = 5.0 if self.is_dynamic else None
        spec = self.to_spec(t=0.0, step_index=0, bake_duration=bake)
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
        """Export the Figure to `.png`, `.svg`, `.gif`, `.mp4`, `.webm`, `.html`, `.txt`, or `.ans`."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        ext = out.suffix.lower()
        effective_fps = fps if fps is not None else self.fps

        if ext == ".png":
            save_png(self, out, scale=scale)
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
