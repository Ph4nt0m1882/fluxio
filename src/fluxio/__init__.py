"""Fluxio — Modern, lightweight, real-time visualization engine for Python & AI chatbots."""

from __future__ import annotations
from pathlib import Path
from .figure import Figure, FigureStyle, SubplotSlot
from .protocol import NumberCell, ToolbarConfig
from .text_render import render_spec_to_terminal
from .theme import (
    BUILTIN_THEMES,
    VALID_ACCENT_SIDES,
    VALID_VARIANTS,
    BackgroundImage,
    Gradient,
    resolve_cell_style,
    resolve_theme,
)
from .window import show

__version__ = "0.1.0"

__all__ = [
    "BUILTIN_THEMES",
    "VALID_ACCENT_SIDES",
    "VALID_VARIANTS",
    "BackgroundImage",
    "Figure",
    "FigureStyle",
    "Gradient",
    "NumberCell",
    "SubplotSlot",
    "ToolbarConfig",
    "render_spec_to_terminal",
    "resolve_cell_style",
    "resolve_theme",
    "save",
    "show",
]


def save(
    fig: Figure,
    path: str | Path,
    *,
    duration: float = 3.0,
    fps: int | None = None,
    scale: float = 2.0,
) -> Path:
    """Convenience function calling `fig.save(...)`."""
    return fig.save(path, duration=duration, fps=fps, scale=scale)
