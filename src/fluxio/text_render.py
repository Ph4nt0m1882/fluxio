"""Terminal TUI & `btop`-style block-digit renderer for `print(fig)` and `.txt` exports."""

from __future__ import annotations
import html
import re
import select
import shutil
import sys
import time
from typing import TYPE_CHECKING, Any
from .theme import MONOSPACE_STACK, hex_to_rgb, resolve_cell_style

if TYPE_CHECKING:
    from .figure import Figure

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
            "█"
            if (t == "1" and b == "1")
            else ("▀" if t == "1" else ("▄" if b == "1" else " "))
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
        c_val = "\x1b[39;1m" if ansi else ""
    else:
        c_val = bg_seq + _fg(val_col, ansi, bold=True)

    if not is_rev and lbl_col.lower() in (
        "#cbd5e1",
        "#94a3b8",
        "#64748b",
        "#475569",
        "#334155",
    ):
        c_lbl = "\x1b[39;2m" if ansi else ""
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

    # Prepare interior lines (height = box_h - 2) via modular chart TUI renderer
    from . import charts as _charts  # noqa: F401
    from .charts.base import get_tui_renderer

    interior_h = box_h - 2
    tui_fn = get_tui_renderer(str(cell.get("kind", "number")))
    if tui_fn is not None:
        content_rows = tui_fn(
            cell,
            inner_w,
            interior_h,
            {
                "val": c_val,
                "lbl": c_lbl,
                "unit": c_unit,
                "accent": c_accent,
                "border": c_border,
            },
            {
                "split_block_renderable": split_block_renderable,
                "render_block_digits": render_block_digits,
                "ansi": ansi,
                "bg_seq": bg_seq,
                "accent_hex": accent_col,
            },
        )
    else:
        content_rows = [" " * inner_w for _ in range(interior_h)]

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

        row_box_h = (
            13
            if any(str(c.get("kind", "number")) != "number" for c in row_cells)
            else 7
        )

        # Render each cell in this row and stitch horizontally according to col & col_span
        segments_per_line = ["" for _ in range(row_box_h)]
        cursor_col = 0
        for cell in row_cells:
            c_idx = int(cell["col"])
            if c_idx > cursor_col:
                empty_span = c_idx - cursor_col
                empty_w = empty_span * unit_w + col_gap * empty_span
                for li in range(row_box_h):
                    segments_per_line[li] += " " * empty_w

            c_span = max(1, min(int(cell.get("col_span", 1)), cols - c_idx))
            cell_w = c_span * unit_w + col_gap * (c_span - 1)
            cs = cell.get("resolved_style") or resolve_cell_style(
                theme, cell.get("style"), cell.get("color")
            )
            box_lines = _render_single_box_lines(cell, cs, cell_w, row_box_h, ansi)
            trailing_gap = " " * col_gap if (c_idx + c_span) < cols else ""
            for li in range(row_box_h):
                segments_per_line[li] += box_lines[li] + trailing_gap
            cursor_col = c_idx + c_span

        out_lines.extend(segments_per_line)

    return "\n".join(out_lines)


def get_active_ipython_kernel() -> Any | None:
    """Return the active IPython kernel instance when running inside a Jupyter Notebook, else None."""
    if "ipykernel" not in sys.modules:
        return None
    try:
        from IPython import get_ipython  # type: ignore

        ip = get_ipython()
        if ip is not None and "IPKernelApp" in getattr(ip, "config", {}):
            return ip
    except Exception:
        pass
    return None


def _poll_tty_key() -> str | None:
    try:
        rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
        if rlist:
            return sys.stdin.read(1)
    except Exception:
        pass
    return None


def live_print_figure(
    fig: Figure,
    *,
    duration: float | None = None,
    fps: int | None = None,
    controls: bool = True,
    ansi: bool = True,
    width: int | None = None,
) -> None:
    """Animate `fig` in-place inside a terminal (with keyboard controls) or Jupyter cell."""
    if not fig.is_dynamic and duration is None:
        sys.stdout.write(fig.to_text(ansi=ansi, width=width) + "\n")
        sys.stdout.flush()
        return

    effective_fps = max(1, int(fps if fps is not None else fig.fps))
    ip = get_active_ipython_kernel()
    # Cap Jupyter refresh rate slightly so notebook IOPub stays responsive
    if ip is not None and fps is None:
        effective_fps = min(effective_fps, 12)
    interval = 1.0 / effective_fps

    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    stdin_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
    use_kbd = bool(controls and is_tty and stdin_tty and ip is None)

    old_term_attrs: Any = None
    stdin_fd: int | None = None
    if use_kbd:
        try:
            import termios
            import tty

            stdin_fd = sys.stdin.fileno()
            old_term_attrs = termios.tcgetattr(stdin_fd)
            tty.setcbreak(stdin_fd)
        except Exception:
            use_kbd = False
            old_term_attrs = None

    playing = True
    start_wall = time.monotonic()
    run_start = start_wall
    paused_elapsed = 0.0
    step_idx = 0
    prev_lines = 0

    if is_tty and ansi:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    try:
        while True:
            now = time.monotonic()
            if duration is not None and (now - start_wall) >= duration and step_idx > 0:
                break

            if use_kbd:
                key = _poll_tty_key()
                if key in ("q", "Q", "\x1b"):
                    break
                if key == " ":
                    if playing:
                        paused_elapsed += now - run_start
                        playing = False
                    else:
                        run_start = now
                        playing = True
                elif key in ("r", "R"):
                    paused_elapsed = 0.0
                    run_start = now
                    step_idx = 0
                    for cell in fig.cells:
                        cell.reset_cursor()

            elapsed = paused_elapsed + (now - run_start) if playing else paused_elapsed
            spec = fig.to_spec(t=elapsed, step_index=step_idx)
            frame_txt = render_spec_to_terminal(spec, ansi=ansi, width=width)

            if controls and is_tty:
                state_badge = (
                    (
                        "\x1b[1;32m● LIVE\x1b[0m"
                        if playing
                        else "\x1b[1;33m⏸ PAUSE\x1b[0m"
                    )
                    if ansi
                    else ("LIVE" if playing else "PAUSE")
                )
                dim = "\x1b[39;2m" if ansi else ""
                rst = "\x1b[0m" if ansi else ""
                frame_txt += f"\n  {state_badge}  {dim}[Espace] Pause/Play • [R] Reset • [Q / Ctrl+C] Quitter{rst}"

            if ip is not None:
                if step_idx > 0:
                    from IPython.display import clear_output  # type: ignore

                    clear_output(wait=True)
                sys.stdout.write(frame_txt + "\n")
                sys.stdout.flush()
            elif is_tty:
                prefix = f"\x1b[{prev_lines}A\r\x1b[J" if prev_lines > 0 else ""
                sys.stdout.write(f"{prefix}{frame_txt}\n")
                sys.stdout.flush()
                prev_lines = frame_txt.count("\n") + 1
            else:
                # Non-TTY stream (e.g. test capture or pipe): write initial frame once cleanly
                if step_idx == 0:
                    sys.stdout.write(frame_txt + "\n")
                    sys.stdout.flush()

            if playing:
                step_idx += 1

            sleep_for = interval
            if duration is not None:
                rem = duration - (time.monotonic() - start_wall)
                if rem <= 0:
                    break
                sleep_for = min(interval, rem)
            time.sleep(max(0.002, sleep_for))
    except KeyboardInterrupt:
        pass
    finally:
        if old_term_attrs is not None and stdin_fd is not None:
            try:
                import termios

                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_term_attrs)
            except Exception:
                pass
        if is_tty and ansi:
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()


_ANSI_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")
_ANSI_OTHER_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-ln-z]")

_BRAILLE_DOT_OFFSETS: tuple[tuple[int, float, float], ...] = (
    (0, 0.28, 0.16),
    (1, 0.28, 0.39),
    (2, 0.28, 0.61),
    (6, 0.28, 0.84),
    (3, 0.72, 0.16),
    (4, 0.72, 0.39),
    (5, 0.72, 0.61),
    (7, 0.72, 0.84),
)

_BOX_ORTHO_ARMS: dict[str, tuple[str, ...]] = {
    "┌": ("R", "D"),
    "┐": ("L", "D"),
    "└": ("R", "U"),
    "┘": ("L", "U"),
    "├": ("U", "D", "R"),
    "┤": ("U", "D", "L"),
    "┬": ("L", "R", "D"),
    "┴": ("L", "R", "U"),
    "┼": ("L", "R", "U", "D"),
}


def render_ansi_to_svg(
    ansi_text: str,
    *,
    title: str = "terminal — print(fig)",
) -> str:
    """Render an ANSI TrueColor terminal string into a pixel-locked, zero-font-drift vector SVG."""
    cleaned = _ANSI_OTHER_RE.sub("", ansi_text.rstrip("\n"))
    raw_lines = cleaned.split("\n") if cleaned else [""]

    default_fg = "#f8fafc"
    fg = default_fg
    bg: str | None = None
    bold = False
    dim = False

    # Each cell is (char, effective_fg_hex, bg_hex_or_None, is_bold)
    grid: list[list[tuple[str, str, str | None, bool]]] = []
    for line in raw_lines:
        row_cells: list[tuple[str, str, str | None, bool]] = []
        pos = 0
        for m in _ANSI_SGR_RE.finditer(line):
            chunk = line[pos : m.start()]
            if chunk:
                eff_fg = "#94a3b8" if (dim and fg == default_fg) else fg
                for ch_c in chunk:
                    row_cells.append((ch_c, eff_fg, bg, bold))
            codes_str = m.group(1)
            codes = codes_str.split(";") if codes_str else ["0"]
            idx = 0
            while idx < len(codes):
                code = codes[idx]
                if code in ("", "0"):
                    fg = default_fg
                    bg = None
                    bold = False
                    dim = False
                elif code == "1":
                    bold = True
                elif code == "2":
                    dim = True
                elif code == "22":
                    bold = False
                    dim = False
                elif code == "32":
                    fg = "#22c55e"
                elif code == "33":
                    fg = "#eab308"
                elif code == "39":
                    fg = default_fg
                elif code == "49":
                    bg = None
                elif code == "38" and idx + 4 < len(codes) and codes[idx + 1] == "2":
                    r_v = max(0, min(255, int(codes[idx + 2])))
                    g_v = max(0, min(255, int(codes[idx + 3])))
                    b_v = max(0, min(255, int(codes[idx + 4])))
                    fg = f"#{r_v:02x}{g_v:02x}{b_v:02x}"
                    idx += 4
                elif code == "48" and idx + 4 < len(codes) and codes[idx + 1] == "2":
                    r_v = max(0, min(255, int(codes[idx + 2])))
                    g_v = max(0, min(255, int(codes[idx + 3])))
                    b_v = max(0, min(255, int(codes[idx + 4])))
                    bg = f"#{r_v:02x}{g_v:02x}{b_v:02x}"
                    idx += 4
                idx += 1
            pos = m.end()

        tail = line[pos:]
        if tail:
            eff_fg = "#94a3b8" if (dim and fg == default_fg) else fg
            for ch_c in tail:
                row_cells.append((ch_c, eff_fg, bg, bold))
        grid.append(row_cells)

    cw = 9.0
    ch = 18.0
    header_h = 34.0
    pad_x = 18.0
    pad_top = header_h + 14.0
    pad_bot = 16.0

    n_rows = max(1, len(grid))
    n_cols = max((len(r) for r in grid), default=40)
    svg_w = pad_x * 2.0 + n_cols * cw
    svg_h = pad_top + n_rows * ch + pad_bot

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w:.1f} {svg_h:.1f}" width="{svg_w:.0f}" height="{svg_h:.0f}">',
        "  <defs>",
        f'    <clipPath id="fxTermClip"><rect width="{svg_w:.1f}" height="{svg_h:.1f}" rx="16"/></clipPath>',
        "  </defs>",
        '  <g clip-path="url(#fxTermClip)">',
        f'    <rect width="{svg_w:.1f}" height="{svg_h:.1f}" fill="#090d16"/>',
        f'    <rect width="{svg_w:.1f}" height="{header_h:.1f}" fill="#0f172a"/>',
        f'    <line x1="0" y1="{header_h:.1f}" x2="{svg_w:.1f}" y2="{header_h:.1f}" stroke="#1e293b" stroke-width="1"/>',
        '    <circle cx="20" cy="17" r="5.2" fill="#ef4444"/>',
        '    <circle cx="36" cy="17" r="5.2" fill="#f59e0b"/>',
        '    <circle cx="52" cy="17" r="5.2" fill="#22c55e"/>',
        f'    <text x="{svg_w / 2.0:.1f}" y="21.2" text-anchor="middle" fill="#94a3b8" font-family="{MONOSPACE_STACK}" font-size="11.8" font-weight="600">{html.escape(title)}</text>',
    ]

    # 1. Cell background fills (coalesced per row for `variant="reverse"`)
    for r_idx, row_cells in enumerate(grid):
        y0 = pad_top + r_idx * ch
        c_idx = 0
        row_len = len(row_cells)
        while c_idx < row_len:
            cell_bg = row_cells[c_idx][2]
            if cell_bg is None:
                c_idx += 1
                continue
            span = 1
            while c_idx + span < row_len and row_cells[c_idx + span][2] == cell_bg:
                span += 1
            x0 = pad_x + c_idx * cw
            out.append(
                f'    <rect x="{x0:.2f}" y="{y0:.2f}" width="{span * cw + 0.35:.2f}" height="{ch + 0.35:.2f}" fill="{cell_bg}"/>'
            )
            c_idx += span

    # 2. Vector primitives (Braille, blocks, box-drawing) & cell-locked glyphs
    for r_idx, row_cells in enumerate(grid):
        y0 = pad_top + r_idx * ch
        y1 = y0 + ch
        cy = y0 + ch * 0.5
        for c_idx, (ch_c, c_fg, _c_bg, c_bold) in enumerate(row_cells):
            if ch_c == " " or ch_c == "\u2800":
                continue
            x0 = pad_x + c_idx * cw
            x1 = x0 + cw
            cx = x0 + cw * 0.5
            cp = ord(ch_c)

            if 0x2801 <= cp <= 0x28FF:
                bits = cp - 0x2800
                for bit, dx, dy in _BRAILLE_DOT_OFFSETS:
                    if bits & (1 << bit):
                        out.append(
                            f'    <circle cx="{x0 + cw * dx:.2f}" cy="{y0 + ch * dy:.2f}" r="1.42" fill="{c_fg}"/>'
                        )
            elif ch_c == "█":
                out.append(
                    f'    <rect x="{x0:.2f}" y="{y0:.2f}" width="{cw + 0.35:.2f}" height="{ch + 0.35:.2f}" fill="{c_fg}"/>'
                )
            elif ch_c == "▀":
                out.append(
                    f'    <rect x="{x0:.2f}" y="{y0:.2f}" width="{cw + 0.35:.2f}" height="{ch * 0.5 + 0.35:.2f}" fill="{c_fg}"/>'
                )
            elif ch_c == "▄":
                out.append(
                    f'    <rect x="{x0:.2f}" y="{cy:.2f}" width="{cw + 0.35:.2f}" height="{ch * 0.5 + 0.35:.2f}" fill="{c_fg}"/>'
                )
            elif ch_c == "▌":
                out.append(
                    f'    <rect x="{x0:.2f}" y="{y0:.2f}" width="{cw * 0.5 + 0.35:.2f}" height="{ch + 0.35:.2f}" fill="{c_fg}"/>'
                )
            elif ch_c == "▐":
                out.append(
                    f'    <rect x="{cx:.2f}" y="{y0:.2f}" width="{cw * 0.5 + 0.35:.2f}" height="{ch + 0.35:.2f}" fill="{c_fg}"/>'
                )
            elif ch_c in ("─", "━"):
                sw = 2.8 if ch_c == "━" else 1.45
                out.append(
                    f'    <line x1="{x0 - 0.25:.2f}" y1="{cy:.2f}" x2="{x1 + 0.25:.2f}" y2="{cy:.2f}" stroke="{c_fg}" stroke-width="{sw}"/>'
                )
            elif ch_c == "╌":
                out.append(
                    f'    <line x1="{x0 + 0.7:.2f}" y1="{cy:.2f}" x2="{cx - 0.6:.2f}" y2="{cy:.2f}" stroke="{c_fg}" stroke-width="1.6"/>'
                )
                out.append(
                    f'    <line x1="{cx + 0.6:.2f}" y1="{cy:.2f}" x2="{x1 - 0.7:.2f}" y2="{cy:.2f}" stroke="{c_fg}" stroke-width="1.6"/>'
                )
            elif ch_c in ("│", "┃"):
                sw = 3.0 if ch_c == "┃" else 1.45
                out.append(
                    f'    <line x1="{cx:.2f}" y1="{y0 - 0.25:.2f}" x2="{cx:.2f}" y2="{y1 + 0.25:.2f}" stroke="{c_fg}" stroke-width="{sw}"/>'
                )
            elif ch_c == "╭":
                out.append(
                    f'    <path d="M {cx:.2f} {y1 + 0.25:.2f} L {cx:.2f} {cy + 3.6:.2f} Q {cx:.2f} {cy:.2f} {cx + 3.6:.2f} {cy:.2f} L {x1 + 0.25:.2f} {cy:.2f}" fill="none" stroke="{c_fg}" stroke-width="1.45"/>'
                )
            elif ch_c == "╮":
                out.append(
                    f'    <path d="M {x0 - 0.25:.2f} {cy:.2f} L {cx - 3.6:.2f} {cy:.2f} Q {cx:.2f} {cy:.2f} {cx:.2f} {cy + 3.6:.2f} L {cx:.2f} {y1 + 0.25:.2f}" fill="none" stroke="{c_fg}" stroke-width="1.45"/>'
                )
            elif ch_c == "╰":
                out.append(
                    f'    <path d="M {cx:.2f} {y0 - 0.25:.2f} L {cx:.2f} {cy - 3.6:.2f} Q {cx:.2f} {cy:.2f} {cx + 3.6:.2f} {cy:.2f} L {x1 + 0.25:.2f} {cy:.2f}" fill="none" stroke="{c_fg}" stroke-width="1.45"/>'
                )
            elif ch_c == "╯":
                out.append(
                    f'    <path d="M {x0 - 0.25:.2f} {cy:.2f} L {cx - 3.6:.2f} {cy:.2f} Q {cx:.2f} {cy:.2f} {cx:.2f} {cy - 3.6:.2f} L {cx:.2f} {y0 - 0.25:.2f}" fill="none" stroke="{c_fg}" stroke-width="1.45"/>'
                )
            elif ch_c in _BOX_ORTHO_ARMS:
                arms = _BOX_ORTHO_ARMS[ch_c]
                segs: list[str] = []
                if "L" in arms:
                    segs.append(f"M {x0 - 0.25:.2f} {cy:.2f} L {cx:.2f} {cy:.2f}")
                if "R" in arms:
                    segs.append(f"M {cx:.2f} {cy:.2f} L {x1 + 0.25:.2f} {cy:.2f}")
                if "U" in arms:
                    segs.append(f"M {cx:.2f} {y0 - 0.25:.2f} L {cx:.2f} {cy:.2f}")
                if "D" in arms:
                    segs.append(f"M {cx:.2f} {cy:.2f} L {cx:.2f} {y1 + 0.25:.2f}")
                out.append(
                    f'    <path d="{" ".join(segs)}" fill="none" stroke="{c_fg}" stroke-width="1.45" stroke-linecap="square"/>'
                )
            else:
                fw = ' font-weight="700"' if c_bold else ""
                out.append(
                    f'    <text x="{cx:.2f}" y="{y0 + ch * 0.73:.2f}" text-anchor="middle" fill="{c_fg}" font-family="{MONOSPACE_STACK}" font-size="13.2"{fw}>{html.escape(ch_c)}</text>'
                )

    out.append("  </g>")
    out.append(
        f'  <rect x="0.75" y="0.75" width="{svg_w - 1.5:.1f}" height="{svg_h - 1.5:.1f}" rx="15.25" fill="none" stroke="#334155" stroke-opacity="0.7" stroke-width="1.5"/>'
    )
    out.append("</svg>\n")
    return "\n".join(out)
