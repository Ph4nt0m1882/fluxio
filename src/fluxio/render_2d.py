"""Shared headless 2D & SVG figure renderer delegating cell content to modular `charts/` renderers."""

from __future__ import annotations
import base64
import html
import io
import math
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any
from PIL import Image, ImageColor, ImageDraw, ImageFont
from .charts.base import get_pillow_renderer, get_svg_renderer
from .text_render import build_block_matrix, split_block_renderable
from .theme import hex_to_rgb, resolve_cell_style

if TYPE_CHECKING:
    from .figure import Figure

_FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
_FONT_CANDIDATES_REGULAR = [
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
_MONO_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
]
_MONO_CANDIDATES_REGULAR = [
    "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf",
]


@lru_cache(maxsize=64)
def _load_font(
    size: int,
    bold: bool = False,
    mono: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if mono:
        candidates = _MONO_CANDIDATES_BOLD if bold else _MONO_CANDIDATES_REGULAR
    else:
        candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=max(8, size))
            except OSError:
                continue
    return ImageFont.load_default(size=max(8, size))


def _rgba(hex_color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(hex_color)
    a = int(round(max(0.0, min(1.0, opacity)) * 255))
    return (r, g, b, a)


def _build_color_lut(stops: list[str], steps: int = 512) -> list[tuple[int, int, int]]:
    rgbs = [hex_to_rgb(c) for c in stops]
    if len(rgbs) == 1:
        return [rgbs[0]] * steps
    lut: list[tuple[int, int, int]] = []
    n_seg = len(rgbs) - 1
    for i in range(steps):
        pos = (i / (steps - 1)) * n_seg
        seg = min(n_seg - 1, int(pos))
        frac = pos - seg
        r1, g1, b1 = rgbs[seg]
        r2, g2, b2 = rgbs[seg + 1]
        lut.append(
            (
                int(round(r1 + (r2 - r1) * frac)),
                int(round(g1 + (g2 - g1) * frac)),
                int(round(b1 + (b2 - b1) * frac)),
            )
        )
    return lut


def _render_gradient_rgba(
    w: int,
    h: int,
    stops: list[str],
    angle: float,
    kind: str,
) -> Image.Image:
    lut = _build_color_lut(stops, 512)
    max_idx = len(lut) - 1
    gw, gh = 192, 192
    buf = bytearray(gw * gh * 3)

    if kind == "radial":
        max_r = math.hypot(w, h) * 0.6
        xs = [((ix + 0.5) / gw - 0.5) * w for ix in range(gw)]
        ys = [((iy + 0.5) / gh - 0.5) * h for iy in range(gh)]
        pos = 0
        for dy in ys:
            dy2 = dy * dy
            for dx in xs:
                t = min(1.0, math.sqrt(dx * dx + dy2) / max(1e-6, max_r))
                r, g, b = lut[int(t * max_idx)]
                buf[pos] = r
                buf[pos + 1] = g
                buf[pos + 2] = b
                pos += 3
    else:
        rad = ((angle - 90.0) * math.pi) / 180.0
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)
        half_len = max(1e-6, (abs(w * cos_r) + abs(h * sin_r)) / 2.0)
        tx = [
            (((ix + 0.5) / gw - 0.5) * w * cos_r) / (2.0 * half_len) for ix in range(gw)
        ]
        ty = [
            (((iy + 0.5) / gh - 0.5) * h * sin_r) / (2.0 * half_len) for iy in range(gh)
        ]
        pos = 0
        for vy in ty:
            base = 0.5 + vy
            for vx in tx:
                t = max(0.0, min(1.0, base + vx))
                r, g, b = lut[int(t * max_idx)]
                buf[pos] = r
                buf[pos + 1] = g
                buf[pos + 2] = b
                pos += 3

    small = Image.frombytes("RGB", (gw, gh), bytes(buf))
    return small.resize((w, h), resample=Image.Resampling.BICUBIC).convert("RGBA")


def _render_background_rgba(theme: dict[str, Any], w: int, h: int) -> Image.Image:
    bg = theme.get("background_spec") or {"type": "solid", "color": theme["background"]}
    if theme.get("transparent") or bg.get("type") == "transparent":
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))

    btype = bg.get("type", "solid")
    if btype == "gradient":
        stops = list(bg.get("stops") or [theme["background"]])
        return _render_gradient_rgba(
            w,
            h,
            stops,
            float(bg.get("angle", 135.0)),
            str(bg.get("kind", "linear")),
        )

    if btype == "image":
        canvas = Image.new("RGBA", (w, h), _rgba(theme["background"], 1.0))
        data_url = str(bg.get("data_url", ""))
        if "," in data_url:
            raw = base64.b64decode(data_url.split(",", 1)[1])
            with Image.open(io.BytesIO(raw)) as src_im:
                im = src_im.convert("RGBA")
                iw, ih = im.size
                fit = str(bg.get("fit", "cover"))
                if fit == "stretch":
                    layer = im.resize((w, h), resample=Image.Resampling.LANCZOS)
                else:
                    scale = (
                        min(w / iw, h / ih) if fit == "contain" else max(w / iw, h / ih)
                    )
                    dw = max(1, int(round(iw * scale)))
                    dh = max(1, int(round(ih * scale)))
                    resized = im.resize((dw, dh), resample=Image.Resampling.LANCZOS)
                    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                    layer.paste(resized, ((w - dw) // 2, (h - dh) // 2))

                opacity = max(0.0, min(1.0, float(bg.get("opacity", 1.0))))
                if opacity < 1.0:
                    alpha_ch = layer.split()[3].point(lambda p: int(round(p * opacity)))
                    layer.putalpha(alpha_ch)
                canvas = Image.alpha_composite(canvas, layer)

        ov_col = bg.get("overlay")
        ov_op = float(bg.get("overlay_opacity", 0.0))
        if ov_col and ov_op > 0:
            ov_layer = Image.new("RGBA", (w, h), _rgba(str(ov_col), ov_op))
            canvas = Image.alpha_composite(canvas, ov_layer)
        return canvas

    col = str(bg.get("color", theme["background"]))
    return Image.new("RGBA", (w, h), _rgba(col, 1.0))


def _crescent_inner_box(
    w: float,
    h: float,
    side: str,
    accent_w: float,
) -> tuple[float, float, float, float] | None:
    if side == "none" or accent_w <= 0:
        return None
    t = max(0.0, min(accent_w, w * 0.45, h * 0.45))
    if side == "left":
        return (t, 0.0, w, h)
    if side == "right":
        return (0.0, 0.0, w - t, h)
    if side == "top":
        return (0.0, t, w, h)
    if side == "bottom":
        return (0.0, 0.0, w, h - t)
    return None


def _svg_rrect_subpath(x: float, y: float, w: float, h: float, r: float) -> str:
    R = max(0.0, min(r, w / 2.0, h / 2.0))
    return (
        f"M {x + R:.2f} {y:.2f} "
        f"L {x + w - R:.2f} {y:.2f} "
        f"A {R:.2f} {R:.2f} 0 0 1 {x + w:.2f} {y + R:.2f} "
        f"L {x + w:.2f} {y + h - R:.2f} "
        f"A {R:.2f} {R:.2f} 0 0 1 {x + w - R:.2f} {y + h:.2f} "
        f"L {x + R:.2f} {y + h:.2f} "
        f"A {R:.2f} {R:.2f} 0 0 1 {x:.2f} {y + h - R:.2f} "
        f"L {x:.2f} {y + R:.2f} "
        f"A {R:.2f} {R:.2f} 0 0 1 {x + R:.2f} {y:.2f} Z"
    )


def _svg_tapered_accent_path(
    x: float,
    y: float,
    w: float,
    h: float,
    radius: float,
    side: str,
    accent_w: float,
) -> str:
    box = _crescent_inner_box(w, h, side, accent_w)
    if box is None:
        return ""
    ix0, iy0, ix1, iy1 = box
    outer = _svg_rrect_subpath(x, y, w, h, radius)
    inner = _svg_rrect_subpath(x + ix0, y + iy0, ix1 - ix0, iy1 - iy0, radius)
    return f"{outer} {inner}"


def _compute_fig_ui_scale(width: float, height: float) -> float:
    r = min(width / 960.0, height / 560.0)
    return min(2.2, 1.0 + (r - 1.0) * 0.55) if r > 1.05 else 1.0


def _compute_header_height(
    spec: dict[str, Any],
    width: float = 900.0,
    height: float = 520.0,
) -> int:
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    if not title and not subtitle:
        return 0
    s = float(spec["theme"].get("font_scale", 1.0)) * _compute_fig_ui_scale(
        width, height
    )
    return int(round((56 if (title and subtitle) else 38) * s))


def _compute_grid_rects(
    spec: dict[str, Any],
    width: float,
    height: float,
) -> dict[str, tuple[float, float, float, float]]:
    theme = spec["theme"]
    padding = float(theme["padding"])
    gap = float(theme["gap"])
    rows = max(1, int(spec["rows"]))
    cols = max(1, int(spec["cols"]))
    header_h = float(_compute_header_height(spec, width, height))

    inner_x = padding
    inner_y = padding + header_h
    inner_w = max(40.0, width - padding * 2)
    inner_h = max(40.0, height - padding * 2 - header_h)

    unit_w = (inner_w - gap * max(0, cols - 1)) / cols
    unit_h = (inner_h - gap * max(0, rows - 1)) / rows

    rects: dict[str, tuple[float, float, float, float]] = {}
    for cell in spec["cells"]:
        col = int(cell["col"])
        row = int(cell["row"])
        c_span = max(1, min(int(cell.get("col_span", 1)), cols - col))
        r_span = max(1, min(int(cell.get("row_span", 1)), rows - row))
        x = inner_x + col * (unit_w + gap)
        y = inner_y + row * (unit_h + gap)
        w = max(10.0, unit_w * c_span + gap * (c_span - 1))
        h = max(10.0, unit_h * r_span + gap * (r_span - 1))
        rects[cell["id"]] = (x, y, w, h)
    return rects


def _paste_ring_and_crescent(
    card_layer: Image.Image,
    cw_i: int,
    ch_i: int,
    radius: float,
    bw: float,
    ring_rgba: tuple[int, int, int, int] | None,
    side: str,
    accent_w: float,
    crescent_rgba: tuple[int, int, int, int],
) -> Image.Image:
    if ring_rgba is not None and bw > 0:
        ring_mask = Image.new("L", (cw_i, ch_i), 0)
        rm_draw = ImageDraw.Draw(ring_mask)
        rm_draw.rounded_rectangle([0, 0, cw_i - 1, ch_i - 1], radius=radius, fill=255)
        rm_draw.rounded_rectangle(
            [bw, bw, cw_i - 1 - bw, ch_i - 1 - bw],
            radius=max(0.0, radius - bw),
            fill=0,
        )
        ring_fill = Image.new("RGBA", (cw_i, ch_i), ring_rgba)
        clipped_ring = Image.new("RGBA", (cw_i, ch_i), (0, 0, 0, 0))
        clipped_ring.paste(ring_fill, (0, 0), mask=ring_mask)
        card_layer = Image.alpha_composite(card_layer, clipped_ring)

    inner_box = _crescent_inner_box(float(cw_i), float(ch_i), side, accent_w)
    if inner_box is not None:
        bx0, by0, bx1, by1 = inner_box
        crescent_mask = Image.new("L", (cw_i, ch_i), 0)
        cm_draw = ImageDraw.Draw(crescent_mask)
        cm_draw.rounded_rectangle([0, 0, cw_i - 1, ch_i - 1], radius=radius, fill=255)
        cm_draw.rounded_rectangle(
            [bx0, by0, bx1 - 1, by1 - 1],
            radius=min(radius, (bx1 - bx0) / 2.0, (by1 - by0) / 2.0),
            fill=0,
        )
        acc_fill = Image.new("RGBA", (cw_i, ch_i), crescent_rgba)
        crescent_layer = Image.new("RGBA", (cw_i, ch_i), (0, 0, 0, 0))
        crescent_layer.paste(acc_fill, (0, 0), mask=crescent_mask)
        card_layer = Image.alpha_composite(card_layer, crescent_layer)

    return card_layer


def render_spec_to_image(spec: dict[str, Any], scale: float = 1.0) -> Image.Image:
    """Render a FigureSpec dictionary to a Pillow RGBA Image via registered chart renderers."""
    # Ensure concrete chart modules are imported so their renderers are registered
    from . import charts as _charts  # noqa: F401

    base_w, base_h = spec["size"]
    theme = spec["theme"]
    is_text_theme = theme.get("variant") == "text"

    ss = 2.0
    s = scale * ss
    w = max(64, int(round(base_w * s)))
    h = max(64, int(round(base_h * s)))

    img = _render_background_rgba(theme, w, h)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pad = float(theme["padding"]) * s
    fig_ui = _compute_fig_ui_scale(base_w, base_h)
    fscale_global = float(theme.get("font_scale", 1.0)) * fig_ui
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    title_px = int(round(18 * fscale_global * s))
    sub_px = int(round(13 * fscale_global * s))

    if title:
        f_title = _load_font(title_px, bold=True, mono=is_text_theme)
        t_col = theme["accent"] if is_text_theme else theme["title_color"]
        prefix_t = "▸ " if is_text_theme else ""
        draw.text((pad, pad), f"{prefix_t}{title}", fill=_rgba(t_col), font=f_title)
    if subtitle:
        f_sub = _load_font(sub_px, bold=False, mono=is_text_theme)
        offset_y = pad + ((title_px + 6 * fig_ui * s) if title else 0)
        draw.text(
            (pad, offset_y), subtitle, fill=_rgba(theme["subtitle_color"]), font=f_sub
        )

    rects = _compute_grid_rects(spec, base_w, base_h)
    helpers = {
        "load_font": _load_font,
        "rgba": _rgba,
        "split_block_renderable": split_block_renderable,
        "build_block_matrix": build_block_matrix,
    }

    for cell in spec["cells"]:
        cs = cell.get("resolved_style") or resolve_cell_style(
            theme, cell.get("style"), cell.get("color")
        )
        variant = cs["variant"]
        rx, ry, rw, rh = rects[cell["id"]]
        x0, y0, cw, ch = rx * s, ry * s, rw * s, rh * s
        cw_i = max(4, int(round(cw)))
        ch_i = max(4, int(round(ch)))
        ix0 = int(round(x0))
        iy0 = int(round(y0))

        raw_rad = (
            min(10.0, float(cs["radius"])) if variant == "text" else float(cs["radius"])
        )
        radius = min(raw_rad * s, cw / 2.0, ch / 2.0)

        card_layer = Image.new("RGBA", (cw_i, ch_i), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(card_layer)

        if variant == "reverse":
            fill_col = _rgba(cs["accent"], float(cs["surface_opacity"]))
            cdraw.rounded_rectangle(
                [0, 0, cw_i - 1, ch_i - 1], radius=radius, fill=fill_col
            )
            bw = float(cs["border_width"]) * s
            rev_ink = cs["reverse_ink"]
            card_layer = _paste_ring_and_crescent(
                card_layer,
                cw_i,
                ch_i,
                radius,
                bw,
                _rgba(rev_ink, 0.20),
                str(cs["accent_side"]),
                float(cs["accent_width"]) * s,
                _rgba(rev_ink, 0.30),
            )
        elif variant == "text":
            cdraw.rounded_rectangle(
                [0, 0, cw_i - 1, ch_i - 1],
                radius=radius,
                fill=_rgba("#090d16", 0.74),
            )
            card_layer = _paste_ring_and_crescent(
                card_layer,
                cw_i,
                ch_i,
                radius,
                1.5 * s,
                _rgba(cs["border"], 0.48),
                str(cs["accent_side"]),
                max(4.0, float(cs["accent_width"]) * 0.75) * s,
                _rgba(cs["accent"], 1.0),
            )
        else:
            surf_alpha = float(cs["surface_opacity"])
            if surf_alpha > 0:
                cdraw.rounded_rectangle(
                    [0, 0, cw_i - 1, ch_i - 1],
                    radius=radius,
                    fill=_rgba(cs["surface"], surf_alpha),
                )
            bw = float(cs["border_width"]) * s
            ring_rgba = (
                _rgba(cs["border"], float(cs["border_opacity"]))
                if bw > 0 and float(cs["border_opacity"]) > 0
                else None
            )
            card_layer = _paste_ring_and_crescent(
                card_layer,
                cw_i,
                ch_i,
                radius,
                bw,
                ring_rgba,
                str(cs["accent_side"]),
                float(cs["accent_width"]) * s,
                _rgba(cs["accent"], 1.0),
            )

        renderer_fn = get_pillow_renderer(str(cell.get("kind", "number")))
        if renderer_fn is not None:
            txt_layer = Image.new("RGBA", (cw_i, ch_i), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(txt_layer)
            renderer_fn(
                tdraw,
                cell,
                cs,
                cw_i,
                ch_i,
                rw,
                rh,
                float(cs["font_scale"]),
                s,
                helpers,
            )
            card_layer = Image.alpha_composite(card_layer, txt_layer)

        overlay.alpha_composite(card_layer, dest=(ix0, iy0))

    img = Image.alpha_composite(img, overlay)
    target_w = max(16, int(round(base_w * scale)))
    target_h = max(16, int(round(base_h * scale)))
    return img.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)


def render_spec_to_svg(spec: dict[str, Any]) -> str:
    """Render a FigureSpec dictionary to crisp vector SVG via registered chart renderers."""
    from . import charts as _charts  # noqa: F401

    width, height = spec["size"]
    theme = spec["theme"]
    is_text_theme = theme.get("variant") == "text"
    font_family = html.escape(theme["font"], quote=True)
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
    ]

    bg = theme.get("background_spec") or {"type": "solid", "color": theme["background"]}
    if not theme.get("transparent", False) and bg.get("type") != "transparent":
        btype = bg.get("type", "solid")
        if btype == "gradient":
            stops = list(bg.get("stops") or [theme["background"]])
            if bg.get("kind") == "radial":
                parts.append(
                    '  <defs><radialGradient id="fx_bg_grad" cx="50%" cy="50%" r="65%">'
                )
                for idx, col in enumerate(stops):
                    pct = 0 if len(stops) == 1 else (idx / (len(stops) - 1)) * 100
                    parts.append(
                        f'    <stop offset="{pct:.1f}%" stop-color="{html.escape(col)}" />'
                    )
                parts.append("  </radialGradient></defs>")
            else:
                rad = ((float(bg.get("angle", 135.0)) - 90.0) * math.pi) / 180.0
                x1 = 50.0 - math.cos(rad) * 50.0
                y1 = 50.0 - math.sin(rad) * 50.0
                x2 = 50.0 + math.cos(rad) * 50.0
                y2 = 50.0 + math.sin(rad) * 50.0
                parts.append(
                    f'  <defs><linearGradient id="fx_bg_grad" x1="{x1:.1f}%" y1="{y1:.1f}%" '
                    f'x2="{x2:.1f}%" y2="{y2:.1f}%">'
                )
                for idx, col in enumerate(stops):
                    pct = 0 if len(stops) == 1 else (idx / (len(stops) - 1)) * 100
                    parts.append(
                        f'    <stop offset="{pct:.1f}%" stop-color="{html.escape(col)}" />'
                    )
                parts.append("  </linearGradient></defs>")
            parts.append(
                f'  <rect width="{width}" height="{height}" fill="url(#fx_bg_grad)" />'
            )
        elif btype == "image":
            parts.append(
                f'  <rect width="{width}" height="{height}" fill="{html.escape(theme["background"])}" />'
            )
            fit = bg.get("fit", "cover")
            par = (
                "none"
                if fit == "stretch"
                else ("xMidYMid meet" if fit == "contain" else "xMidYMid slice")
            )
            op = float(bg.get("opacity", 1.0))
            parts.append(
                f'  <image href="{html.escape(str(bg.get("data_url", "")), quote=True)}" '
                f'width="{width}" height="{height}" preserveAspectRatio="{par}" opacity="{op:.3f}" />'
            )
            if bg.get("overlay") and float(bg.get("overlay_opacity", 0.0)) > 0:
                parts.append(
                    f'  <rect width="{width}" height="{height}" fill="{html.escape(str(bg["overlay"]))}" '
                    f'fill-opacity="{float(bg["overlay_opacity"]):.3f}" />'
                )
        else:
            col = str(bg.get("color", theme["background"]))
            parts.append(
                f'  <rect width="{width}" height="{height}" fill="{html.escape(col)}" />'
            )

    pad = float(theme["padding"])
    fig_ui = _compute_fig_ui_scale(width, height)
    fscale_global = float(theme.get("font_scale", 1.0)) * fig_ui
    title_px = int(round(18 * fscale_global))
    sub_px = int(round(13 * fscale_global))
    if spec.get("title"):
        t_col = theme["accent"] if is_text_theme else theme["title_color"]
        t_pref = "▸ " if is_text_theme else ""
        parts.append(
            f'  <text x="{pad}" y="{pad + title_px * 0.9:.1f}" fill="{html.escape(t_col)}" '
            f'font-family="{font_family}" font-size="{title_px}" font-weight="700">'
            f"{html.escape(t_pref + spec['title'])}</text>"
        )
    if spec.get("subtitle"):
        sub_y = pad + (title_px + sub_px + 6 if spec.get("title") else sub_px)
        parts.append(
            f'  <text x="{pad}" y="{sub_y:.1f}" fill="{html.escape(theme["subtitle_color"])}" '
            f'font-family="{font_family}" font-size="{sub_px}">'
            f"{html.escape(spec['subtitle'])}</text>"
        )

    rects = _compute_grid_rects(spec, width, height)

    for idx, cell in enumerate(spec["cells"]):
        cs = cell.get("resolved_style") or resolve_cell_style(
            theme, cell.get("style"), cell.get("color")
        )
        variant = cs["variant"]
        rx, ry, rw, rh = rects[cell["id"]]
        radius = (
            min(10.0, float(cs["radius"])) if variant == "text" else float(cs["radius"])
        )
        clip_id = f"fx_clip_{idx}"

        parts.append(
            f'  <defs><clipPath id="{clip_id}">'
            f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" rx="{radius:.1f}" />'
            f"</clipPath></defs>"
        )

        is_rev = variant == "reverse"
        rev_ink = cs["reverse_ink"]
        surf_col = (
            cs["accent"]
            if is_rev
            else ("#090d16" if variant == "text" else cs["surface"])
        )
        surf_op = float(cs["surface_opacity"]) if variant != "text" else 0.74
        b_col = rev_ink if is_rev else cs["border"]
        b_op = 0.20 if is_rev else float(cs["border_opacity"])

        parts.append(
            f'  <rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
            f'rx="{radius:.1f}" fill="{html.escape(surf_col)}" fill-opacity="{surf_op:.3f}" '
            f'stroke="{html.escape(b_col)}" stroke-opacity="{b_op:.3f}" '
            f'stroke-width="{float(cs["border_width"]):.2f}" />'
        )

        acc_w = (
            max(4.0, float(cs["accent_width"]) * 0.75)
            if variant == "text"
            else float(cs["accent_width"])
        )
        d_path = _svg_tapered_accent_path(
            rx, ry, rw, rh, radius, str(cs["accent_side"]), acc_w
        )
        if d_path:
            c_col = rev_ink if is_rev else cs["accent"]
            c_op = 0.30 if is_rev else 1.0
            parts.append(
                f'  <path d="{d_path}" fill="{html.escape(c_col)}" fill-opacity="{c_op:.3f}" '
                f'fill-rule="evenodd" clip-path="url(#{clip_id})" />'
            )

        svg_fn = get_svg_renderer(str(cell.get("kind", "number")))
        if svg_fn is not None:
            parts.extend(svg_fn(cell, cs, rx, ry, rw, rh))

    parts.append("</svg>")
    return "\n".join(parts)


def save_png(fig: Figure, path: Path, scale: float = 2.0) -> None:
    spec = fig.to_spec(t=0.0, step_index=0)
    img = render_spec_to_image(spec, scale=scale)
    img.save(path, format="PNG")


def save_svg(fig: Figure, path: Path) -> None:
    spec = fig.to_spec(t=0.0, step_index=0)
    svg = render_spec_to_svg(spec)
    path.write_text(svg, encoding="utf-8")


def save_gif(
    fig: Figure,
    path: Path,
    *,
    duration: float = 3.0,
    fps: int = 20,
    scale: float = 1.0,
) -> None:
    n_frames = max(2, int(round(duration * fps)))
    bg_hex = fig.resolved_theme["background"]
    bg_rgb = ImageColor.getrgb(bg_hex)[:3]

    frames: list[Image.Image] = []
    for i in range(n_frames):
        t = i / fps
        spec = fig.to_spec(t=t, step_index=i)
        rgba = render_spec_to_image(spec, scale=scale)
        flat = Image.new("RGB", rgba.size, bg_rgb)
        flat.paste(rgba, mask=rgba.split()[3])
        frames.append(flat.quantize(colors=256, method=Image.Quantize.MEDIANCUT))

    frame_ms = max(20, int(round(1000 / fps)))
    frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=frame_ms,
        loop=0,
        optimize=False,
    )


def save_video(
    fig: Figure,
    path: Path,
    *,
    duration: float = 3.0,
    fps: int = 30,
    scale: float = 1.0,
) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError(
            "ffmpeg is required to export video files (.mp4/.webm), but was not found in PATH."
        )

    n_frames = max(2, int(round(duration * fps)))
    first_spec = fig.to_spec(t=0.0, step_index=0)
    sample_img = render_spec_to_image(first_spec, scale=scale)

    w = sample_img.width - (sample_img.width % 2)
    h = sample_img.height - (sample_img.height % 2)
    bg_rgb = ImageColor.getrgb(fig.resolved_theme["background"])[:3]

    ext = path.suffix.lower()
    codec_args = (
        ["-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p"]
        if ext == ".webm"
        else ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    )

    cmd = [
        ffmpeg_bin,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "-",
        *codec_args,
        str(path),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(n_frames):
            t = i / fps
            rgba = (
                sample_img
                if i == 0
                else render_spec_to_image(fig.to_spec(t=t, step_index=i), scale=scale)
            )
            if rgba.size != (w, h):
                rgba = rgba.crop((0, 0, w, h))
            rgb = Image.new("RGB", (w, h), bg_rgb)
            rgb.paste(rgba, mask=rgba.split()[3])
            proc.stdin.write(rgb.tobytes())
    finally:
        proc.stdin.close()

    stderr_out = (
        proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    )
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"ffmpeg video export failed (exit {ret}): {stderr_out}")
