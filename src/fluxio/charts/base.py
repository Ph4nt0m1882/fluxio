"""Level-1 root `Visual` class and modular renderer registry for all Fluxio visualizations."""

from __future__ import annotations
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any
from ..theme import resolve_theme

if TYPE_CHECKING:
    from ..figure import Figure

# Keys that belong to the outer Figure container when `.style(...)` is called on a standalone Visual
_FIGURE_ONLY_STYLE_KEYS = frozenset(
    {
        "theme",
        "background",
        "transparent",
        "padding",
        "gap",
        "hover_ms",
        "title_color",
        "subtitle_color",
    }
)

PillowCellRenderer = Callable[..., None]
SvgCellRenderer = Callable[..., list[str]]
TuiCellRenderer = Callable[..., list[str]]

_PILLOW_RENDERERS: dict[str, PillowCellRenderer] = {}
_SVG_RENDERERS: dict[str, SvgCellRenderer] = {}
_TUI_RENDERERS: dict[str, TuiCellRenderer] = {}


def register_chart_renderers(
    kind: str,
    *,
    pillow: PillowCellRenderer,
    svg: SvgCellRenderer,
    tui: TuiCellRenderer,
) -> None:
    """Register headless 2D Pillow, vector SVG, and terminal TUI renderers for a chart `kind`."""
    _PILLOW_RENDERERS[kind] = pillow
    _SVG_RENDERERS[kind] = svg
    _TUI_RENDERERS[kind] = tui


def get_pillow_renderer(kind: str) -> PillowCellRenderer | None:
    return _PILLOW_RENDERERS.get(kind)


def get_svg_renderer(kind: str) -> SvgCellRenderer | None:
    return _SVG_RENDERERS.get(kind)


def get_tui_renderer(kind: str) -> TuiCellRenderer | None:
    return _TUI_RENDERERS.get(kind)


class Visual:
    """Level-1 root base class for all Fluxio visualizations.

    Can be used standalone (`v.show()`, `print(v)`, `v.save(...)`, Jupyter inline)
    or placed inside a multi-cell `fx.Figure(rows, cols)` container.
    """

    kind: str = "visual"

    def __init__(
        self,
        *,
        label: str = "",
        description: str = "",
        color: str | None = None,
        title: str = "",
        subtitle: str = "",
        theme: str = "dark",
        style: Mapping[str, Any] | None = None,
        size: tuple[int, int] = (780, 360),
        fps: int = 60,
        toolbar: bool | dict[str, bool] = True,
        row: int = 0,
        col: int = 0,
        row_span: int = 1,
        col_span: int = 1,
    ) -> None:
        self.id = f"cell_{uuid.uuid4().hex[:6]}"
        self.row = int(row)
        self.col = int(col)
        self.row_span = max(1, int(row_span))
        self.col_span = max(1, int(col_span))
        self.label = label
        self.description = description
        self.color = color

        # Standalone container metadata
        self.title = title
        self.subtitle = subtitle
        self.theme_name = theme
        self.size = (int(size[0]), int(size[1]))
        self.fps = max(1, int(fps))
        self.toolbar = toolbar

        self._style_overrides: dict[str, Any] = {}
        self._figure_style: dict[str, Any] = {}
        self._standalone_fig: Figure | None = None

        if style:
            self.style(**dict(style))
        else:
            resolve_theme(self.theme_name, None)

    def style(self, **kwargs: Any) -> Visual:
        """Customize aesthetics for this visual (chainable; supports both cell & standalone keys)."""
        for k, v in kwargs.items():
            if v is None:
                continue
            if k == "theme":
                self.theme_name = str(v)
            elif k in _FIGURE_ONLY_STYLE_KEYS:
                self._figure_style[k] = v
            else:
                self._style_overrides[k] = v

        # Validate combined style immediately
        resolve_theme(self.theme_name, {**self._figure_style, **self._style_overrides})
        return self

    def _apply_slot_defaults(self, slot_style: Mapping[str, Any]) -> None:
        """Apply `fig[row, col].style(...)` defaults without clobbering explicit visual overrides."""
        merged = dict(slot_style)
        merged.update(self._style_overrides)
        self._style_overrides = merged

    @property
    def is_dynamic(self) -> bool:
        return False

    def reset_cursor(self) -> None:
        """Reset any stateful stream/generator cursors to t=0."""

    def evaluate_tick_update(
        self,
        t: float,
        step_index: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def to_dict(
        self,
        *,
        theme_dict: Mapping[str, Any],
        t: float = 0.0,
        step_index: int | None = 0,
        bake_duration: float | None = None,
        fps: int = 30,
    ) -> dict[str, Any]:
        raise NotImplementedError

    # --- Standalone Figure capabilities (1x1 wrapper) ---

    def _get_standalone_figure(self) -> Figure:
        from ..figure import Figure

        combined_style = {**self._figure_style, **self._style_overrides}
        if self._standalone_fig is None:
            fig = Figure(
                rows=1,
                cols=1,
                title=self.title,
                subtitle=self.subtitle,
                theme=self.theme_name,
                style=combined_style,
                size=self.size,
                fps=self.fps,
                toolbar=self.toolbar,
            )
            # Attach without mutating grid coordinates used in any external parent Figure
            saved_pos = (self.id, self.row, self.col, self.row_span, self.col_span)
            fig.cells.append(self)
            fig._occupied.add((0, 0))
            (self.id, self.row, self.col, self.row_span, self.col_span) = saved_pos
            self._standalone_fig = fig
        else:
            fig = self._standalone_fig
            fig.title = self.title
            fig.subtitle = self.subtitle
            fig.theme_name = self.theme_name
            fig.size = self.size
            fig.fps = self.fps
            fig.style.clear()
            fig.style.update(combined_style)
        return fig

    def to_spec(
        self,
        *,
        t: float = 0.0,
        step_index: int | None = 0,
        bake_duration: float | None = None,
    ) -> dict[str, Any]:
        """Serialize this visual as a standalone 1x1 FigureSpec dictionary."""
        fig = self._get_standalone_figure()
        saved = (self.row, self.col, self.row_span, self.col_span)
        try:
            self.row, self.col, self.row_span, self.col_span = 0, 0, 1, 1
            return fig.to_spec(t=t, step_index=step_index, bake_duration=bake_duration)
        finally:
            self.row, self.col, self.row_span, self.col_span = saved

    def to_text(
        self,
        *,
        ansi: bool = True,
        width: int | None = None,
        t: float = 0.0,
        step_index: int | None = 0,
    ) -> str:
        """Render this visual as a formatted Unicode TUI string."""
        from ..text_render import render_spec_to_terminal

        spec = self.to_spec(t=t, step_index=step_index)
        return render_spec_to_terminal(spec, ansi=ansi, width=width)

    def reset_print(self) -> Visual:
        """Reset in-place terminal cursor state for manual `print(visual)` loops."""
        if self._standalone_fig is not None:
            self._standalone_fig.reset_print()
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
        """Display this visual in the terminal or Jupyter stdout, animating in-place if dynamic."""
        fig = self._get_standalone_figure()
        saved = (self.row, self.col, self.row_span, self.col_span)
        try:
            self.row, self.col, self.row_span, self.col_span = 0, 0, 1, 1
            fig.print(
                duration=duration,
                fps=fps,
                controls=controls,
                ansi=ansi,
                width=width,
            )
        finally:
            self.row, self.col, self.row_span, self.col_span = saved

    def __str__(self) -> str:
        fig = self._get_standalone_figure()
        saved = (self.row, self.col, self.row_span, self.col_span)
        try:
            self.row, self.col, self.row_span, self.col_span = 0, 0, 1, 1
            return str(fig)
        finally:
            self.row, self.col, self.row_span, self.col_span = saved

    def __repr__(self) -> str:
        lbl = f" '{self.label or self.title}'" if (self.label or self.title) else ""
        return f"<fluxio.{self.__class__.__name__}{lbl}>"

    def _repr_html_(self) -> str:
        from ..html_export import render_jupyter_html

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
        """Open this visual in an interactive desktop window."""
        fig = self._get_standalone_figure()
        saved = (self.row, self.col, self.row_span, self.col_span)
        try:
            self.row, self.col, self.row_span, self.col_span = 0, 0, 1, 1
            return fig.show(
                backend=backend,
                block=block,
                host=host,
                port=port,
                close_after=close_after,
            )
        finally:
            self.row, self.col, self.row_span, self.col_span = saved

    def save(
        self,
        path: str | Path,
        *,
        duration: float = 3.0,
        fps: int | None = None,
        scale: float = 2.0,
    ) -> Path:
        """Export this visual to `.png`, `.svg`, `.gif`, `.mp4`, `.webm`, `.html`, `.txt`, or `.ans`."""
        fig = self._get_standalone_figure()
        saved = (self.row, self.col, self.row_span, self.col_span)
        try:
            self.row, self.col, self.row_span, self.col_span = 0, 0, 1, 1
            return fig.save(path, duration=duration, fps=fps, scale=scale)
        finally:
            self.row, self.col, self.row_span, self.col_span = saved
