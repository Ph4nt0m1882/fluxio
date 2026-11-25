"""Terminal TUI & `btop`-style block-digit renderer for `print(fig)` and `.txt` exports."""

from __future__ import annotations
import shutil
from typing import Any
from .theme import hex_to_rgb, resolve_cell_style

DIGIT_SUBPIXELS: dict[str, list[str]] = {
    "0": ["111", "101", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "100", "111"],
    "3": ["111", "001", "011", "001", "001", "111"],
    "4": ["101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "111", "001", "001", "111"],
    "6": ["111", "100", "111", "101", "101", "111"],
    "7": ["111", "001", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "101", "111"],
    "9": ["111", "101", "111", "001", "001", "111"],
    ".": ["0", "0", "0", "0", "0", "1"],
    ",": ["0", "0", "0", "0", "1", "1"],
    "-": ["00", "00", "11", "00", "00", "00"],
    "+": ["000", "010", "111", "010", "000", "000"],
    ":": ["0", "1", "0", "0", "1", "0"],
    " ": ["0", "0", "0", "0", "0", "0"],
}


def split_block_renderable(formatted: str) -> tuple[str, str]:
    idx = 0
    while idx < len(formatted) and formatted[idx] not in DIGIT_SUBPIXELS:
        idx += 1
    prefix = formatted[:idx]
    core = formatted[idx:]
    if not core or any(ch not in DIGIT_SUBPIXELS for ch in core):
        return "", ""
    return prefix, core


def build_block_matrix(core: str) -> list[str] | None:
    if not core:
        return None
    glyphs: list[list[str]] = []
    for ch in core:
        g = DIGIT_SUBPIXELS.get(ch)
        if g is None:
            return None
        glyphs.append(g)
    out = [""] * 6
    for idx, g in enumerate(glyphs):
        sep = "0" if idx > 0 else ""
        for r in range(6):
            out[r] += sep + g[r]
    return out


def render_block_digits(core: str) -> tuple[str, str, str] | None:
    matrix = build_block_matrix(core)
    if not matrix:
        return None
    rows: list[str] = []
    for r in range(3):
        top = matrix[r * 2]
        bot = matrix[r * 2 + 1]
        line = "".join(
            "█" if (t == "1" and b == "1") else ("▀" if t == "1" else ("▄" if b == "1" else " "))
            for t, b in zip(top, bot, strict=True)
        )
        rows.append(line)
    return (rows[0], rows[1], rows[2])


def _fg(hex_color: str, ansi: bool, bold: bool = False) -> str:
    if not ansi:
        return ""
    r, g, b = hex_to_rgb(hex_color)
    b_code = "1;" if bold else ""
    return f"\x1b[{b_code}38;2;{r};{g};{b}m"


def _bg(hex_color: str, ansi: bool) -> str:
    if not ansi:
        return ""
    r, g, b = hex_to_rgb(hex_color)
    return f"\x1b[48;2;{r};{g};{b}m"


def _reset(ansi: bool) -> str:
    return "\x1b[0m" if ansi else ""


def _render_single_box_lines(
    cell: dict[str, Any],
    cs: dict[str, Any],
    box_w: int,
    box_h: int,
    ansi: bool,
) -> list[str]:
    """Render one cell into `box_h` strings of exact visual width `box_w`."""
    box_w = max(14, box_w)
    box_h = max(7, box_h)
    inner_w = box_w - 2

    side = str(cs["accent_side"])
    accent = str(cs["accent"])
    is_rev = cs["variant"] == "reverse"
    rev_ink = str(cs["reverse_ink"])

    bg_seq = _bg(accent, ansi) if is_rev else ""
    rst = _reset(ansi)

    border_col = rev_ink if is_rev else str(cs["border"])
    accent_col = rev_ink if is_rev else accent
    val_col = rev_ink if is_rev else str(cs["text"])
    lbl_col = rev_ink if is_rev else str(cs["muted"])
    unit_col = rev_ink if is_rev else str(cs["unit_color"])

    c_border = bg_seq + _fg(border_col, ansi, bold=False)
    c_accent = bg_seq + _fg(accent_col, ansi, bold=True)
    if not is_rev and val_col.lower() in ("#f8fafc", "#0f172a", "#090d16"):
        c_val = ("\x1b[39;1m" if ansi else "")
    else:
        c_val = bg_seq + _fg(val_col, ansi, bold=True)

    if not is_rev and lbl_col.lower() in ("#cbd5e1", "#94a3b8", "#64748b", "#475569", "#334155"):
        c_lbl = ("\x1b[39;2m" if ansi else "")
    else:
        c_lbl = bg_seq + _fg(lbl_col, ansi, bold=False)

    c_unit = bg_seq + _fg(unit_col, ansi, bold=True)

    h_top_ch = "━" if side == "top" else "─"
    h_bot_ch = "━" if side == "bottom" else "─"
    v_left_ch = "┃" if side == "left" else "│"
    v_right_ch = "┃" if side == "right" else "│"

    c_top = c_accent if side == "top" else c_border
    c_bot = c_accent if side == "bottom" else c_border
    c_left = c_accent if side == "left" else c_border
    c_right = c_accent if side == "right" else c_border

    # Top border with optional embedded `┤ Label ├` tab
    label = str(cell.get("label") or "").strip()
    if label and len(label) + 6 <= inner_w:
        rem = inner_w - (len(label) + 4)
        top_line = (
            f"{c_top}╭{h_top_ch}{c_accent}┤ {c_lbl}{label}{c_accent} ├"
            f"{c_top}{h_top_ch * (rem - 1)}╮{rst}"
        )
    elif label:
        trunc = label[: max(1, inner_w - 2)]
        rem = inner_w - len(trunc) - 2
        top_line = f"{c_top}╭ {c_lbl}{trunc} {c_top}{h_top_ch * max(0, rem)}╮{rst}"
    else:
        top_line = f"{c_top}╭{h_top_ch * inner_w}╮{rst}"

    bot_line = f"{c_bot}╰{h_bot_ch * inner_w}╯{rst}"

    # Prepare interior lines (height = box_h - 2)
    interior_h = box_h - 2
    formatted = str(cell.get("formatted", cell.get("value", "")))
    unit = str(cell.get("unit") or "").strip()
    desc = str(cell.get("description") or "").strip()

    prefix, core = split_block_renderable(formatted)
    block3 = render_block_digits(core) if core else None
    unit_suffix = f" {unit}" if unit else ""
    prefix_pad = f"{prefix} " if prefix else ""

    content_rows: list[str] = []
    if block3 is not None and (len(prefix_pad) + len(block3[0]) + len(unit_suffix) + 2 <= inner_w) and interior_h >= 4:
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
    avail_pad = max(0, interior_h - len(mid_block) - (1 if desc and interior_h >= 5 else 0))
    top_pad_n = avail_pad // 2
    bot_pad_n = avail_pad - top_pad_n

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
    content_rows = content_rows[:interior_h]

    lines = [top_line]
    for r_str in content_rows:
        lines.append(f"{c_left}{v_left_ch}{bg_seq}{r_str}{c_right}{v_right_ch}{rst}")
    lines.append(bot_line)
    return lines


def render_spec_to_terminal(
    spec: dict[str, Any],
    *,
    ansi: bool = True,
    width: int | None = None,
) -> str:
    """Render a FigureSpec into an ANSI TrueColor (or plain UTF-8) TUI grid string."""
    term_cols = width or min(104, max(56, shutil.get_terminal_size((88, 26)).columns))
    rows = max(1, int(spec["rows"]))
    cols = max(1, int(spec["cols"]))
    theme = spec["theme"]
    rst = _reset(ansi)

    out_lines: list[str] = []
    title = str(spec.get("title") or "").strip()
    subtitle = str(spec.get("subtitle") or "").strip()
    if title:
        c_t = _fg(theme["accent"], ansi, bold=True)
        out_lines.append(f"{c_t}▸ {title}{rst}")
    if subtitle:
        c_s = _fg(theme["subtitle_color"], ansi, bold=False)
        out_lines.append(f"  {c_s}{subtitle}{rst}")
    if title or subtitle:
        out_lines.append("")

    col_gap = 2
    unit_w = max(16, (term_cols - col_gap * (cols - 1)) // cols)
    box_h = 7

    # Index cells by starting row/col
    by_row: dict[int, list[dict[str, Any]]] = {r: [] for r in range(rows)}
    for cell in spec["cells"]:
        r = int(cell["row"])
        if 0 <= r < rows:
            by_row[r].append(cell)

    for r in range(rows):
        row_cells = sorted(by_row[r], key=lambda c: int(c["col"]))
        if not row_cells:
            continue

        # Render each cell in this row and stitch horizontally according to col & col_span
        segments_per_line = ["" for _ in range(box_h)]
        cursor_col = 0
        for cell in row_cells:
            c_idx = int(cell["col"])
            if c_idx > cursor_col:
                empty_span = c_idx - cursor_col
                empty_w = empty_span * unit_w + col_gap * empty_span
                for li in range(box_h):
                    segments_per_line[li] += " " * empty_w

            c_span = max(1, min(int(cell.get("col_span", 1)), cols - c_idx))
            cell_w = c_span * unit_w + col_gap * (c_span - 1)
            cs = cell.get("resolved_style") or resolve_cell_style(
                theme, cell.get("style"), cell.get("color")
            )
            box_lines = _render_single_box_lines(cell, cs, cell_w, box_h, ansi)
            trailing_gap = " " * col_gap if (c_idx + c_span) < cols else ""
            for li in range(box_h):
                segments_per_line[li] += box_lines[li] + trailing_gap
            cursor_col = c_idx + c_span

        out_lines.extend(segments_per_line)

    return "\n".join(out_lines)
