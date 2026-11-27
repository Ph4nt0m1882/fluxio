"""Unicode Braille (2x4 subpixel) terminal canvas for `Axis2D` charts (`print(fig)` & `.txt`)."""

from __future__ import annotations
from ..theme import hex_to_rgb

# Unicode Braille dot bitmasks indexed by [dy][dx] for dx in (0, 1), dy in (0, 1, 2, 3)
_BRAILLE_BITS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)


def _ansi_fg(hex_color: str, ansi: bool, bold: bool = False) -> str:
    if not ansi:
        return ""
    r, g, b = hex_to_rgb(hex_color)
    b_prefix = "1;" if bold else ""
    return f"\x1b[{b_prefix}38;2;{r};{g};{b}m"


class BrailleCanvas:
    """High-resolution 2x4 subpixel per character Braille rasterizer with TrueColor support."""

    def __init__(self, char_width: int, char_height: int) -> None:
        self.char_w = max(2, int(char_width))
        self.char_h = max(2, int(char_height))
        self.px_w = self.char_w * 2
        self.px_h = self.char_h * 4
        self._masks: list[list[int]] = [[0] * self.char_w for _ in range(self.char_h)]
        self._colors: list[list[str | None]] = [
            [None] * self.char_w for _ in range(self.char_h)
        ]

    def set_pixel(self, px: int, py: int, color: str) -> None:
        if 0 <= px < self.px_w and 0 <= py < self.px_h:
            cx, dx = divmod(px, 2)
            cy, dy = divmod(py, 4)
            self._masks[cy][cx] |= _BRAILLE_BITS[dy][dx]
            self._colors[cy][cx] = color

    def draw_line(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: str,
        linestyle: str = "solid",
    ) -> None:
        """Rasterize a subpixel segment using Bresenham's algorithm with optional dash pattern."""
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        step = 0

        while True:
            draw_dot = True
            if linestyle == "dashed":
                draw_dot = (step % 6) < 4
            elif linestyle == "dotted":
                draw_dot = (step % 3) == 0

            if draw_dot:
                self.set_pixel(x0, y0, color)

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
            step += 1

    def render_rows(self, *, ansi: bool = True, restore_seq: str = "") -> list[str]:
        """Convert the subpixel canvas into `char_h` strings of exact visual width `char_w`."""
        rows_out: list[str] = []
        for cy in range(self.char_h):
            parts: list[str] = []
            last_col: str | None = None
            for cx in range(self.char_w):
                mask = self._masks[cy][cx]
                if mask == 0:
                    if last_col is not None and ansi:
                        parts.append(restore_seq)
                        last_col = None
                    parts.append(" ")
                else:
                    col = self._colors[cy][cx]
                    if ansi and col != last_col and col is not None:
                        parts.append(_ansi_fg(col, True, bold=True))
                        last_col = col
                    parts.append(chr(0x2800 | mask))
            if last_col is not None and ansi:
                parts.append(restore_seq)
            rows_out.append("".join(parts))
        return rows_out
