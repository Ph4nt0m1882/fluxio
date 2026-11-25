/**
 * 6x3 subpixel font (3 character rows of half-blocks `█`, `▀`, `▄`, ` `)
 * inspired by `btop` / terminal dashboards, usable both as Unicode strings and Canvas/SVG block grids.
 */

export const DIGIT_SUBPIXELS: Record<string, string[]> = {
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
};

function subpixelsToThreeRows(matrix6: string[]): [string, string, string] {
  const rows: [string, string, string] = ["", "", ""];
  for (let r = 0; r < 3; r++) {
    const top = matrix6[r * 2]!;
    const bot = matrix6[r * 2 + 1]!;
    let line = "";
    for (let c = 0; c < top.length; c++) {
      const t = top[c] === "1";
      const b = bot[c] === "1";
      line += t && b ? "█" : t ? "▀" : b ? "▄" : " ";
    }
    rows[r] = line;
  }
  return rows;
}

/** Split a formatted value like "€128.4" into { prefix: "€", core: "128.4" }. */
export function splitBlockRenderable(formatted: string): {
  prefix: string;
  core: string;
} {
  let idx = 0;
  while (idx < formatted.length && !DIGIT_SUBPIXELS[formatted[idx]!]) {
    idx++;
  }
  const prefix = formatted.slice(0, idx);
  const core = formatted.slice(idx);
  for (const ch of core) {
    if (!DIGIT_SUBPIXELS[ch]) {
      return { prefix: "", core: "" };
    }
  }
  return { prefix, core };
}

/** Build the 6-row binary matrix ("0"/"1" strings) for a numeric core string. */
export function buildBlockMatrix(core: string): string[] | null {
  if (!core) return null;
  const glyphs: string[][] = [];
  for (const ch of core) {
    const g = DIGIT_SUBPIXELS[ch];
    if (!g) return null;
    glyphs.push(g);
  }
  const out: string[] = ["", "", "", "", "", ""];
  glyphs.forEach((g, idx) => {
    const sep = idx > 0 ? "0" : "";
    for (let r = 0; r < 6; r++) {
      out[r] += sep + g[r]!;
    }
  });
  return out;
}

/** Render a numeric string into 3 lines of `█`, `▀`, `▄` characters. */
export function renderBlockDigits(text: string): [string, string, string] | null {
  const matrix = buildBlockMatrix(text);
  if (!matrix) return null;
  return subpixelsToThreeRows(matrix);
}
