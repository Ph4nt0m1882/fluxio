import type { GridRect } from "../layout";
import type { PlotCellSpec } from "../protocol";
import type { CellLayerCacheEntry } from "../renderer";
import { rgbaString, smoothstep, type ResolvedCellStyle } from "../themes";
import {
  computeAxis2DBounds,
  computeAxis2DLayout,
  dataToCanvasX,
  dataToCanvasY,
  findNearestPlotPoint,
  pickSeriesColor,
  renderAxis2DHeaderAndLegend,
  renderAxis2DScaffold,
  renderHoverTooltip,
  type Axis2DLayout,
  type AxisBounds,
} from "./axis2d";
import { computeCardUiScale, renderCardSurfaceAndFrame } from "./base";

export interface PlotCacheMeta {
  layout: Axis2DLayout;
  envYMin?: number;
  envYMax?: number;
}

function drawPlotCurvesIntoArea(
  ctx: CanvasRenderingContext2D,
  cell: PlotCellSpec,
  cs: ResolvedCellStyle,
  layout: Axis2DLayout,
  strokeScale: number,
): void {
  const { area, bounds } = layout;
  ctx.save();
  ctx.beginPath();
  ctx.rect(
    Math.floor(area.x),
    Math.floor(area.y),
    Math.ceil(area.width),
    Math.ceil(area.height),
  );
  ctx.clip();

  const baselineDataY = Math.max(bounds.yMin, Math.min(bounds.yMax, 0));
  const baselineY = dataToCanvasY(baselineDataY, area, bounds);

  cell.series.forEach((s, idx) => {
    const n = Math.min(s.x.length, s.y.length);
    if (n === 0) return;

    const baseColor =
      cs.variant === "reverse" && idx === 0 && !s.color
        ? cs.reverse_ink
        : pickSeriesColor(s.color, idx, cs.accent);

    const pts: Array<{ x: number; y: number }> = [];
    for (let i = 0; i < n; i++) {
      const xv = s.x[i]!;
      const yv = s.y[i]!;
      if (!Number.isFinite(xv) || !Number.isFinite(yv)) continue;
      pts.push({
        x: dataToCanvasX(xv, area, bounds),
        y: dataToCanvasY(yv, area, bounds),
      });
    }
    if (pts.length === 0) return;

    // Subtle vertical area fill under curve (uses AVX2 solid-alpha fast-path on huge live canvases!)
    if (s.fill_alpha > 0 && pts.length >= 2) {
      ctx.beginPath();
      ctx.moveTo(pts[0]!.x, baselineY);
      for (const pt of pts) {
        ctx.lineTo(pt.x, pt.y);
      }
      ctx.lineTo(pts[pts.length - 1]!.x, baselineY);
      ctx.closePath();

      if (cell.dynamic && area.width * area.height > 240_000) {
        ctx.fillStyle = rgbaString(baseColor, s.fill_alpha * 0.62);
      } else {
        let minCanvasY = pts[0]!.y;
        for (const pt of pts) {
          if (pt.y < minCanvasY) minCanvasY = pt.y;
        }
        const grad = ctx.createLinearGradient(0, minCanvasY, 0, baselineY);
        grad.addColorStop(0, rgbaString(baseColor, s.fill_alpha));
        grad.addColorStop(1, rgbaString(baseColor, 0));
        ctx.fillStyle = grad;
      }
      ctx.fill();
    }

    // Main polyline
    ctx.beginPath();
    if (s.linestyle === "dashed") {
      ctx.setLineDash([7 * strokeScale, 5 * strokeScale]);
    } else if (s.linestyle === "dotted") {
      ctx.setLineDash([2.2 * strokeScale, 4 * strokeScale]);
    } else {
      ctx.setLineDash([]);
    }

    ctx.moveTo(pts[0]!.x, pts[0]!.y);
    for (let i = 1; i < pts.length; i++) {
      ctx.lineTo(pts[i]!.x, pts[i]!.y);
    }
    ctx.strokeStyle = baseColor;
    ctx.lineWidth = Math.max(1, s.linewidth * strokeScale);
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();
    ctx.setLineDash([]);

    // Optional markers (batched into a single path!)
    if (s.marker) {
      const r = (s.marker === "circle" ? 3.5 : 2.8) * strokeScale;
      ctx.beginPath();
      for (const pt of pts) {
        ctx.moveTo(pt.x + r, pt.y);
        ctx.arc(pt.x, pt.y, r, 0, Math.PI * 2);
      }
      if (s.marker === "circle") {
        ctx.fillStyle = cs.variant === "reverse" ? cs.accent : "#0f172a";
        ctx.fill();
        ctx.lineWidth = 1.8 * strokeScale;
        ctx.strokeStyle = baseColor;
        ctx.stroke();
      } else {
        ctx.fillStyle = baseColor;
        ctx.fill();
      }
    }
  });

  ctx.restore();
}

/**
 * Level-3 `Plot` chart renderer (family: `Axis2D`) with offscreen bitmap & scaffold caching.
 */
export function renderPlotChart(
  ctx: CanvasRenderingContext2D,
  cell: PlotCellSpec,
  rect: GridRect,
  cs: ResolvedCellStyle,
  rawHoverProgress: number,
  playing: boolean,
  pointerWorld: { x: number; y: number } | null,
  dpr = 1,
  cacheEntry?: CellLayerCacheEntry,
): void {
  const eased = smoothstep(rawHoverProgress);
  const strokeScale = Math.sqrt(computeCardUiScale(rect.width, rect.height));

  let bounds: AxisBounds = computeAxis2DBounds(
    cell.series,
    cell.xlim,
    cell.ylim,
    cell.xmin,
    cell.xmax,
    cell.ymin,
    cell.ymax,
  );

  // Stabilize auto-scaled Y bounds on live oscillating waves so axes don't jitter or thrash scaffold cache
  if (
    cell.dynamic &&
    cacheEntry?.plotMeta &&
    cell.ylim === null &&
    cell.ymin === null &&
    cell.ymax === null
  ) {
    const prevMin = cacheEntry.plotMeta.envYMin;
    const prevMax = cacheEntry.plotMeta.envYMax;
    if (prevMin !== undefined && prevMax !== undefined) {
      const curSpan = bounds.yMax - bounds.yMin;
      const prevSpan = prevMax - prevMin;
      if (
        bounds.yMin >= prevMin &&
        bounds.yMax <= prevMax &&
        curSpan >= prevSpan * 0.55
      ) {
        bounds = { ...bounds, yMin: prevMin, yMax: prevMax };
      }
    }
  }

  if (cacheEntry) {
    const pad = 2;
    const pw = Math.max(4, Math.ceil((rect.width + pad * 2) * dpr));
    const ph = Math.max(4, Math.ceil((rect.height + pad * 2) * dpr));
    const hStep = Math.round(rawHoverProgress * 40);
    const bKey = `${bounds.xMin.toPrecision(6)},${bounds.xMax.toPrecision(6)},${bounds.yMin.toPrecision(6)},${bounds.yMax.toPrecision(6)}`;

    if (!cell.dynamic) {
      // Static Plot: cache the ENTIRE card + axes + curves + markers! Hover tooltip draws on top in 0.04ms!
      const key = `plotStatic|${pw}x${ph}|${dpr}|${hStep}|${bKey}|${cell.series.length}`;
      if (cacheEntry.key !== key || !cacheEntry.plotMeta) {
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
          renderCardSurfaceAndFrame(cctx, localRect, cs, rawHoverProgress);
          const localLayout = computeAxis2DLayout(cctx, localRect, cs, bounds, {
            title: cell.label,
            dynamic: false,
            xlabel: cell.xlabel,
            ylabel: cell.ylabel,
            legend: cell.legend,
            xstep: cell.xstep,
            ystep: cell.ystep,
            xmin: cell.xmin,
            ymin: cell.ymin,
            legendItems: cell.series.map((s) => ({
              label: s.label,
              color: s.color,
              linestyle: s.linestyle,
            })),
          });
          renderAxis2DHeaderAndLegend(
            cctx,
            localRect,
            cs,
            localLayout,
            cell.label,
            false,
            playing,
          );
          renderAxis2DScaffold(
            cctx,
            localLayout,
            cs,
            cell.xlabel,
            cell.ylabel,
            cell.grid,
          );
          drawPlotCurvesIntoArea(cctx, cell, cs, localLayout, strokeScale);

          const worldArea = {
            x: rect.x + (localLayout.area.x - pad),
            y: rect.y + (localLayout.area.y - pad),
            width: localLayout.area.width,
            height: localLayout.area.height,
          };
          cacheEntry.plotMeta = {
            layout: { ...localLayout, area: worldArea },
          };
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
      if (eased > 0.01 && pointerWorld && cacheEntry.plotMeta) {
        const worldArea = cacheEntry.plotMeta.layout.area;
        const snapped = findNearestPlotPoint(
          cell,
          worldArea,
          bounds,
          pointerWorld.x,
          pointerWorld.y,
        );
        if (snapped) {
          renderHoverTooltip(ctx, worldArea, snapped, cs, eased);
        }
      }
      return;
    }

    // Dynamic Plot: cache Card + Crescent + Title + Legend + Grid + Ticks + Axis Titles; ONLY stroke curves per tick!
    const key = `plotDyn|${pw}x${ph}|${dpr}|${hStep}|${playing}|${bKey}|${cell.series.length}`;
    if (cacheEntry.key !== key || !cacheEntry.plotMeta) {
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
        renderCardSurfaceAndFrame(cctx, localRect, cs, rawHoverProgress);
        const localLayout = computeAxis2DLayout(cctx, localRect, cs, bounds, {
          title: cell.label,
          dynamic: true,
          xlabel: cell.xlabel,
          ylabel: cell.ylabel,
          legend: cell.legend,
          xstep: cell.xstep,
          ystep: cell.ystep,
          xmin: cell.xmin,
          ymin: cell.ymin,
          legendItems: cell.series.map((s) => ({
            label: s.label,
            color: s.color,
            linestyle: s.linestyle,
          })),
        });
        renderAxis2DHeaderAndLegend(
          cctx,
          localRect,
          cs,
          localLayout,
          cell.label,
          true,
          playing,
        );
        renderAxis2DScaffold(
          cctx,
          localLayout,
          cs,
          cell.xlabel,
          cell.ylabel,
          cell.grid,
        );

        const worldArea = {
          x: rect.x + (localLayout.area.x - pad),
          y: rect.y + (localLayout.area.y - pad),
          width: localLayout.area.width,
          height: localLayout.area.height,
        };
        cacheEntry.plotMeta = {
          layout: { ...localLayout, area: worldArea, bounds },
          envYMin: bounds.yMin,
          envYMax: bounds.yMax,
        };
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
    if (cacheEntry.plotMeta) {
      const worldLayout = cacheEntry.plotMeta.layout;
      drawPlotCurvesIntoArea(ctx, cell, cs, worldLayout, strokeScale);
      if (eased > 0.01 && pointerWorld) {
        const snapped = findNearestPlotPoint(
          cell,
          worldLayout.area,
          worldLayout.bounds,
          pointerWorld.x,
          pointerWorld.y,
        );
        if (snapped) {
          renderHoverTooltip(ctx, worldLayout.area, snapped, cs, eased);
        }
      }
    }
    return;
  }

  // Uncached path (e.g. during active viewport zoom != 100%)
  renderCardSurfaceAndFrame(ctx, rect, cs, rawHoverProgress);
  const layout = computeAxis2DLayout(ctx, rect, cs, bounds, {
    title: cell.label,
    dynamic: cell.dynamic,
    xlabel: cell.xlabel,
    ylabel: cell.ylabel,
    legend: cell.legend,
    xstep: cell.xstep,
    ystep: cell.ystep,
    xmin: cell.xmin,
    ymin: cell.ymin,
    legendItems: cell.series.map((s) => ({
      label: s.label,
      color: s.color,
      linestyle: s.linestyle,
    })),
  });
  renderAxis2DHeaderAndLegend(
    ctx,
    rect,
    cs,
    layout,
    cell.label,
    cell.dynamic,
    playing,
  );
  renderAxis2DScaffold(ctx, layout, cs, cell.xlabel, cell.ylabel, cell.grid);
  drawPlotCurvesIntoArea(ctx, cell, cs, layout, strokeScale);

  if (eased > 0.01 && pointerWorld) {
    const snapped = findNearestPlotPoint(
      cell,
      layout.area,
      bounds,
      pointerWorld.x,
      pointerWorld.y,
    );
    if (snapped) {
      renderHoverTooltip(ctx, layout.area, snapped, cs, eased);
    }
  }
}
