"""Fluxio scene protocol and dynamic value evaluation."""

from __future__ import annotations
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from .theme import resolve_cell_style

NumberSource = int | float | Callable[[float], int | float] | Iterator[int | float]


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


@dataclass
class ToolbarConfig:
    enabled: bool = True
    zoom: bool = True
    capture: bool = True
    playback: bool = True
    fullscreen: bool = True

    def to_dict(self) -> dict[str, bool]:
        return {
            "enabled": self.enabled,
            "zoom": self.zoom,
            "capture": self.capture,
            "playback": self.playback,
            "fullscreen": self.fullscreen,
        }


@dataclass
class NumberCell:
    """Atomic numeric KPI / value display cell supporting static, callable, or generator sources."""

    id: str
    row: int
    col: int
    source: NumberSource
    label: str = ""
    unit: str = ""
    prefix: str = ""
    precision: int | None = None
    color: str | None = None
    description: str = ""
    row_span: int = 1
    col_span: int = 1
    _style_overrides: dict[str, Any] = field(default_factory=dict, repr=False)
    _history: list[float] = field(default_factory=list, init=False, repr=False)
    _exhausted: bool = field(default=False, init=False, repr=False)
    _step_cursor: int = field(default=0, init=False, repr=False)

    def style(self, **kwargs: Any) -> NumberCell:
        """Customize visual aesthetics specifically for this cell (chainable)."""
        for k, v in kwargs.items():
            if v is not None:
                self._style_overrides[k] = v
        return self

    @property
    def is_callable(self) -> bool:
        return callable(self.source)

    @property
    def is_iterator(self) -> bool:
        return isinstance(self.source, Iterator)

    @property
    def is_dynamic(self) -> bool:
        return self.is_callable or self.is_iterator

    def _pull_iterator_up_to(self, index: int) -> float:
        assert isinstance(self.source, Iterator)
        while len(self._history) <= index and not self._exhausted:
            try:
                nxt = float(next(self.source))
                self._history.append(nxt)
            except StopIteration:
                self._exhausted = True
                break
        if not self._history:
            return 0.0
        if index < len(self._history):
            return self._history[index]
        return self._history[-1]

    def evaluate_at(self, t: float, step_index: int | None = None) -> float:
        """Evaluate the numeric cell at time `t` (seconds) or sequential step `step_index`."""
        if self.is_callable:
            fn = self.source
            assert callable(fn)
            return float(fn(float(t)))
        if self.is_iterator:
            if step_index is None:
                idx = self._step_cursor
                self._step_cursor += 1
            else:
                idx = step_index
            return self._pull_iterator_up_to(idx)
        return float(self.source)

    def reset_cursor(self) -> None:
        self._step_cursor = 0

    def sample_frames(self, duration: float, fps: int) -> list[float] | None:
        if not self.is_dynamic:
            return None
        count = max(1, int(round(duration * fps)))
        return [self.evaluate_at(i / fps, step_index=i) for i in range(count)]

    def to_dict(
        self,
        *,
        theme_dict: Mapping[str, Any],
        t: float = 0.0,
        step_index: int | None = 0,
        bake_duration: float | None = None,
        fps: int = 30,
    ) -> dict[str, Any]:
        frames = (
            self.sample_frames(bake_duration, fps)
            if (bake_duration is not None and self.is_dynamic)
            else None
        )
        val = frames[0] if frames else self.evaluate_at(t, step_index=step_index)
        resolved = resolve_cell_style(theme_dict, self._style_overrides, self.color)

        return {
            "id": self.id,
            "row": self.row,
            "col": self.col,
            "row_span": self.row_span,
            "col_span": self.col_span,
            "kind": "number",
            "label": self.label,
            "value": val,
            "formatted": format_number_value(val, self.precision, self.prefix),
            "unit": self.unit,
            "precision": self.precision,
            "prefix": self.prefix,
            "color": self.color,
            "style": dict(self._style_overrides) if self._style_overrides else None,
            "resolved_style": resolved,
            "description": self.description,
            "dynamic": self.is_dynamic,
            "frames": frames,
        }
