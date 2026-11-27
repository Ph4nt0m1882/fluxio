import type { GridRect } from "../layout";
import {
  normalizeLegendPosition,
  type LegendPosition,
  type PlotCellSpec,
} from "../protocol";
import { MONOSPACE_STACK, rgbaString, type ResolvedCellStyle } from "../themes";
import { addRoundedRectSubpath, computeCardUiScale } from "./base";

export interface PlotArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface AxisBounds {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

export interface SnappedPoint {
  seriesIndex: number;
  seriesLabel: string;
  color: string;
  dataX: number;
  dataY: number;
  canvasX: number;
  canvasY: number;
}

export const SERIES_PALETTE = [
  "#38bdf8",
  "#f97316",
  "#34d399",
  "#a78bfa",
  "#f43f5e",
  "#eab308",
  "#06b6d4",
];

export function pickSeriesColor(
  explicitColor: string | null,
  index: number,
  primaryAccent: string,
): string {
  if (explicitColor) return explicitColor;
  if (index === 0) return primaryAccent;
  const filtered = SERIES_PALETTE.filter(
    (c) => c.toLowerCase() !== primaryAccent.toLowerCase(),
  );
  return filtered[(index - 1) % filtered.length] ?? primaryAccent;
}

function niceNum(range: number, round: boolean): number {
  if (range <= 0 || !Number.isFinite(range)) return 1;
  const exponent = Math.floor(Math.log10(range));
  const fraction = range / Math.pow(10, exponent);
  let niceFraction: number;
  if (round) {
    if (fraction < 1.5) niceFraction = 1;
    else if (fraction < 3) niceFraction = 2;
    else if (fraction < 7) niceFraction = 5;
    else niceFraction = 10;
  } else {
    if (fraction <= 1) niceFraction = 1;
    else if (fraction <= 2) niceFraction = 2;
    else if (fraction <= 5) niceFraction = 5;
    else niceFraction = 10;
  }
  return niceFraction * Math.pow(10, exponent);
}

export function computeNiceTicks(
  minVal: number,
  maxVal: number,
  maxTicks = 5,
): number[] {
  let lo = minVal;
  let hi = maxVal;
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 1];
  if (lo === hi) {
    const pad = lo === 0 ? 1 : Math.abs(lo) * 0.1;
    lo -= pad;
    hi += pad;
  }
  if (lo > hi) [lo, hi] = [hi, lo];

  const nTicks = Math.max(2, maxTicks);
  const range = niceNum(hi - lo, false);
  const step = niceNum(range / (nTicks - 1), true);
  const graphMin = Math.floor(lo / step) * step;
  const graphMax = Math.ceil(hi / step) * step;

  const ticks: number[] = [];
  for (let v = graphMin; v <= graphMax + step * 0.5; v += step) {
    const clean = Number(v.toPrecision(10));
    ticks.push(Object.is(clean, -0) ? 0 : clean);
    if (ticks.length > 20) break;
  }
  return ticks;
}

export function computeAxisTicks(
  minVal: number,
  maxVal: number,
  maxTicks = 5,
  step?: number | null,
  explicitMin?: number | null,
): number[] {
  if (typeof step !== "number" || !Number.isFinite(step) || step <= 0) {
    return computeNiceTicks(minVal, maxVal, maxTicks);
  }
  const lo = Math.min(minVal, maxVal);
  const hi = Math.max(minVal, maxVal);
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 1];

  const span = Math.max(0, hi - lo);
  let effStep = step;
  if (span / effStep > 200) {
    effStep *= Math.ceil(span / effStep / 100);
  }

  const eps = 1e-9 * effStep;
  let start: number;
  if (typeof explicitMin === "number" && Number.isFinite(explicitMin)) {
    start = explicitMin;
    if (start < lo - eps) {
      start += Math.ceil((lo - start - eps) / effStep) * effStep;
    }
  } else {
    start = Math.ceil((lo - eps) / effStep) * effStep;
  }

  const ticks: number[] = [];
  for (let k = 0; k <= 250; k++) {
    const v = start + k * effStep;
    if (v > hi + eps) break;
    const clean = Number(v.toPrecision(10));
    ticks.push(Object.is(clean, -0) ? 0 : clean);
  }
  return ticks.length > 0 ? ticks : [lo, hi];
}

export function formatTickNumber(v: number): string {
  const abs = Math.abs(v);
  if (abs === 0) return "0";
  if (abs >= 1e5 || abs < 1e-3) return v.toExponential(1);
  if (Number.isInteger(v)) return String(v);
  return Number(v.toFixed(abs < 1 ? 3 : abs < 10 ? 2 : 1)).toString();
}

export function computeAxis2DBounds(
  series: Array<{ x: number[]; y: number[] }>,
  xlim?: [number, number] | null,
  ylim?: [number, number] | null,
  xmin?: number | null,
  xmax?: number | null,
  ymin?: number | null,
  ymax?: number | null,
): AxisBounds {
  const effXMin =
    typeof xmin === "number" && Number.isFinite(xmin)
      ? xmin
      : xlim
        ? xlim[0]
        : null;
  const effXMax =
    typeof xmax === "number" && Number.isFinite(xmax)
      ? xmax
      : xlim
        ? xlim[1]
        : null;
  const effYMin =
    typeof ymin === "number" && Number.isFinite(ymin)
      ? ymin
      : ylim
        ? ylim[0]
        : null;
  const effYMax =
    typeof ymax === "number" && Number.isFinite(ymax)
      ? ymax
      : ylim
        ? ylim[1]
        : null;

  let xMin = Infinity;
  let xMax = -Infinity;
  let yMin = Infinity;
  let yMax = -Infinity;

  for (const s of series) {
    const n = Math.min(s.x.length, s.y.length);
    for (let i = 0; i < n; i++) {
      const xv = s.x[i]!;
      const yv = s.y[i]!;
      if (Number.isFinite(xv) && Number.isFinite(yv)) {
        if (xv < xMin) xMin = xv;
        if (xv > xMax) xMax = xv;
        if (yv < yMin) yMin = yv;
        if (yv > yMax) yMax = yv;
      }
    }
  }

  if (!Number.isFinite(xMin) || !Number.isFinite(xMax)) {
    xMin = 0;
    xMax = 1;
  }
  if (!Number.isFinite(yMin) || !Number.isFinite(yMax)) {
    yMin = 0;
    yMax = 1;
  }

  let outXMin = effXMin ?? xMin;
  let outXMax = effXMax ?? xMax;
  if (outXMin > outXMax) [outXMin, outXMax] = [outXMax, outXMin];
  if (outXMin === outXMax) {
    if (effXMin !== null && effXMax === null) outXMax = outXMin + 1;
    else if (effXMax !== null && effXMin === null) outXMin = outXMax - 1;
    else {
      outXMin -= 0.5;
      outXMax += 0.5;
    }
  }

  let autoYMin: number;
  let autoYMax: number;
  if (yMin === yMax) {
    const d = yMin === 0 ? 1 : Math.abs(yMin) * 0.1;
    autoYMin = yMin - d;
    autoYMax = yMax + d;
  } else {
    const padY = (yMax - yMin) * 0.06;
    autoYMin = yMin - padY;
    autoYMax = yMax + padY;
  }

  let outYMin = effYMin ?? autoYMin;
  let outYMax = effYMax ?? autoYMax;
  if (outYMin > outYMax) [outYMin, outYMax] = [outYMax, outYMin];
  if (outYMin === outYMax) outYMax = outYMin + 1;

  return { xMin: outXMin, xMax: outXMax, yMin: outYMin, yMax: outYMax };
}

export function dataToCanvasX(
  x: number,
  area: PlotArea,
  bounds: AxisBounds,
): number {
  const span = bounds.xMax - bounds.xMin || 1;
  return area.x + ((x - bounds.xMin) / span) * area.width;
}

export function dataToCanvasY(
  y: number,
  area: PlotArea,
  bounds: AxisBounds,
): number {
  const span = bounds.yMax - bounds.yMin || 1;
  return area.y + area.height - ((y - bounds.yMin) / span) * area.height;
}

export interface LegendItemInput {
  label: string;
  color: string | null;
  linestyle?: "solid" | "dashed" | "dotted";
}

export interface PlacedLegendItem {
  label: string;
  color: string;
  linestyle: "solid" | "dashed" | "dotted";
  width: number;
}

export interface Axis2DLayout {
  area: PlotArea;
  bounds: AxisBounds;
  xTicks: number[];
  yTicks: number[];
  maxYTickWidth: number;
  legendPosition: LegendPosition;
  legendRows: PlacedLegendItem[][];
  legendBaseY: number;
  legendRowHeight: number;
  effFontScale: number;
}

export function truncateCanvasText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string {
  if (maxWidth <= 12 || ctx.measureText(text).width <= maxWidth) return text;
  const ell = "…";
  let lo = 0;
  let hi = text.length;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (ctx.measureText(text.slice(0, mid) + ell).width <= maxWidth) {
      lo = mid;
    } else {
      hi = mid - 1;
    }
  }
  return lo > 0 ? text.slice(0, lo) + ell : ell;
}

export function packLegendRows(
  ctx: CanvasRenderingContext2D,
  items: LegendItemInput[],
  cs: ResolvedCellStyle,
  availWidth: number,
  effScale = cs.font_scale,
): PlacedLegendItem[][] {
  const isRev = cs.variant === "reverse";
  const font = cs.variant === "text" ? MONOSPACE_STACK : cs.font;
  const fontPx = Math.max(10, Math.round(11.5 * effScale));
  ctx.font = `600 ${fontPx}px ${font}`;

  const swatchPlusGap = 19 * effScale;
  const itemGap = 16 * effScale;
  const maxW = Math.max(60, availWidth);

  const rows: PlacedLegendItem[][] = [];
  let curRow: PlacedLegendItem[] = [];
  let curW = 0;

  items.forEach((it, idx) => {
    const lbl = it.label.trim();
    if (!lbl) return;
    const col =
      isRev && idx === 0 && !it.color
        ? cs.reverse_ink
        : pickSeriesColor(it.color, idx, cs.accent);
    const ls = it.linestyle ?? "solid";
    const itemW = swatchPlusGap + ctx.measureText(lbl).width;
    const needed = curRow.length === 0 ? itemW : itemGap + itemW;

    if (curRow.length > 0 && curW + needed > maxW) {
      rows.push(curRow);
      curRow = [{ label: lbl, color: col, linestyle: ls, width: itemW }];
      curW = itemW;
    } else {
      curRow.push({ label: lbl, color: col, linestyle: ls, width: itemW });
      curW += needed;
    }
  });

  if (curRow.length > 0) rows.push(curRow);
  return rows;
}

export function computeAxis2DLayout(
  ctx: CanvasRenderingContext2D,
  rect: GridRect,
  cs: ResolvedCellStyle,
  bounds: AxisBounds,
  opts: {
    title: string;
    dynamic: boolean;
    xlabel: string;
    ylabel: string;
    legend: LegendPosition | boolean;
    legendItems: LegendItemInput[];
    xstep?: number | null;
    ystep?: number | null;
    xmin?: number | null;
    ymin?: number | null;
  },
): Axis2DLayout {
  const s = cs.font_scale * computeCardUiScale(rect.width, rect.height);
  const font = cs.variant === "text" ? MONOSPACE_STACK : cs.font;
  const hasTitle = opts.title.trim().length > 0;
  const hasHeader = hasTitle || opts.dynamic;
  const hasXLabel = opts.xlabel.trim().length > 0;
  const hasYLabel = opts.ylabel.trim().length > 0;

  const normLeg = normalizeLegendPosition(opts.legend);
  const hasLabels = opts.legendItems.some((i) => i.label.trim().length > 0);
  const effLeg: LegendPosition = hasLabels ? normLeg : "none";

  const padX = 20 * s;
  const badgeReserve = opts.dynamic
    ? (cs.variant === "text" ? 72 : 28) * s
    : 0;
  const legAvailW =
    rect.width -
    padX * 2 -
    (effLeg === "top" && !hasTitle ? badgeReserve : 0);

  const legendRows =
    effLeg !== "none"
      ? packLegendRows(ctx, opts.legendItems, cs, legAvailW, s)
      : [];
  const legendRowHeight = 18 * s;

  let topLegY0 = 0;
  let topPad: number;
  if (effLeg === "top" && legendRows.length > 0) {
    topLegY0 = (hasTitle ? 35 : 13) * s;
    topPad = topLegY0 + legendRows.length * legendRowHeight + 8 * s;
  } else {
    topPad = (hasHeader ? 38 : 18) * s;
  }

  const axesBotH = (hasXLabel ? 44 : 26) * s;
  const bottomPad =
    effLeg === "bottom" && legendRows.length > 0
      ? axesBotH + legendRows.length * legendRowHeight + 10 * s
      : (hasXLabel ? 46 : 30) * s;

  // Measure Y ticks first so rotated 90° ylabel NEVER collides with wide numbers
  const estHeight = Math.max(32, rect.height - topPad - bottomPad);
  const yTicksAll = computeAxisTicks(
    bounds.yMin,
    bounds.yMax,
    Math.max(3, Math.floor(estHeight / (52 * s))),
    opts.ystep,
    opts.ymin,
  );
  const yTicks = yTicksAll.filter(
    (yt) => yt >= bounds.yMin - 1e-9 && yt <= bounds.yMax + 1e-9,
  );

  const tickFontPx = Math.max(10, Math.round(11 * s));
  ctx.font = `500 ${tickFontPx}px ${font}`;
  let maxYTickWidth = 20 * s;
  for (const yt of yTicks) {
    const w = ctx.measureText(formatTickNumber(yt)).width;
    if (w > maxYTickWidth) maxYTickWidth = w;
  }

  const leftPad = hasYLabel
    ? Math.max(58 * s, 38 * s + maxYTickWidth)
    : Math.max(44 * s, 22 * s + maxYTickWidth);

  const estWidth = Math.max(40, rect.width - leftPad - 22 * s);
  const xTicksAll = computeAxisTicks(
    bounds.xMin,
    bounds.xMax,
    Math.max(3, Math.floor(estWidth / (85 * s))),
    opts.xstep,
    opts.xmin,
  );
  const xTicks = xTicksAll.filter(
    (xt) => xt >= bounds.xMin - 1e-9 && xt <= bounds.xMax + 1e-9,
  );
  const halfLastXW =
    xTicks.length > 0
      ? 0.5 * ctx.measureText(formatTickNumber(xTicks[xTicks.length - 1]!)).width
      : 0;
  const rightPad = Math.max(22 * s, halfLastXW + 14 * s);

  const area: PlotArea = {
    x: rect.x + leftPad,
    y: rect.y + topPad,
    width: Math.max(40, rect.width - leftPad - rightPad),
    height: Math.max(32, rect.height - topPad - bottomPad),
  };

  const legendBaseY =
    effLeg === "top" ? rect.y + topLegY0 : area.y + area.height + axesBotH;

  return {
    area,
    bounds,
    xTicks,
    yTicks,
    maxYTickWidth,
    legendPosition: effLeg,
    legendRows,
    legendBaseY,
    legendRowHeight,
    effFontScale: s,
  };
}

export function renderAxis2DHeaderAndLegend(
  ctx: CanvasRenderingContext2D,
  rect: GridRect,
  cs: ResolvedCellStyle,
  layout: Axis2DLayout,
  title: string,
  dynamic: boolean,
  playing: boolean,
): void {
  const s = layout.effFontScale;
  const isRev = cs.variant === "reverse";
  const isMono = cs.variant === "text";
  const padX = 20 * s;
  const padY = 13 * s;
  const badgeReserve = dynamic ? (isMono ? 72 : 28) * s : 0;

  ctx.save();
  if (title.trim().length > 0) {
    const hdrPx = Math.round(14 * s);
    const font = isMono ? MONOSPACE_STACK : cs.font;
    ctx.font = `700 ${hdrPx}px ${font}`;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";

    if (isMono) {
      const innerFit = truncateCanvasText(
        ctx,
        title,
        rect.width - padX * 2 - badgeReserve - ctx.measureText("┤  ├").width,
      );
      ctx.fillStyle = cs.accent;
      ctx.fillText("┤ ", rect.x + padX, rect.y + padY);
      const wL = ctx.measureText("┤ ").width;
      ctx.fillStyle = cs.text;
      ctx.fillText(innerFit, rect.x + padX + wL, rect.y + padY);
      const wT = ctx.measureText(innerFit).width;
      ctx.fillStyle = cs.accent;
      ctx.fillText(" ├", rect.x + padX + wL + wT, rect.y + padY);
    } else {
      const fit = truncateCanvasText(
        ctx,
        title,
        rect.width - padX * 2 - badgeReserve,
      );
      ctx.fillStyle = isRev
        ? rgbaString(cs.reverse_ink, cs.text_opacity)
        : rgbaString(cs.text, cs.text_opacity);
      ctx.fillText(fit, rect.x + padX, rect.y + padY);
    }
  }

  if (dynamic) {
    if (isMono) {
      const statusTxt = playing ? "● LIVE" : "⏸ PAUSE";
      ctx.font = `700 11px ${MONOSPACE_STACK}`;
      ctx.textAlign = "right";
      ctx.textBaseline = "top";
      ctx.fillStyle = playing ? "#22c55e" : "#eab308";
      ctx.fillText(statusTxt, rect.x + rect.width - padX, rect.y + padY + 1);
    } else {
      const dotX = rect.x + rect.width - padX - 4;
      const dotY = rect.y + padY + 7 * s;
      ctx.beginPath();
      ctx.arc(dotX, dotY, 4.2, 0, Math.PI * 2);
      ctx.fillStyle = isRev
        ? rgbaString(cs.reverse_ink, 0.85)
        : playing
          ? "#22c55e"
          : "#eab308";
      ctx.fill();
    }
  }

  // Render wrapped multi-row legend (either below title or below xlabel)
  if (layout.legendRows.length > 0) {
    const font = isMono ? MONOSPACE_STACK : cs.font;
    const fontPx = Math.max(10, Math.round(11.5 * s));
    const textCol = isRev
      ? rgbaString(cs.reverse_ink, cs.text_opacity * 0.92)
      : rgbaString(cs.text, cs.text_opacity * 0.92);

    ctx.font = `600 ${fontPx}px ${font}`;
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";

    const swLen = 14 * s;
    const swGap = 5 * s;
    const itGap = 16 * s;

    layout.legendRows.forEach((row, rIdx) => {
      const cy = layout.legendBaseY + (rIdx + 0.5) * layout.legendRowHeight;
      let curX = rect.x + padX;
      for (const item of row) {
        ctx.beginPath();
        if (item.linestyle === "dashed") ctx.setLineDash([4, 3]);
        else if (item.linestyle === "dotted") ctx.setLineDash([1.5, 2.5]);
        else ctx.setLineDash([]);
        ctx.strokeStyle = item.color;
        ctx.lineWidth = 2.4;
        ctx.moveTo(curX, cy);
        ctx.lineTo(curX + swLen, cy);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = textCol;
        ctx.fillText(item.label, curX + swLen + swGap, cy);
        curX += item.width + itGap;
      }
    });
  }
  ctx.restore();
}

export function renderAxis2DScaffold(
  ctx: CanvasRenderingContext2D,
  layout: Axis2DLayout,
  cs: ResolvedCellStyle,
  xlabel: string,
  ylabel: string,
  showGrid: boolean,
): void {
  const { area, bounds, xTicks, yTicks, maxYTickWidth, effFontScale: s } = layout;
  const isRev = cs.variant === "reverse";
  const font = cs.variant === "text" ? MONOSPACE_STACK : cs.font;
  const tickFontPx = Math.max(10, Math.round(11 * s));
  const labelFontPx = Math.max(11, Math.round(12 * s));

  const inkBase = isRev ? cs.reverse_ink : cs.muted;
  const inkAlpha = isRev ? cs.muted_opacity : 0.85;
  const gridColor = isRev
    ? rgbaString(cs.reverse_ink, 0.14)
    : rgbaString(cs.muted, 0.16);
  const spineColor = isRev
    ? rgbaString(cs.reverse_ink, 0.32)
    : rgbaString(cs.muted, 0.35);

  ctx.save();
  ctx.lineWidth = 1;

  // Batch ALL gridlines into a single stroke() call for maximum Canvas 2D throughput
  if (showGrid && (xTicks.length > 0 || yTicks.length > 0)) {
    ctx.beginPath();
    ctx.strokeStyle = gridColor;
    for (const yt of yTicks) {
      const py = dataToCanvasY(yt, area, bounds);
      ctx.moveTo(area.x, py);
      ctx.lineTo(area.x + area.width, py);
    }
    for (const xt of xTicks) {
      const px = dataToCanvasX(xt, area, bounds);
      ctx.moveTo(px, area.y);
      ctx.lineTo(px, area.y + area.height);
    }
    ctx.stroke();
  }

  // Horizontal Y tick labels
  ctx.font = `500 ${tickFontPx}px ${font}`;
  ctx.fillStyle = rgbaString(inkBase, inkAlpha);
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  const yLblStride = Math.max(
    1,
    Math.ceil(yTicks.length / Math.max(2, Math.floor(area.height / (18 * s)))),
  );
  yTicks.forEach((yt, yIdx) => {
    if (yIdx % yLblStride === 0) {
      const py = dataToCanvasY(yt, area, bounds);
      ctx.fillText(formatTickNumber(yt), area.x - 8 * s, py);
    }
  });

  // Vertical X tick labels
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const xLblStride = Math.max(
    1,
    Math.ceil(xTicks.length / Math.max(2, Math.floor(area.width / (38 * s)))),
  );
  xTicks.forEach((xt, xIdx) => {
    if (xIdx % xLblStride === 0) {
      const px = dataToCanvasX(xt, area, bounds);
      ctx.fillText(formatTickNumber(xt), px, area.y + area.height + 7 * s);
    }
  });

  // Axis L-spine
  ctx.beginPath();
  ctx.strokeStyle = spineColor;
  ctx.lineWidth = 1.2;
  ctx.moveTo(area.x, area.y);
  ctx.lineTo(area.x, area.y + area.height);
  ctx.lineTo(area.x + area.width, area.y + area.height);
  ctx.stroke();

  // X (bottom) & Y (left rotated -90°) axis titles
  ctx.font = `600 ${labelFontPx}px ${font}`;
  ctx.fillStyle = rgbaString(inkBase, Math.min(1, inkAlpha + 0.12));
  if (xlabel) {
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText(xlabel, area.x + area.width / 2, area.y + area.height + 25 * s);
  }
  if (ylabel) {
    const yLabelX = Math.max(
      rectSafeLeft(area.x, maxYTickWidth, s),
      8 * s,
    );
    ctx.save();
    ctx.translate(yLabelX, area.y + area.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(ylabel, 0, 0);
    ctx.restore();
  }

  ctx.restore();
}

function rectSafeLeft(areaX: number, maxYTickWidth: number, s: number): number {
  return areaX - 16 * s - maxYTickWidth;
}

export function findNearestPlotPoint(
  cell: PlotCellSpec,
  area: PlotArea,
  bounds: AxisBounds,
  worldX: number,
  worldY: number,
): SnappedPoint | null {
  if (
    worldX < area.x - 10 ||
    worldX > area.x + area.width + 10 ||
    worldY < area.y - 10 ||
    worldY > area.y + area.height + 10
  ) {
    return null;
  }

  let best: SnappedPoint | null = null;
  let bestScore = Infinity;

  cell.series.forEach((s, sIdx) => {
    const n = Math.min(s.x.length, s.y.length);
    const col = pickSeriesColor(s.color, sIdx, cell.color ?? "#38bdf8");
    for (let i = 0; i < n; i++) {
      const dxData = s.x[i]!;
      const dyData = s.y[i]!;
      if (!Number.isFinite(dxData) || !Number.isFinite(dyData)) continue;
      const cx = dataToCanvasX(dxData, area, bounds);
      const cy = dataToCanvasY(dyData, area, bounds);
      // Prioritize horizontal proximity (cursor column) with slight vertical tie-breaking
      const dist = Math.abs(cx - worldX) * 2.2 + Math.abs(cy - worldY) * 0.45;
      if (dist < bestScore) {
        bestScore = dist;
        best = {
          seriesIndex: sIdx,
          seriesLabel: s.label,
          color: col,
          dataX: dxData,
          dataY: dyData,
          canvasX: cx,
          canvasY: cy,
        };
      }
    }
  });

  return best;
}

export function renderHoverTooltip(
  ctx: CanvasRenderingContext2D,
  area: PlotArea,
  snapped: SnappedPoint,
  cs: ResolvedCellStyle,
  alpha: number,
): void {
  if (alpha <= 0.01) return;
  const font = cs.variant === "text" ? MONOSPACE_STACK : cs.font;

  ctx.save();
  ctx.globalAlpha = alpha;

  // Vertical magnetic crosshair line
  ctx.beginPath();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = rgbaString(snapped.color, 0.55);
  ctx.lineWidth = 1.2;
  ctx.moveTo(snapped.canvasX, area.y);
  ctx.lineTo(snapped.canvasX, area.y + area.height);
  ctx.stroke();
  ctx.setLineDash([]);

  // Highlight glow + crisp dot on snapped point
  ctx.beginPath();
  ctx.arc(snapped.canvasX, snapped.canvasY, 7, 0, Math.PI * 2);
  ctx.fillStyle = rgbaString(snapped.color, 0.28);
  ctx.fill();

  ctx.beginPath();
  ctx.arc(snapped.canvasX, snapped.canvasY, 4, 0, Math.PI * 2);
  ctx.fillStyle = snapped.color;
  ctx.fill();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = "#ffffff";
  ctx.stroke();

  // Floating glass tooltip pill
  const coordText = `(${formatTickNumber(snapped.dataX)}, ${formatTickNumber(snapped.dataY)})`;
  const text = snapped.seriesLabel
    ? `${snapped.seriesLabel}: ${coordText}`
    : coordText;

  ctx.font = `600 11.5px ${font}`;
  const tw = ctx.measureText(text).width;
  const boxW = tw + 20;
  const boxH = 26;
  let bx = snapped.canvasX + 10;
  let by = snapped.canvasY - boxH - 10;
  if (bx + boxW > area.x + area.width) bx = snapped.canvasX - boxW - 10;
  if (by < area.y) by = snapped.canvasY + 10;

  ctx.beginPath();
  addRoundedRectSubpath(ctx, bx, by, boxW, boxH, 7);
  ctx.fillStyle = "rgba(15, 23, 42, 0.90)";
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = rgbaString(snapped.color, 0.75);
  ctx.stroke();

  ctx.fillStyle = "#f8fafc";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(text, bx + 10, by + boxH / 2);

  ctx.restore();
}
