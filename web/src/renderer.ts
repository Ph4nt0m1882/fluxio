import { computeGridRects, type GridRect, type Viewport } from "./layout";
import type { FigureSpec } from "./protocol";
import { resolveCellStyle, rgbaString, type ThemeSpec } from "./themes";
import { buildTaperedAccentSvgPath } from "./charts/base";
import { renderNumberChart } from "./charts/number";
import { renderPlotChart, type PlotCacheMeta } from "./charts/plot";

export { buildTaperedAccentSvgPath };

export interface CellLayerCacheEntry {
  canvas: HTMLCanvasElement;
  key: string;
  plotMeta?: PlotCacheMeta;
}

export interface RenderState {
  spec: FigureSpec;
  viewport: Viewport;
  hoverProgress: Map<string, number>;
  pointerWorld?: { x: number; y: number } | null;
  playing: boolean;
  elapsedSeconds: number;
  bgImage?: HTMLImageElement | null;
  bgCache?: { canvas: HTMLCanvasElement; key: string } | null;
  cellCache?: Map<string, CellLayerCacheEntry>;
  partialDynamicOnly?: boolean;
}

export function computeFigureUiScale(width: number, height: number): number {
  const r = Math.min(width / 960, height / 560);
  return r > 1.05 ? Math.min(2.2, 1 + (r - 1) * 0.55) : 1.0;
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

export function computeHeaderHeight(
  spec: FigureSpec,
  uiScale = 1.0,
): number {
  if (!spec.title && !spec.subtitle) {
    return 0;
  }
  const s = spec.theme.font_scale * uiScale;
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
  const {
    spec,
    viewport,
    hoverProgress,
    pointerWorld,
    playing,
    bgImage,
    bgCache,
    cellCache,
    partialDynamicOnly,
  } = state;
  const theme = spec.theme;
  const uiScale = computeFigureUiScale(logicalWidth, logicalHeight);
  const headerHeight = computeHeaderHeight(spec, uiScale);

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

  const physW = Math.round(logicalWidth * dpr);
  const physH = Math.round(logicalHeight * dpr);

  // Fast incremental dirty-rect path on pure animation ticks: ONLY repaint dynamic cells!
  if (
    partialDynamicOnly &&
    viewport.scale === 1 &&
    viewport.offsetX === 0 &&
    viewport.offsetY === 0 &&
    bgCache &&
    bgCache.key !== "" &&
    !theme.transparent &&
    theme.background_spec.type !== "transparent"
  ) {
    for (const cell of spec.cells) {
      if (!cell.dynamic) continue;
      const rect = rectMap.get(cell.id);
      if (!rect) continue;
      const cs = resolveCellStyle(spec.theme, cell.style, cell.color);
      const rawHover = hoverProgress.get(cell.id) ?? 0;

      const rx = Math.max(0, Math.floor(rect.x - 3));
      const ry = Math.max(0, Math.floor(rect.y - 3));
      const rw = Math.min(logicalWidth - rx, Math.ceil(rect.width + 6));
      const rh = Math.min(logicalHeight - ry, Math.ceil(rect.height + 6));

      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.beginPath();
      ctx.rect(rx, ry, rw, rh);
      ctx.clip();
      ctx.drawImage(
        bgCache.canvas,
        rx * dpr,
        ry * dpr,
        rw * dpr,
        rh * dpr,
        rx,
        ry,
        rw,
        rh,
      );

      let cacheEntry: CellLayerCacheEntry | undefined;
      if (cellCache && typeof document !== "undefined") {
        cacheEntry = cellCache.get(cell.id);
        if (!cacheEntry) {
          cacheEntry = { canvas: document.createElement("canvas"), key: "" };
          cellCache.set(cell.id, cacheEntry);
        }
      }

      if (cell.kind === "number") {
        renderNumberChart(ctx, cell, rect, cs, rawHover, playing);
      } else if (cell.kind === "plot") {
        renderPlotChart(
          ctx,
          cell,
          rect,
          cs,
          rawHover,
          playing,
          pointerWorld ?? null,
          dpr,
          cacheEntry,
        );
      }
      ctx.restore();
    }
    return rects;
  }

  ctx.save();
  if (
    bgCache &&
    !theme.transparent &&
    theme.background_spec.type !== "transparent"
  ) {
    const imgReady =
      theme.background_spec.type === "image"
        ? Boolean(bgImage && bgImage.complete && bgImage.naturalWidth > 0)
        : false;
    const nextKey = `${physW}x${physH}|${theme.background}|${JSON.stringify(theme.background_spec)}|${imgReady}`;
    if (bgCache.key !== nextKey) {
      bgCache.canvas.width = physW;
      bgCache.canvas.height = physH;
      const bctx =
        bgCache.canvas.getContext("2d", { alpha: false }) ??
        bgCache.canvas.getContext("2d");
      if (bctx) {
        bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        renderBackground(bctx, logicalWidth, logicalHeight, theme, bgImage);
        bgCache.key = nextKey;
      }
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(bgCache.canvas, 0, 0);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  } else {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, logicalWidth, logicalHeight);
    renderBackground(ctx, logicalWidth, logicalHeight, theme, bgImage);
  }

  ctx.translate(viewport.offsetX, viewport.offsetY);
  ctx.scale(viewport.scale, viewport.scale);

  const titlePx = Math.round(18 * theme.font_scale * uiScale);
  const subPx = Math.round(13 * theme.font_scale * uiScale);
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
      theme.padding + (spec.title ? titlePx + Math.round(6 * uiScale) : 0),
    );
  }

  const canUseCellCache =
    Boolean(cellCache) &&
    viewport.scale === 1 &&
    typeof document !== "undefined";

  for (const cell of spec.cells) {
    const rect = rectMap.get(cell.id);
    if (!rect) continue;
    const rawHover = hoverProgress.get(cell.id) ?? 0;
    const cs = resolveCellStyle(spec.theme, cell.style, cell.color);

    let cacheEntry: CellLayerCacheEntry | undefined;
    if (canUseCellCache && cellCache) {
      cacheEntry = cellCache.get(cell.id);
      if (!cacheEntry) {
        cacheEntry = { canvas: document.createElement("canvas"), key: "" };
        cellCache.set(cell.id, cacheEntry);
      }
    }

    switch (cell.kind) {
      case "number": {
        if (cacheEntry && !cell.dynamic) {
          const pad = 2;
          const pw = Math.max(4, Math.ceil((rect.width + pad * 2) * dpr));
          const ph = Math.max(4, Math.ceil((rect.height + pad * 2) * dpr));
          const hStep = Math.round(rawHover * 40);
          const key = `num|${pw}x${ph}|${dpr}|${hStep}|${cell.formatted}|${cell.unit}`;
          if (cacheEntry.key !== key) {
            cacheEntry.canvas.width = pw;
            cacheEntry.canvas.height = ph;
            const cctx = cacheEntry.canvas.getContext("2d");
            if (cctx) {
              cctx.setTransform(dpr, 0, 0, dpr, 0, 0);
              const localRect: GridRect = {
                id: rect.id,
                x: pad,
                y: pad,
                width: rect.width,
                height: rect.height,
              };
              renderNumberChart(cctx, cell, localRect, cs, rawHover, playing);
              cacheEntry.key = key;
            }
          }
          ctx.drawImage(
            cacheEntry.canvas,
            rect.x - pad,
            rect.y - pad,
            pw / dpr,
            ph / dpr,
          );
        } else {
          renderNumberChart(ctx, cell, rect, cs, rawHover, playing);
        }
        break;
      }
      case "plot":
        renderPlotChart(
          ctx,
          cell,
          rect,
          cs,
          rawHover,
          playing,
          pointerWorld ?? null,
          dpr,
          cacheEntry,
        );
        break;
    }
  }

  ctx.restore();
  return rects;
}
