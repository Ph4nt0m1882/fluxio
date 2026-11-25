import {
  resolveTheme,
  type CellStyleOverride,
  type ThemeSpec,
} from "./themes";

export interface ToolbarSpec {
  enabled: boolean;
  zoom: boolean;
  capture: boolean;
  playback: boolean;
  fullscreen: boolean;
}

export interface NumberCellSpec {
  id: string;
  row: number;
  col: number;
  row_span: number;
  col_span: number;
  kind: "number";
  label: string;
  value: number;
  formatted: string;
  unit: string;
  precision: number | null;
  prefix: string;
  color: string | null;
  style: CellStyleOverride | null;
  description: string;
  dynamic: boolean;
  frames: number[] | null;
}

export type CellSpec = NumberCellSpec;

export interface FigureSpec {
  version: string;
  id: string;
  title: string;
  subtitle: string;
  rows: number;
  cols: number;
  size: [number, number];
  fps: number;
  dynamic: boolean;
  theme: ThemeSpec;
  toolbar: ToolbarSpec;
  cells: CellSpec[];
}

export interface TickUpdate {
  id: string;
  value: number;
  formatted?: string;
}

export interface TickMessage {
  type: "tick";
  t: number;
  updates: TickUpdate[];
}

export interface SnapshotMessage {
  type: "snapshot";
  spec: unknown;
}

export interface StateMessage {
  type: "state";
  playing: boolean;
}

export interface CaptureSavedMessage {
  type: "capture_saved";
  path: string;
}

export type ServerMessage =
  | TickMessage
  | SnapshotMessage
  | StateMessage
  | CaptureSavedMessage;

export function formatNumberValue(
  value: number,
  precision: number | null | undefined,
  prefix = "",
): string {
  if (!Number.isFinite(value)) {
    return String(value);
  }
  let numStr: string;
  if (typeof precision === "number" && precision >= 0) {
    numStr = value.toFixed(precision);
  } else if (Number.isInteger(value)) {
    numStr = String(value);
  } else {
    numStr = Number(value.toFixed(3)).toString();
  }
  return `${prefix}${numStr}`;
}

export function parseFigureSpec(raw: unknown): FigureSpec {
  if (!raw || typeof raw !== "object") {
    throw new Error("Invalid Fluxio FigureSpec: expected object");
  }
  const obj = raw as Record<string, unknown>;
  const rows = Math.max(1, Number(obj.rows ?? 1));
  const cols = Math.max(1, Number(obj.cols ?? 1));
  const rawSize = Array.isArray(obj.size) ? obj.size : [900, 520];
  const width = Math.max(160, Number(rawSize[0] ?? 900));
  const height = Math.max(120, Number(rawSize[1] ?? 520));
  const theme = resolveTheme(
    (obj.theme as Partial<ThemeSpec>) ?? { name: "dark" },
  );

  const rawToolbar = (obj.toolbar as Partial<ToolbarSpec>) ?? {};
  const toolbar: ToolbarSpec = {
    enabled: rawToolbar.enabled ?? true,
    zoom: rawToolbar.zoom ?? true,
    capture: rawToolbar.capture ?? true,
    playback: rawToolbar.playback ?? true,
    fullscreen: rawToolbar.fullscreen ?? true,
  };

  const rawCells = Array.isArray(obj.cells) ? obj.cells : [];
  const cells: CellSpec[] = rawCells.map((c, idx) => {
    const item = c as Record<string, unknown>;
    const val = Number(item.value ?? 0);
    const precision =
      typeof item.precision === "number" ? item.precision : null;
    const prefix = String(item.prefix ?? "");
    const styleObj =
      item.style && typeof item.style === "object"
        ? (item.style as CellStyleOverride)
        : null;
    return {
      id: String(item.id ?? `cell_${idx}`),
      row: Math.max(0, Number(item.row ?? 0)),
      col: Math.max(0, Number(item.col ?? 0)),
      row_span: Math.max(1, Number(item.row_span ?? 1)),
      col_span: Math.max(1, Number(item.col_span ?? 1)),
      kind: "number",
      label: String(item.label ?? ""),
      value: val,
      formatted:
        typeof item.formatted === "string"
          ? item.formatted
          : formatNumberValue(val, precision, prefix),
      unit: String(item.unit ?? ""),
      precision,
      prefix,
      color: typeof item.color === "string" ? item.color : null,
      style: styleObj,
      description: String(item.description ?? ""),
      dynamic: Boolean(item.dynamic ?? false),
      frames: Array.isArray(item.frames)
        ? item.frames.map((n) => Number(n))
        : null,
    };
  });

  return {
    version: String(obj.version ?? "0.1"),
    id: String(obj.id ?? "fig_default"),
    title: String(obj.title ?? ""),
    subtitle: String(obj.subtitle ?? ""),
    rows,
    cols,
    size: [width, height],
    fps: Math.max(1, Number(obj.fps ?? 30)),
    dynamic: Boolean(obj.dynamic ?? cells.some((c) => c.dynamic)),
    theme,
    toolbar,
    cells,
  };
}

export function applyTickMessage(spec: FigureSpec, msg: TickMessage): void {
  const byId = new Map(spec.cells.map((c) => [c.id, c]));
  for (const upd of msg.updates) {
    const cell = byId.get(upd.id);
    if (cell) {
      cell.value = upd.value;
      cell.formatted =
        upd.formatted ??
        formatNumberValue(upd.value, cell.precision, cell.prefix);
    }
  }
}
