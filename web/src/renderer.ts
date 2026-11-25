import { computeGridRects, type GridRect, type Viewport } from "./layout";
import type { FigureSpec, NumberCellSpec } from "./protocol";
import { buildBlockMatrix, splitBlockRenderable } from "./text_digits";
import {
  lerpRgba,
  MONOSPACE_STACK,
  resolveCellStyle,
  rgbaString,
  smoothstep,
  type AccentSide,
  type ResolvedCellStyle,
  type ThemeSpec,
} from "./themes";

export interface RenderState {
  spec: FigureSpec;
  viewport: Viewport;
  hoverProgress: Map<string, number>;
  playing: boolean;
  elapsedSeconds: number;
  bgImage?: HTMLImageElement | null;
}

/** Crisp Material-inspired monochrome SVG icons (zero OS emoji inconsistency). */
export const TOOLBAR_ICONS = {
  play: `<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true"><path d="M8 5.14v13.72a1 1 0 0 0 1.55.83l10.29-6.86a1 1 0 0 0 0-1.66L9.55 4.31A1 1 0 0 0 8 5.14z"/></svg>`,
  pause: `<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true"><path d="M6 5h4v14H6V5zm8 0h4v14h-4V5z"/></svg>`,
  replay: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>`,
  zoomOut: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M5 12h14"/></svg>`,
  zoomIn: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3.5"/></svg>`,
  fullscreen: `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>`,
} as const;

function addRoundedRectSubpath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

function roundedRectSvgSubpath(
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): string {
  const R = Math.max(0, Math.min(r, w / 2, h / 2));
  const f = (n: number): string => n.toFixed(2);
  return (
    `M ${f(x + R)} ${f(y)} ` +
    `L ${f(x + w - R)} ${f(y)} ` +
    `A ${f(R)} ${f(R)} 0 0 1 ${f(x + w)} ${f(y + R)} ` +
    `L ${f(x + w)} ${f(y + h - R)} ` +
    `A ${f(R)} ${f(R)} 0 0 1 ${f(x + w - R)} ${f(y + h)} ` +
    `L ${f(x + R)} ${f(y + h)} ` +
    `A ${f(R)} ${f(R)} 0 0 1 ${f(x)} ${f(y + h - R)} ` +
    `L ${f(x)} ${f(y + R)} ` +
    `A ${f(R)} ${f(R)} 0 0 1 ${f(x + R)} ${f(y)} Z`
  );
}

function computeCrescentInnerRect(
  rect: GridRect,
  side: AccentSide,
  accentWidth: number,
): { x: number; y: number; w: number; h: number } | null {
  if (side === "none" || accentWidth <= 0) return null;
  const { x, y, width: w, height: h } = rect;
  const t = Math.max(0, Math.min(accentWidth, w * 0.45, h * 0.45));
  if (side === "left") return { x: x + t, y, w: w - t, h };
  if (side === "right") return { x, y, w: w - t, h };
  if (side === "top") return { x, y: y + t, w, h: h - t };
  if (side === "bottom") return { x, y, w, h: h - t };
  return null;
}

export function buildTaperedAccentSvgPath(
  rect: GridRect,
  radius: number,
  side: AccentSide,
  accentWidth: number,
): string {
  const inner = computeCrescentInnerRect(rect, side, accentWidth);
  if (!inner) return "";
  const outerPath = roundedRectSvgSubpath(
    rect.x,
    rect.y,
    rect.width,
    rect.height,
    radius,
  );
  const innerPath = roundedRectSvgSubpath(
    inner.x,
    inner.y,
    inner.w,
    inner.h,
    radius,
  );
  return `${outerPath} ${innerPath}`;
}

function fillInsetRoundedRing(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
  thickness: number,
  fillStyle: string,
): void {
  if (thickness <= 0 || w <= thickness * 2 || h <= thickness * 2) return;
  ctx.beginPath();
  addRoundedRectSubpath(ctx, x, y, w, h, r);
  addRoundedRectSubpath(
    ctx,
    x + thickness,
    y + thickness,
    w - thickness * 2,
    h - thickness * 2,
    Math.max(0, r - thickness),
  );
  ctx.fillStyle = fillStyle;
  ctx.fill("evenodd");
}

function fillTaperedAccentCrescent(
  ctx: CanvasRenderingContext2D,
  rect: GridRect,
  radius: number,
  side: AccentSide,
  accentWidth: number,
  color: string,
): void {
  const inner = computeCrescentInnerRect(rect, side, accentWidth);
  if (!inner) return;
  ctx.beginPath();
  addRoundedRectSubpath(ctx, rect.x, rect.y, rect.width, rect.height, radius);
  addRoundedRectSubpath(ctx, inner.x, inner.y, inner.w, inner.h, radius);
  ctx.fillStyle = color;
  ctx.fill("evenodd");
}

function renderBackground(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  theme: ThemeSpec,
  bgImage?: HTMLImageElement | null,
): void {
  const bg = theme.background_spec;
  if (theme.transparent || bg.type === "transparent") {
    return;
  }

  if (bg.type === "gradient" && bg.stops.length > 0) {
    let grad: CanvasGradient;
    if (bg.kind === "radial") {
      grad = ctx.createRadialGradient(
        w / 2,
        h / 2,
        0,
        w / 2,
        h / 2,
        Math.hypot(w, h) * 0.6,
      );
    } else {
      const rad = ((bg.angle - 90) * Math.PI) / 180;
      const halfLen =
        (Math.abs(w * Math.cos(rad)) + Math.abs(h * Math.sin(rad))) / 2;
      const cx = w / 2;
      const cy = h / 2;
      grad = ctx.createLinearGradient(
        cx - Math.cos(rad) * halfLen,
        cy - Math.sin(rad) * halfLen,
        cx + Math.cos(rad) * halfLen,
        cy + Math.sin(rad) * halfLen,
      );
    }
    if (bg.stops.length === 1) {
      grad.addColorStop(0, bg.stops[0]!);
      grad.addColorStop(1, bg.stops[0]!);
    } else {
      bg.stops.forEach((stop, i) => {
        grad.addColorStop(i / (bg.stops.length - 1), stop);
      });
    }
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);
    return;
  }

  if (bg.type === "image") {
    ctx.fillStyle = theme.background;
    ctx.fillRect(0, 0, w, h);

    if (bgImage && bgImage.complete && bgImage.naturalWidth > 0) {
      ctx.save();
      ctx.globalAlpha = Math.max(0, Math.min(1, bg.opacity));
      const iw = bgImage.naturalWidth;
      const ih = bgImage.naturalHeight;
      if (bg.fit === "stretch") {
        ctx.drawImage(bgImage, 0, 0, w, h);
      } else {
        const scale =
          bg.fit === "contain"
            ? Math.min(w / iw, h / ih)
            : Math.max(w / iw, h / ih);
        const dw = iw * scale;
        const dh = ih * scale;
        ctx.drawImage(bgImage, (w - dw) / 2, (h - dh) / 2, dw, dh);
      }
      ctx.restore();
    }

    if (bg.overlay && bg.overlay_opacity > 0) {
      ctx.fillStyle = rgbaString(bg.overlay, bg.overlay_opacity);
      ctx.fillRect(0, 0, w, h);
    }
    return;
  }

  ctx.fillStyle = bg.type === "solid" ? bg.color : theme.background;
  ctx.fillRect(0, 0, w, h);
}

export function computeHeaderHeight(spec: FigureSpec): number {
  if (!spec.title && !spec.subtitle) {
    return 0;
  }
  const s = spec.theme.font_scale;
  if (spec.title && spec.subtitle) {
    return Math.round(56 * s);
  }
  return Math.round(38 * s);
}

export function renderFigureToCanvas(
  ctx: CanvasRenderingContext2D,
  logicalWidth: number,
  logicalHeight: number,
  dpr: number,
  state: RenderState,
): GridRect[] {
  const { spec, viewport, hoverProgress, playing, bgImage } = state;
  const theme = spec.theme;

  ctx.save();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, logicalWidth, logicalHeight);

  renderBackground(ctx, logicalWidth, logicalHeight, theme, bgImage);

  ctx.translate(viewport.offsetX, viewport.offsetY);
  ctx.scale(viewport.scale, viewport.scale);

  const headerHeight = computeHeaderHeight(spec);
  const titlePx = Math.round(18 * theme.font_scale);
  const subPx = Math.round(13 * theme.font_scale);
  const titlePrefix = theme.variant === "text" ? "▸ " : "";

  if (spec.title) {
    ctx.fillStyle = theme.variant === "text" ? theme.accent : theme.title_color;
    ctx.font = `700 ${titlePx}px ${theme.font}`;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";
    ctx.fillText(`${titlePrefix}${spec.title}`, theme.padding, theme.padding);
  }
  if (spec.subtitle) {
    ctx.fillStyle = theme.subtitle_color;
    ctx.font = `400 ${subPx}px ${theme.font}`;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";
    ctx.fillText(
      spec.subtitle,
      theme.padding,
      theme.padding + (spec.title ? titlePx + 6 : 0),
    );
  }

  const rects = computeGridRects({
    width: logicalWidth,
    height: logicalHeight,
    rows: spec.rows,
    cols: spec.cols,
    padding: theme.padding,
    gap: theme.gap,
    headerHeight,
    cells: spec.cells,
  });

  const rectMap = new Map(rects.map((r) => [r.id, r]));

  for (const cell of spec.cells) {
    const rect = rectMap.get(cell.id);
    if (!rect) continue;
    const rawHover = hoverProgress.get(cell.id) ?? 0;
    const cs = resolveCellStyle(spec.theme, cell.style, cell.color);
    if (cs.variant === "text") {
      renderTextTuiCell(ctx, cell, rect, cs, rawHover, playing);
    } else {
      renderModernCardCell(ctx, cell, rect, cs, rawHover, playing);
    }
  }

  ctx.restore();
  return rects;
}

function renderModernCardCell(
  ctx: CanvasRenderingContext2D,
  cell: NumberCellSpec,
  rect: GridRect,
  cs: ResolvedCellStyle,
  rawHoverProgress: number,
  playing: boolean,
): void {
  const eased = smoothstep(rawHoverProgress);
  const isReverse = cs.variant === "reverse";

  // 1. Card background fill: solid accent in `reverse`, translucent veil in `classic`
  if (isReverse) {
    const revAlpha = Math.min(1, Math.max(0, cs.surface_opacity));
    ctx.beginPath();
    addRoundedRectSubpath(ctx, rect.x, rect.y, rect.width, rect.height, cs.radius);
    ctx.fillStyle = rgbaString(cs.accent, revAlpha);
    ctx.fill();

    // Subtle progressive sheen on hover
    if (eased > 0) {
      ctx.fillStyle = rgbaString(cs.reverse_ink, 0.06 * eased);
      ctx.fill();
    }
  } else {
    const veilAlpha = Math.min(1, Math.max(0, cs.surface_opacity + 0.035 * eased));
    if (veilAlpha > 0) {
      ctx.beginPath();
      addRoundedRectSubpath(ctx, rect.x, rect.y, rect.width, rect.height, cs.radius);
      ctx.fillStyle = rgbaString(cs.surface, veilAlpha);
      ctx.fill();
    }
  }

  // 2. Inset border ring + tapered crescent
  const bw = cs.border_width + (cs.hover_border_width - cs.border_width) * eased;
  if (isReverse) {
    fillInsetRoundedRing(
      ctx,
      rect.x,
      rect.y,
      rect.width,
      rect.height,
      cs.radius,
      bw,
      rgbaString(cs.reverse_ink, 0.18 + 0.36 * eased),
    );
    fillTaperedAccentCrescent(
      ctx,
      rect,
      cs.radius,
      cs.accent_side,
      cs.accent_width,
      rgbaString(cs.reverse_ink, 0.28 + 0.18 * eased),
    );
  } else {
    if (bw > 0 && (cs.border_opacity > 0 || eased > 0)) {
      const ringColor = lerpRgba(
        cs.border,
        cs.border_opacity,
        cs.accent,
        0.95,
        eased,
      );
      fillInsetRoundedRing(
        ctx,
        rect.x,
        rect.y,
        rect.width,
        rect.height,
        cs.radius,
        bw,
        ringColor,
      );
    }
    fillTaperedAccentCrescent(
      ctx,
      rect,
      cs.radius,
      cs.accent_side,
      cs.accent_width,
      cs.accent,
    );
  }

  ctx.save();
  ctx.beginPath();
  addRoundedRectSubpath(ctx, rect.x, rect.y, rect.width, rect.height, cs.radius);
  ctx.clip();

  const padX = Math.min(28, Math.max(16, rect.width * 0.07));
  const padY = Math.min(22, Math.max(12, rect.height * 0.085));

  const labelFill = isReverse
    ? rgbaString(cs.reverse_ink, cs.muted_opacity)
    : rgbaString(cs.muted, cs.muted_opacity);
  const valueFill = isReverse
    ? rgbaString(cs.reverse_ink, cs.text_opacity)
    : rgbaString(cs.text, cs.text_opacity);
  const unitFill = isReverse
    ? rgbaString(cs.reverse_ink, cs.muted_opacity)
    : rgbaString(cs.unit_color, cs.text_opacity);

  if (cell.label) {
    const labelFontPx = Math.round(
      Math.min(16, Math.max(11, rect.height * 0.085)) * cs.font_scale,
    );
    ctx.fillStyle = labelFill;
    ctx.font = `600 ${labelFontPx}px ${cs.font}`;
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(cell.label, rect.x + padX, rect.y + padY + 2);
  }

  if (cell.dynamic) {
    const dotR = 4.5;
    const dotX = rect.x + rect.width - padX - dotR;
    const dotY = rect.y + padY + 8;
    ctx.beginPath();
    ctx.arc(dotX, dotY, dotR, 0, Math.PI * 2);
    ctx.fillStyle = isReverse
      ? rgbaString(cs.reverse_ink, 0.85)
      : playing
        ? "#22c55e"
        : "#eab308";
    ctx.fill();
  }

  let valueFontPx = Math.round(
    Math.min(rect.height * 0.42, rect.width * 0.28, 96) * cs.font_scale,
  );
  valueFontPx = Math.max(18, valueFontPx);

  ctx.font = `700 ${valueFontPx}px ${cs.font}`;
  let valMetrics = ctx.measureText(cell.formatted);
  const unitFontPx = Math.max(13, Math.round(valueFontPx * 0.42));
  ctx.font = `600 ${unitFontPx}px ${cs.font}`;
  const unitText = cell.unit ? ` ${cell.unit}` : "";
  const unitMetrics = ctx.measureText(unitText);

  const maxAvailableW = Math.max(24, rect.width - padX * 2);
  const totalW = valMetrics.width + unitMetrics.width;
  if (totalW > maxAvailableW && totalW > 0) {
    const shrink = maxAvailableW / totalW;
    valueFontPx = Math.max(14, Math.floor(valueFontPx * shrink));
  }

  const finalUnitPx = Math.max(11, Math.round(valueFontPx * 0.42));
  ctx.font = `700 ${valueFontPx}px ${cs.font}`;
  valMetrics = ctx.measureText(cell.formatted);
  ctx.font = `600 ${finalUnitPx}px ${cs.font}`;
  const finalUnitW = cell.unit ? ctx.measureText(unitText).width : 0;

  const groupW = valMetrics.width + finalUnitW;
  const startX = rect.x + (rect.width - groupW) / 2;
  const centerY = rect.y + rect.height * (cell.label ? 0.56 : 0.5);

  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.font = `700 ${valueFontPx}px ${cs.font}`;
  ctx.fillStyle = valueFill;
  ctx.fillText(cell.formatted, startX, centerY);

  if (cell.unit) {
    ctx.font = `600 ${finalUnitPx}px ${cs.font}`;
    ctx.fillStyle = unitFill;
    ctx.fillText(unitText, startX + valMetrics.width, centerY + valueFontPx * 0.08);
  }

  if (cell.description && rect.height >= 130) {
    const descPx = Math.max(10, Math.round(12 * cs.font_scale));
    ctx.font = `400 ${descPx}px ${cs.font}`;
    ctx.fillStyle = labelFill;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(
      cell.description,
      rect.x + rect.width / 2,
      rect.y + rect.height - padY,
      maxAvailableW,
    );
  }

  ctx.restore();
}

function renderTextTuiCell(
  ctx: CanvasRenderingContext2D,
  cell: NumberCellSpec,
  rect: GridRect,
  cs: ResolvedCellStyle,
  rawHoverProgress: number,
  playing: boolean,
): void {
  const eased = smoothstep(rawHoverProgress);
  const monoFont = MONOSPACE_STACK;
  const radius = Math.min(10, cs.radius);

  // TUI dark console surface
  ctx.beginPath();
  addRoundedRectSubpath(ctx, rect.x, rect.y, rect.width, rect.height, radius);
  ctx.fillStyle = rgbaString("#090d16", 0.72 + 0.08 * eased);
  ctx.fill();

  // Crisp terminal frame + heavy accent bar on chosen side
  const frameColor = lerpRgba(cs.border, 0.45, cs.accent, 0.98, eased);
  fillInsetRoundedRing(
    ctx,
    rect.x,
    rect.y,
    rect.width,
    rect.height,
    radius,
    1.5 + 1.0 * eased,
    frameColor,
  );
  fillTaperedAccentCrescent(
    ctx,
    rect,
    radius,
    cs.accent_side,
    Math.max(4, cs.accent_width * 0.75),
    cs.accent,
  );

  ctx.save();
  ctx.beginPath();
  addRoundedRectSubpath(ctx, rect.x, rect.y, rect.width, rect.height, radius);
  ctx.clip();

  const padX = 18;
  const padY = 14;

  // btop-style header tab: ┤ Label ├
  if (cell.label) {
    const lblPx = Math.round(13 * cs.font_scale);
    ctx.font = `700 ${lblPx}px ${monoFont}`;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";
    ctx.fillStyle = cs.accent;
    ctx.fillText("┤ ", rect.x + padX, rect.y + padY);
    const wLeft = ctx.measureText("┤ ").width;
    ctx.fillStyle = cs.text;
    ctx.fillText(cell.label, rect.x + padX + wLeft, rect.y + padY);
    const wLbl = ctx.measureText(cell.label).width;
    ctx.fillStyle = cs.accent;
    ctx.fillText(" ├", rect.x + padX + wLeft + wLbl, rect.y + padY);
  }

  if (cell.dynamic) {
    const statusTxt = playing ? "● LIVE" : "⏸ PAUSE";
    ctx.font = `700 11px ${monoFont}`;
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillStyle = playing ? "#22c55e" : "#eab308";
    ctx.fillText(statusTxt, rect.x + rect.width - padX, rect.y + padY + 1);
  }

  // Render btop 6-row block matrix digits when possible, else crisp monospace fallback
  const { prefix, core } = splitBlockRenderable(cell.formatted);
  const matrix = buildBlockMatrix(core);
  const maxAvailW = Math.max(40, rect.width - padX * 2);
  const centerY = rect.y + rect.height * (cell.label ? 0.56 : 0.5);

  if (matrix && matrix[0]!.length > 0 && rect.height >= 115) {
    const cols = matrix[0]!.length;
    const unitStr = cell.unit ? ` ${cell.unit}` : "";
    const unitPx = Math.round(Math.min(22, Math.max(13, rect.height * 0.11)) * cs.font_scale);
    ctx.font = `700 ${unitPx}px ${monoFont}`;
    const prefixW = prefix ? ctx.measureText(`${prefix} `).width : 0;
    const unitW = unitStr ? ctx.measureText(unitStr).width + 6 : 0;

    const maxBlockAreaW = Math.max(24, maxAvailW - prefixW - unitW);
    const cellSize = Math.floor(
      Math.min(
        (rect.height * 0.42 * cs.font_scale) / 6,
        maxBlockAreaW / cols,
        14,
      ),
    );

    if (cellSize >= 4) {
      const gridW = cols * cellSize;
      const gridH = 6 * cellSize;
      const totalGroupW = prefixW + gridW + unitW;
      const startX = rect.x + (rect.width - totalGroupW) / 2;
      const topY = centerY - gridH / 2;
      const gap = cellSize >= 7 ? 1 : 0;

      if (prefix) {
        ctx.fillStyle = cs.accent;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(`${prefix} `, startX, centerY);
      }

      const gx0 = startX + prefixW;
      ctx.fillStyle = rgbaString(cs.text, cs.text_opacity);
      for (let r = 0; r < 6; r++) {
        const rowStr = matrix[r]!;
        for (let c = 0; c < cols; c++) {
          if (rowStr[c] === "1") {
            ctx.fillRect(
              Math.round(gx0 + c * cellSize),
              Math.round(topY + r * cellSize),
              Math.max(1, cellSize - gap),
              Math.max(1, cellSize - gap),
            );
          }
        }
      }

      if (unitStr) {
        ctx.fillStyle = cs.accent;
        ctx.textAlign = "left";
        ctx.textBaseline = "bottom";
        ctx.fillText(unitStr, gx0 + gridW + 6, topY + gridH);
      }
    } else {
      drawMonospaceFallbackValue(ctx, cell, rect, cs, centerY, maxAvailW);
    }
  } else {
    drawMonospaceFallbackValue(ctx, cell, rect, cs, centerY, maxAvailW);
  }

  if (cell.description && rect.height >= 135) {
    ctx.font = `400 ${Math.round(11.5 * cs.font_scale)}px ${monoFont}`;
    ctx.fillStyle = cs.muted;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(
      `// ${cell.description}`,
      rect.x + rect.width / 2,
      rect.y + rect.height - padY + 2,
      maxAvailW,
    );
  }

  ctx.restore();
}

function drawMonospaceFallbackValue(
  ctx: CanvasRenderingContext2D,
  cell: NumberCellSpec,
  rect: GridRect,
  cs: ResolvedCellStyle,
  centerY: number,
  maxAvailW: number,
): void {
  const monoFont = MONOSPACE_STACK;
  const valPx = Math.max(16, Math.round(Math.min(rect.height * 0.32, 48) * cs.font_scale));
  ctx.font = `700 ${valPx}px ${monoFont}`;
  ctx.fillStyle = rgbaString(cs.text, cs.text_opacity);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const full = cell.unit ? `${cell.formatted} ${cell.unit}` : cell.formatted;
  ctx.fillText(full, rect.x + rect.width / 2, centerY, maxAvailW);
}
