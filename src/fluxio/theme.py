"""Visual themes, variants (classic, reverse, text), backgrounds, adaptive veils, and cell cascade."""

from __future__ import annotations
import base64
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from PIL import Image, ImageColor

VALID_ACCENT_SIDES = ("left", "right", "top", "bottom", "none")
VALID_VARIANTS = ("classic", "reverse", "text")
MONOSPACE_STACK = "'Noto Sans Mono', 'DejaVu Sans Mono', 'JetBrains Mono', 'Fira Code', ui-monospace, monospace"

PRESET_BASES: dict[str, dict[str, Any]] = {
    "dark": {
        "name": "dark",
        "background": "#0b1120",
        "accent": "#38bdf8",
        "radius": 14,
        "padding": 24,
        "gap": 16,
    },
    "light": {
        "name": "light",
        "background": "#f8fafc",
        "accent": "#2563eb",
        "radius": 14,
        "padding": 24,
        "gap": 16,
    },
    "presentation": {
        "name": "presentation",
        "background": "#ffffff",
        "accent": "#1d4ed8",
        "radius": 12,
        "padding": 28,
        "gap": 20,
    },
}

BUILTIN_THEMES = PRESET_BASES


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    rgb = ImageColor.getrgb(color)
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def hex_luminance(color: str) -> float:
    """Compute WCAG relative luminance in [0.0, 1.0] for an RGB/hex color string."""
    r8, g8, b8 = hex_to_rgb(color)

    def _lin(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r8) + 0.7152 * _lin(g8) + 0.0722 * _lin(b8)


def contrast_ink_for_accent(accent_hex: str) -> str:
    return "#ffffff" if hex_luminance(accent_hex) < 0.48 else "#090d16"


@dataclass
class Gradient:
    """Linear or radial multi-stop background gradient."""

    colors: Sequence[str]
    angle: float = 135.0
    kind: str = "linear"

    def __post_init__(self) -> None:
        if not self.colors:
            raise ValueError("Gradient requires at least one color stop.")
        if self.kind not in ("linear", "radial"):
            raise ValueError("Gradient kind must be 'linear' or 'radial'.")
        for c in self.colors:
            hex_to_rgb(c)

    def luminance(self) -> float:
        return sum(hex_luminance(c) for c in self.colors) / len(self.colors)

    def to_spec(self) -> dict[str, Any]:
        return {
            "type": "gradient",
            "kind": self.kind,
            "angle": float(self.angle),
            "stops": list(self.colors),
        }


@dataclass
class BackgroundImage:
    """Self-contained background image (auto-encoded to base64 for standalone HTML & Jupyter)."""

    source: str | Path | bytes
    fit: str = "cover"
    opacity: float = 1.0
    overlay: str | None = None
    overlay_opacity: float = 0.0

    def __post_init__(self) -> None:
        if self.fit not in ("cover", "contain", "stretch"):
            raise ValueError(
                "BackgroundImage fit must be 'cover', 'contain', or 'stretch'."
            )
        self._data_url, self._luminance = self._load_and_analyze(self.source)

    @staticmethod
    def _load_and_analyze(src: str | Path | bytes) -> tuple[str, float]:
        if isinstance(src, str) and src.startswith("data:image/"):
            _, b64 = src.split(",", 1)
            raw = base64.b64decode(b64)
            data_url = src
        elif isinstance(src, bytes):
            raw = src
            data_url = f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"
        else:
            p = Path(src)
            if not p.exists():
                raise FileNotFoundError(f"Background image not found: {p}")
            raw = p.read_bytes()
            ext = p.suffix.lower().lstrip(".")
            mime = "jpeg" if ext in ("jpg", "jpeg") else (ext or "png")
            data_url = (
                f"data:image/{mime};base64,{base64.b64encode(raw).decode('ascii')}"
            )

        with Image.open(io.BytesIO(raw)) as img:
            thumb = img.convert("RGB").resize(
                (8, 8), resample=Image.Resampling.BILINEAR
            )
            raw_bytes = thumb.tobytes()
            n_px = max(1, len(raw_bytes) // 3)
            total = 0.0
            for i in range(0, len(raw_bytes), 3):
                r, g, b = raw_bytes[i], raw_bytes[i + 1], raw_bytes[i + 2]
                total += hex_luminance(f"#{r:02x}{g:02x}{b:02x}")
            avg_lum = total / n_px
        return data_url, avg_lum

    def luminance(self) -> float:
        lum = self._luminance
        if self.overlay and self.overlay_opacity > 0:
            a = max(0.0, min(1.0, float(self.overlay_opacity)))
            lum = lum * (1.0 - a) + hex_luminance(self.overlay) * a
        return lum

    def to_spec(self) -> dict[str, Any]:
        return {
            "type": "image",
            "data_url": self._data_url,
            "fit": self.fit,
            "opacity": max(0.0, min(1.0, float(self.opacity))),
            "overlay": self.overlay,
            "overlay_opacity": max(0.0, min(1.0, float(self.overlay_opacity))),
            "luminance": round(self.luminance(), 4),
        }


def _normalize_background(
    bg_input: Any,
    transparent_flag: bool,
    fallback_hex: str,
) -> tuple[str, dict[str, Any], bool, float]:
    if bg_input == "transparent":
        return fallback_hex, {"type": "transparent"}, True, hex_luminance(fallback_hex)

    if isinstance(bg_input, Gradient):
        first_hex = bg_input.colors[0]
        spec = {"type": "transparent"} if transparent_flag else bg_input.to_spec()
        return first_hex, spec, transparent_flag, bg_input.luminance()

    if isinstance(bg_input, BackgroundImage):
        spec = {"type": "transparent"} if transparent_flag else bg_input.to_spec()
        return fallback_hex, spec, transparent_flag, bg_input.luminance()

    if isinstance(bg_input, Mapping):
        btype = bg_input.get("type", "solid")
        if btype == "transparent" or transparent_flag:
            col = str(bg_input.get("color", fallback_hex))
            return col, {"type": "transparent"}, True, hex_luminance(col)
        if btype == "gradient":
            stops = list(bg_input.get("stops") or [fallback_hex])
            lum = sum(hex_luminance(c) for c in stops) / len(stops)
            return stops[0], dict(bg_input), False, lum
        if btype == "image":
            lum = float(bg_input.get("luminance", 0.5))
            return fallback_hex, dict(bg_input), False, lum
        col = str(bg_input.get("color", fallback_hex))
        return col, {"type": "solid", "color": col}, False, hex_luminance(col)

    if isinstance(bg_input, str):
        spec = (
            {"type": "transparent"}
            if transparent_flag
            else {"type": "solid", "color": bg_input}
        )
        return bg_input, spec, transparent_flag, hex_luminance(bg_input)

    spec = (
        {"type": "transparent"}
        if transparent_flag
        else {"type": "solid", "color": fallback_hex}
    )
    return fallback_hex, spec, transparent_flag, hex_luminance(fallback_hex)


def resolve_theme(
    theme: str = "dark",
    style: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve global Figure theme + user overrides including `variant` (classic, reverse, text)."""
    s = dict(style) if style else {}
    effective_theme = str(s.get("theme") or theme)
    if effective_theme not in PRESET_BASES:
        valid = ", ".join(sorted(PRESET_BASES))
        raise ValueError(f"Unknown theme '{effective_theme}'. Expected one of: {valid}")

    variant = str(s.get("variant", "classic"))
    if variant not in VALID_VARIANTS:
        raise ValueError(
            f"Invalid variant '{variant}'. Expected one of: {', '.join(VALID_VARIANTS)}"
        )

    preset = PRESET_BASES[effective_theme]
    default_bg = "#0a0e14" if variant == "text" else preset["background"]
    transparent_flag = bool(s.get("transparent", False))
    bg_hex, bg_spec, is_trans, lum = _normalize_background(
        s.get("background"), transparent_flag, default_bg
    )

    accent_side = str(s.get("accent_side", "top"))
    if accent_side not in VALID_ACCENT_SIDES:
        raise ValueError(
            f"Invalid accent_side '{accent_side}'. Expected one of: {', '.join(VALID_ACCENT_SIDES)}"
        )

    is_dark = lum < 0.5
    auto_surface = "#ffffff" if is_dark else "#0f172a"
    auto_surface_opacity = 1.0 if variant == "reverse" else (0.10 if is_dark else 0.08)
    auto_text = "#f8fafc" if is_dark else "#0f172a"
    auto_muted = "#cbd5e1" if is_dark else "#475569"

    accent = str(s.get("accent") or preset["accent"])
    rev_ink = contrast_ink_for_accent(accent)
    text = str(s.get("text") or auto_text)
    muted = str(s.get("muted") or auto_muted)

    default_text_op = 0.90 if variant == "reverse" else 1.0
    text_opacity = float(s.get("text_opacity", default_text_op))
    muted_opacity = round(text_opacity * 0.75, 3) if variant == "reverse" else 1.0

    default_font = (
        MONOSPACE_STACK
        if variant == "text"
        else "Inter, 'Noto Sans', system-ui, -apple-system, sans-serif"
    )
    default_radius = 8.0 if variant == "text" else float(preset["radius"])

    return {
        "name": effective_theme,
        "variant": variant,
        "background": bg_hex,
        "background_spec": bg_spec,
        "transparent": is_trans,
        "padding": float(s.get("padding", preset["padding"])),
        "gap": float(s.get("gap", preset["gap"])),
        "hover_ms": float(s.get("hover_ms", 200)),
        "title_color": str(s.get("title_color") or text),
        "subtitle_color": str(s.get("subtitle_color") or muted),
        "surface": str(s.get("surface") or auto_surface),
        "surface_opacity": float(s.get("surface_opacity", auto_surface_opacity)),
        "border": str(s.get("border") or accent),
        "border_opacity": float(s.get("border_opacity", 0.45)),
        "border_width": float(s.get("border_width", 1.6)),
        "hover_border_width": float(s.get("hover_border_width", 2.6)),
        "radius": float(s.get("radius", default_radius)),
        "accent": accent,
        "accent_side": accent_side,
        "accent_width": float(s.get("accent_width", 7.0)),
        "text": text,
        "text_opacity": text_opacity,
        "muted": muted,
        "muted_opacity": muted_opacity,
        "unit_color": str(s.get("unit_color") or accent),
        "reverse_ink": rev_ink,
        "font": str(s.get("font") or default_font),
        "font_scale": float(s.get("font_scale", 1.0)),
    }


def resolve_cell_style(
    theme_dict: Mapping[str, Any],
    cell_style: Mapping[str, Any] | None = None,
    legacy_color: str | None = None,
) -> dict[str, Any]:
    """Cascade global resolved theme down to a specific cell's style overrides."""
    cs = dict(cell_style) if cell_style else {}
    variant = str(cs.get("variant") or theme_dict["variant"])
    if variant not in VALID_VARIANTS:
        raise ValueError(
            f"Invalid variant '{variant}'. Expected one of: {', '.join(VALID_VARIANTS)}"
        )

    side = str(cs.get("accent_side") or theme_dict["accent_side"])
    if side not in VALID_ACCENT_SIDES:
        raise ValueError(
            f"Invalid accent_side '{side}'. Expected one of: {', '.join(VALID_ACCENT_SIDES)}"
        )

    accent = str(cs.get("accent") or legacy_color or theme_dict["accent"])
    rev_ink = contrast_ink_for_accent(accent)
    text = str(cs.get("text") or legacy_color or theme_dict["text"])
    border = str(
        cs.get("border")
        or (accent if (cs.get("accent") or legacy_color) else theme_dict["border"])
    )

    if "surface_opacity" in cs and cs["surface_opacity"] is not None:
        surf_op = float(cs["surface_opacity"])
    elif variant == "reverse" and theme_dict["variant"] != "reverse":
        surf_op = 1.0
    else:
        surf_op = float(theme_dict["surface_opacity"])

    if "text_opacity" in cs and cs["text_opacity"] is not None:
        txt_op = float(cs["text_opacity"])
    elif variant == "reverse" and theme_dict["variant"] != "reverse":
        txt_op = 0.90
    else:
        txt_op = float(theme_dict["text_opacity"])

    muted_op = round(txt_op * 0.75, 3) if variant == "reverse" else 1.0

    if "radius" in cs and cs["radius"] is not None:
        rad = float(cs["radius"])
    elif variant == "text" and theme_dict["variant"] != "text":
        rad = 8.0
    else:
        rad = float(theme_dict["radius"])

    font = str(
        cs.get("font")
        or (
            MONOSPACE_STACK
            if variant == "text" and theme_dict["variant"] != "text"
            else theme_dict["font"]
        )
    )

    return {
        "variant": variant,
        "surface": str(cs.get("surface") or theme_dict["surface"]),
        "surface_opacity": surf_op,
        "border": border,
        "border_opacity": float(
            cs["border_opacity"]
            if "border_opacity" in cs and cs["border_opacity"] is not None
            else theme_dict["border_opacity"]
        ),
        "border_width": float(
            cs["border_width"]
            if "border_width" in cs and cs["border_width"] is not None
            else theme_dict["border_width"]
        ),
        "hover_border_width": float(
            cs["hover_border_width"]
            if "hover_border_width" in cs and cs["hover_border_width"] is not None
            else theme_dict["hover_border_width"]
        ),
        "radius": rad,
        "accent": accent,
        "accent_side": side,
        "accent_width": float(
            cs["accent_width"]
            if "accent_width" in cs and cs["accent_width"] is not None
            else theme_dict["accent_width"]
        ),
        "text": text,
        "text_opacity": txt_op,
        "muted": str(cs.get("muted") or theme_dict["muted"]),
        "muted_opacity": muted_op,
        "unit_color": str(cs.get("unit_color") or accent),
        "reverse_ink": rev_ink,
        "font": font,
        "font_scale": float(
            cs["font_scale"]
            if "font_scale" in cs and cs["font_scale"] is not None
            else theme_dict["font_scale"]
        ),
    }
