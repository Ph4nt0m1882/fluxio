"""Fluxio scene protocol configuration and re-exports."""

from __future__ import annotations
from dataclasses import dataclass
from .charts import Number, NumberSource, Visual, format_number_value

# Backwards-compatible alias
NumberCell = Number


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


__all__ = [
    "Number",
    "NumberCell",
    "NumberSource",
    "ToolbarConfig",
    "Visual",
    "format_number_value",
]
