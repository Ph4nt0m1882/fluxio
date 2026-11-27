"""Level-3 `Number` indicator chart (`Visual` -> `Indicator` -> `Number`) and its 3 renderers."""

from __future__ import annotations
import html
import math
from collections.abc import Callable, Iterator, Mapping
from typing import Any
from PIL import ImageDraw
from ..theme import MONOSPACE_STACK, resolve_cell_style
from .base import register_chart_renderers
from .families import Indicator

NumberSource = int | float | Callable[[float], int | float] | Iterator[int | float]


class Number(Indicator):
    """Numeric KPI / live metric card supporting static numbers, `f(t)` callables, and Python generators."""

    kind = "number"

    def __init__(
        self,
        value: NumberSource,
        *,
        label: str = "",
        unit: str = "",
        prefix: str = "",
        precision: int | None = None,
        color: str | None = None,
        description: str = "",
        title: str = "",
        subtitle: str = "",
        theme: str = "dark",
        style: Mapping[str, Any] | None = None,
        size: tuple[int, int] = (780, 340),
        fps: int = 60,
        toolbar: bool | dict[str, bool] = True,
        row: int = 0,
        col: int = 0,
        row_span: int = 1,
        col_span: int = 1,
    ) -> None:
        super().__init__(
            unit=unit,
            prefix=prefix,
            precision=precision,
            label=label,
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
        self.source = value
        self._history: list[float] = []
        self._exhausted = False
        self._step_cursor = 0

    @property
    def is_callable(self) -> bool:
        return callable(self.source)

    @property
    def is_iterator(self) -> bool:
        return isinstance(self.source, Iterator)

    @property
    def is_dynamic(self) -> bool:
        return self.is_callable or self.is_iterator

    def reset_cursor(self) -> None:
        self._step_cursor = 0

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

    def evaluate_tick_update(
        self,
        t: float,
        step_index: int | None = None,
    ) -> dict[str, Any]:
        val = self.evaluate_at(t, step_index=step_index)
        return {
            "id": self.id,
            "value": val,
            "formatted": self.format_value(val),
        }

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
            "kind": self.kind,
            "label": self.label,
            "value": val,
            "formatted": self.format_value(val),
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


# --- Modular Renderers for `kind == "number"` ---


def _render_number_pillow(
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
    split_block_renderable = helpers["split_block_renderable"]
    build_block_matrix = helpers["build_block_matrix"]

    if cs["variant"] == "text":
        r_ui = min(rw / 620.0, rh / 360.0)
        ui_scale = min(2.2, 1.0 + (r_ui - 1.0) * 0.52) if r_ui > 1.05 else 1.0
        pad_x = 18.0 * ui_scale * s
        pad_y = 14.0 * ui_scale * s
        accent_rgba = rgba(cs["accent"], 1.0)
        txt_rgba = rgba(cs["text"], float(cs["text_opacity"]))
        mut_rgba = rgba(cs["muted"], 1.0)

        label = cell.get("label", "")
        if label:
            f_lbl = load_font(int(round(13 * fscale * ui_scale * s)), bold=True, mono=True)
            w1 = tdraw.textlength("┤ ", font=f_lbl)
            w2 = tdraw.textlength(label, font=f_lbl)
            tdraw.text((pad_x, pad_y), "┤ ", fill=accent_rgba, font=f_lbl)
            tdraw.text(
                (pad_x + w1, pad_y), label, fill=rgba(cs["text"], 1.0), font=f_lbl
            )
            tdraw.text((pad_x + w1 + w2, pad_y), " ├", fill=accent_rgba, font=f_lbl)

        if cell.get("dynamic"):
            f_live = load_font(int(round(11 * ui_scale * s)), bold=True, mono=True)
            tdraw.text(
                (cw_i - pad_x, pad_y + 1 * s),
                "● LIVE",
                fill=rgba("#22c55e"),
                font=f_live,
                anchor="ra",
            )

        formatted = str(cell.get("formatted", cell.get("value", "")))
        prefix, core = split_block_renderable(formatted)
        matrix = build_block_matrix(core)
        max_avail_w = max(40.0 * s, cw_i - pad_x * 2)
        center_y = ch_i * (0.56 if label else 0.5)

        drew_blocks = False
        if matrix and len(matrix[0]) > 0 and rh >= 115:
            cols = len(matrix[0])
            unit_str = f" {cell['unit']}" if cell.get("unit") else ""
            unit_px = int(round(min(64.0, max(13.0, rh * 0.11)) * fscale * s))
            f_unit = load_font(unit_px, bold=True, mono=True)
            prefix_w = tdraw.textlength(f"{prefix} ", font=f_unit) if prefix else 0.0
            unit_w = (
                (tdraw.textlength(unit_str, font=f_unit) + 6 * ui_scale * s)
                if unit_str
                else 0.0
            )

            max_block_w = max(24.0 * s, max_avail_w - prefix_w - unit_w)
            cell_px = math.floor(
                min(
                    (rh * 0.40 * fscale * s) / 6.0,
                    max_block_w / cols,
                    48.0 * s,
                )
            )
            if cell_px >= int(4 * s):
                drew_blocks = True
                grid_w = cols * cell_px
                grid_h = 6 * cell_px
                total_w = prefix_w + grid_w + unit_w
                start_x = (cw_i - total_w) / 2.0
                top_y = center_y - grid_h / 2.0
                gap = max(1, int(round(1.0 * s))) if cell_px >= int(7 * s) else 0

                if prefix:
                    tdraw.text(
                        (start_x, center_y),
                        f"{prefix} ",
                        fill=accent_rgba,
                        font=f_unit,
                        anchor="lm",
                    )
                gx0 = start_x + prefix_w
                for r in range(6):
                    row_str = matrix[r]
                    for c in range(cols):
                        if row_str[c] == "1":
                            bx = int(round(gx0 + c * cell_px))
                            by = int(round(top_y + r * cell_px))
                            bw_b = max(1, cell_px - gap)
                            tdraw.rectangle(
                                [bx, by, bx + bw_b - 1, by + bw_b - 1], fill=txt_rgba
                            )

                if unit_str:
                    tdraw.text(
                        (gx0 + grid_w + 6 * s, top_y + grid_h),
                        unit_str,
                        fill=accent_rgba,
                        font=f_unit,
                        anchor="lb",
                    )

        if not drew_blocks:
            val_px = int(round(max(16.0, min(rh * 0.32, 48.0) * fscale) * s))
            f_val = load_font(val_px, bold=True, mono=True)
            full = f"{formatted} {cell['unit']}" if cell.get("unit") else formatted
            tdraw.text(
                (cw_i / 2.0, center_y), full, fill=txt_rgba, font=f_val, anchor="mm"
            )

        desc = cell.get("description", "")
        if desc and rh >= 135:
            f_desc = load_font(int(round(11.5 * fscale * s)), bold=False, mono=True)
            tdraw.text(
                (cw_i / 2.0, ch_i - pad_y + 2 * s),
                f"// {desc}",
                fill=mut_rgba,
                font=f_desc,
                anchor="mb",
            )
        return

    # Classic & Reverse modern card typography
    is_rev = cs["variant"] == "reverse"
    rev_ink = cs["reverse_ink"]
    txt_op = float(cs["text_opacity"])
    mut_op = float(cs["muted_opacity"])

    lbl_rgba = rgba(rev_ink if is_rev else cs["muted"], mut_op)
    val_rgba = rgba(rev_ink if is_rev else cs["text"], txt_op)
    unit_rgba = rgba(
        rev_ink if is_rev else cs["unit_color"], mut_op if is_rev else txt_op
    )

    pad_x = min(64.0, max(16.0, rw * 0.045)) * s
    pad_y = min(48.0, max(12.0, rh * 0.075)) * s

    label = cell.get("label", "")
    if label:
        lbl_px = int(round(max(11.0, min(rh * 0.075, rw * 0.042, 40.0)) * fscale * s))
        f_lbl = load_font(lbl_px, bold=True)
        tdraw.text((pad_x, pad_y + 2 * s), label, fill=lbl_rgba, font=f_lbl)

    if cell.get("dynamic"):
        dot_r = max(4.5, min(9.0, rh * 0.016)) * s
        dx = cw_i - pad_x - dot_r
        dy = pad_y + dot_r + 4 * s
        dot_col = rgba(rev_ink, 0.85) if is_rev else rgba("#22c55e")
        tdraw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=dot_col)

    val_px = int(round(max(18.0, min(rh * 0.40, rw * 0.26, 280.0) * fscale) * s))
    unit_text = f" {cell['unit']}" if cell.get("unit") else ""
    formatted = str(cell.get("formatted", cell.get("value", "")))

    f_val = load_font(val_px, bold=True)
    unit_px = max(int(round(13 * s)), int(round(val_px * 0.42)))
    f_unit = load_font(unit_px, bold=True)

    val_w = tdraw.textlength(formatted, font=f_val)
    unit_w = tdraw.textlength(unit_text, font=f_unit) if unit_text else 0.0
    max_avail_w = max(24.0 * s, cw_i - pad_x * 2)

    if val_w + unit_w > max_avail_w and (val_w + unit_w) > 0:
        shrink = max_avail_w / (val_w + unit_w)
        val_px = max(int(round(14 * s)), int(val_px * shrink))
        unit_px = max(int(round(11 * s)), int(round(val_px * 0.42)))
        f_val = load_font(val_px, bold=True)
        f_unit = load_font(unit_px, bold=True)
        val_w = tdraw.textlength(formatted, font=f_val)
        unit_w = tdraw.textlength(unit_text, font=f_unit) if unit_text else 0.0

    group_w = val_w + unit_w
    start_x = (cw_i - group_w) / 2.0
    center_y = ch_i * (0.56 if label else 0.5)

    tdraw.text((start_x, center_y), formatted, fill=val_rgba, font=f_val, anchor="lm")
    if unit_text:
        tdraw.text(
            (start_x + val_w, center_y + val_px * 0.08),
            unit_text,
            fill=unit_rgba,
            font=f_unit,
            anchor="lm",
        )

    desc = cell.get("description", "")
    if desc and rh >= 130:
        desc_px = int(round(max(10.0, max(12.0, min(rh * 0.046, rw * 0.026, 26.0)) * fscale) * s))
        f_desc = load_font(desc_px, bold=False)
        tdraw.text(
            (cw_i / 2.0, ch_i - pad_y), desc, fill=lbl_rgba, font=f_desc, anchor="mb"
        )


def _render_number_svg(
    cell: dict[str, Any],
    cs: dict[str, Any],
    rx: float,
    ry: float,
    rw: float,
    rh: float,
) -> list[str]:
    variant = cs["variant"]
    is_rev = variant == "reverse"
    rev_ink = cs["reverse_ink"]
    cell_font = html.escape(
        MONOSPACE_STACK if variant == "text" else cs["font"], quote=True
    )
    fscale = float(cs["font_scale"])

    pad_x = 18.0 if variant == "text" else min(64.0, max(16.0, rw * 0.045))
    pad_y = 14.0 if variant == "text" else min(48.0, max(12.0, rh * 0.075))
    label = cell.get("label", "")
    txt_op = float(cs["text_opacity"])
    mut_op = float(cs["muted_opacity"])

    lbl_col = rev_ink if is_rev else cs["muted"]
    val_col = rev_ink if is_rev else cs["text"]
    unit_col = rev_ink if is_rev else cs["unit_color"]

    parts: list[str] = []
    if label:
        lbl_px = int(
            round(
                (13.0 if variant == "text" else max(11.0, min(rh * 0.075, rw * 0.042, 40.0)))
                * fscale
            )
        )
        lbl_str = f"┤ {label} ├" if variant == "text" else label
        parts.append(
            f'  <text x="{rx + pad_x:.1f}" y="{ry + pad_y + lbl_px:.1f}" '
            f'fill="{html.escape(lbl_col)}" fill-opacity="{mut_op:.3f}" font-family="{cell_font}" '
            f'font-size="{lbl_px}" font-weight="600">{html.escape(lbl_str)}</text>'
        )

    val_px = int(round(max(18.0, min(rh * 0.40, rw * 0.26, 280.0) * fscale)))
    unit_px = max(13, int(round(val_px * 0.42)))
    cy = ry + rh * (0.58 if label else 0.52)
    cx = rx + rw / 2.0
    formatted = html.escape(str(cell.get("formatted", cell.get("value", ""))))
    unit = html.escape(cell.get("unit", ""))

    unit_span = (
        f'<tspan fill="{html.escape(unit_col)}" fill-opacity="{(mut_op if is_rev else txt_op):.3f}" '
        f'font-size="{unit_px}" font-weight="600"> {unit}</tspan>'
        if unit
        else ""
    )
    parts.append(
        f'  <text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="middle" '
        f'fill="{html.escape(val_col)}" fill-opacity="{txt_op:.3f}" font-family="{cell_font}" '
        f'font-size="{val_px}" font-weight="700">{formatted}{unit_span}</text>'
    )

    if cell.get("description") and rh >= 130:
        desc_px = int(round(max(12.0, min(rh * 0.046, rw * 0.026, 26.0)) * fscale))
        d_txt = (
            f"// {cell['description']}" if variant == "text" else cell["description"]
        )
        parts.append(
            f'  <text x="{cx:.1f}" y="{ry + rh - pad_y:.1f}" text-anchor="middle" '
            f'fill="{html.escape(lbl_col)}" fill-opacity="{mut_op:.3f}" font-family="{cell_font}" '
            f'font-size="{desc_px}">{html.escape(d_txt)}</text>'
        )
    return parts


def _render_number_tui(
    cell: dict[str, Any],
    inner_w: int,
    interior_h: int,
    colors: dict[str, str],
    helpers: dict[str, Any],
) -> list[str]:
    split_block_renderable = helpers["split_block_renderable"]
    render_block_digits = helpers["render_block_digits"]

    c_val = colors["val"]
    c_lbl = colors["lbl"]
    c_unit = colors["unit"]

    formatted = str(cell.get("formatted", cell.get("value", "")))
    unit = str(cell.get("unit") or "").strip()
    desc = str(cell.get("description") or "").strip()

    prefix, core = split_block_renderable(formatted)
    block3 = render_block_digits(core) if core else None
    unit_suffix = f" {unit}" if unit else ""
    prefix_pad = f"{prefix} " if prefix else ""

    if (
        block3 is not None
        and (len(prefix_pad) + len(block3[0]) + len(unit_suffix) + 2 <= inner_w)
        and interior_h >= 4
    ):
        b_w = len(block3[0])
        grp_w = len(prefix_pad) + b_w + len(unit_suffix)
        left_pad = (inner_w - grp_w) // 2
        right_pad = inner_w - grp_w - left_pad

        row0 = f"{' ' * left_pad}{' ' * len(prefix_pad)}{c_val}{block3[0]}{' ' * len(unit_suffix)}{' ' * right_pad}"
        row1 = (
            f"{' ' * left_pad}{c_unit}{prefix_pad}{c_val}{block3[1]}"
            f"{' ' * len(unit_suffix)}{' ' * right_pad}"
        )
        row2 = (
            f"{' ' * left_pad}{' ' * len(prefix_pad)}{c_val}{block3[2]}"
            f"{c_unit}{unit_suffix}{' ' * right_pad}"
        )
        mid_block = [row0, row1, row2]
    else:
        plain_txt = f"{formatted}{unit_suffix}"[:inner_w]
        lp = (inner_w - len(plain_txt)) // 2
        rp = inner_w - len(plain_txt) - lp
        mid_block = [f"{' ' * lp}{c_val}{plain_txt}{' ' * rp}"]

    blank = " " * inner_w
    avail_pad = max(
        0, interior_h - len(mid_block) - (1 if desc and interior_h >= 5 else 0)
    )
    top_pad_n = avail_pad // 2
    bot_pad_n = avail_pad - top_pad_n

    content_rows: list[str] = []
    for _ in range(top_pad_n):
        content_rows.append(blank)
    content_rows.extend(mid_block)
    for _ in range(bot_pad_n):
        content_rows.append(blank)

    if desc and len(content_rows) < interior_h:
        d_txt = desc[: max(1, inner_w - 2)]
        lp = (inner_w - len(d_txt)) // 2
        rp = inner_w - len(d_txt) - lp
        content_rows.append(f"{' ' * lp}{c_lbl}{d_txt}{' ' * rp}")

    while len(content_rows) < interior_h:
        content_rows.append(blank)
    return content_rows[:interior_h]


register_chart_renderers(
    "number",
    pillow=_render_number_pillow,
    svg=_render_number_svg,
    tui=_render_number_tui,
)
