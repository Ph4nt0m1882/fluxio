import { describe, expect, it } from "vitest";
import {
  resolveTheme,
  resolveCellStyle,
  lerpRgba,
  stepHoverMap,
  smoothstep,
} from "../src/themes";
import {
  computeGridRects,
  createInitialViewport,
  panViewport,
  screenToWorld,
  worldToScreen,
  zoomViewportAt,
  hitTestCell,
} from "../src/layout";
import { parseFigureSpec, applyTickMessage, formatNumberValue } from "../src/protocol";
import {
  buildTaperedAccentSvgPath,
  computeFigureUiScale,
  TOOLBAR_ICONS,
} from "../src/renderer";
import { computeCardUiScale } from "../src/charts/base";
import { renderBlockDigits } from "../src/text_digits";
import {
  computeAxis2DBounds,
  computeAxisTicks,
  computeNiceTicks,
  findNearestPlotPoint,
} from "../src/charts/axis2d";

describe("Fluxio TypeScript Viewer Core, Variants & Customization", () => {
  it("resolves built-in themes and adaptive translucent card veil", () => {
    const dark = resolveTheme({ name: "dark" });
    expect(dark.background).toBe("#0b1120");
    expect(dark.surface.toLowerCase()).toBe("#ffffff");
    expect(dark.variant).toBe("classic");

    const ppt = resolveTheme({
      name: "presentation",
      accent: "#e11d48",
      transparent: true,
    });
    expect(ppt.name).toBe("presentation");
    expect(ppt.surface.toLowerCase()).toBe("#0f172a");
    expect(ppt.accent).toBe("#e11d48");
    expect(ppt.transparent).toBe(true);
  });

  it("supports classic, reverse, and text variants in global and per-cell cascade", () => {
    const theme = resolveTheme({
      name: "dark",
      accent: "#2563eb",
      accent_side: "left",
      radius: 16,
    });

    const revCell = resolveCellStyle(theme, {
      variant: "reverse",
      accent: "#dc2626",
    });
    expect(revCell.variant).toBe("reverse");
    expect(revCell.accent).toBe("#dc2626");
    // Reverse defaults to ~0.90 text_opacity when not explicitly specified
    expect(revCell.text_opacity).toBeCloseTo(0.9, 2);

    const brightRev = resolveCellStyle(theme, {
      variant: "reverse",
      accent: "#fde047", // Bright yellow -> dark contrast ink!
      text_opacity: 0.85,
    });
    expect(brightRev.reverse_ink).toBe("#090d16");
    expect(brightRev.text_opacity).toBeCloseTo(0.85, 3);

    const textTheme = resolveTheme({ variant: "text" });
    expect(textTheme.variant).toBe("text");
  });

  it("renders 3-row btop-style Unicode block digits cleanly", () => {
    const lines = renderBlockDigits("42.5");
    expect(lines).not.toBeNull();
    expect(lines).toHaveLength(3);
    expect(lines![0]!.length).toBe(lines![1]!.length);
    expect(lines![1]!.length).toBe(lines![2]!.length);
    expect(lines!.join("")).toMatch(/[█▀▄]/);
  });

  it("interpolates hover border progressively without popping", () => {
    const progress = new Map<string, number>();
    const active1 = stepHoverMap(progress, ["c0", "c1"], "c0", 0.05, 200);
    expect(active1).toBe(true);
    const pMid = progress.get("c0") ?? 0;
    expect(pMid).toBeGreaterThan(0.15);
    expect(pMid).toBeLessThan(0.45);
    expect(smoothstep(pMid)).toBeGreaterThan(0.05);
    expect(lerpRgba("#ffffff", 0.16, "#38bdf8", 1.0, 0.5)).toContain("0.58");

    stepHoverMap(progress, ["c0", "c1"], "c0", 0.25, 200);
    expect(stepHoverMap(progress, ["c0", "c1"], "c0", 0.016, 200)).toBe(false);
  });

  it("builds CSS-like tapered crescent paths and clean Material SVG toolbar icons", () => {
    const rect = { id: "c0", x: 10, y: 20, width: 200, height: 120 };
    for (const side of ["left", "right", "top", "bottom"] as const) {
      const d = buildTaperedAccentSvgPath(rect, 20, side, 6);
      expect(d.match(/Z/g)?.length).toBe(2);
    }
    expect(buildTaperedAccentSvgPath(rect, 20, "none", 6)).toBe("");
    for (const svg of Object.values(TOOLBAR_ICONS)) {
      expect(svg).toContain("<svg");
    }
  });

  it("computes grid cell rectangles, viewport transforms, and parses FigureSpec", () => {
    const rects = computeGridRects({
      width: 1000,
      height: 600,
      rows: 2,
      cols: 2,
      padding: 20,
      gap: 10,
      headerHeight: 50,
      cells: [
        { id: "c0", row: 0, col: 0, row_span: 1, col_span: 2 },
        { id: "c1", row: 1, col: 0, row_span: 1, col_span: 1 },
        { id: "c2", row: 1, col: 1, row_span: 1, col_span: 1 },
      ],
    });
    expect(rects[0]!.width).toBeCloseTo(960, 3);

    let vp = createInitialViewport();
    vp = zoomViewportAt(vp, 2.0, 400, 300);
    vp = panViewport(vp, 50, -30);
    const screenPt = worldToScreen(vp, 100, 200);
    expect(screenToWorld(vp, screenPt.x, screenPt.y).x).toBeCloseTo(100, 5);
    expect(hitTestCell(rects, vp, worldToScreen(vp, 120, 90).x, worldToScreen(vp, 120, 90).y)).toBe("c0");

    const spec = parseFigureSpec({
      version: "0.1",
      id: "fig_1",
      title: "Corporate",
      rows: 1,
      cols: 1,
      size: [800, 450],
      fps: 20,
      dynamic: true,
      theme: { name: "dark", variant: "reverse" },
      cells: [
        {
          id: "c_0_0",
          row: 0,
          col: 0,
          row_span: 1,
          col_span: 1,
          kind: "number",
          label: "KPI",
          value: 42,
          formatted: "42.0",
          unit: "%",
          precision: 1,
          prefix: "",
          style: { accent_side: "left", accent: "#f59e0b" },
          dynamic: true,
        },
      ],
    });
    expect(spec.theme.variant).toBe("reverse");
    applyTickMessage(spec, {
      type: "tick",
      t: 0.5,
      updates: [{ id: "c_0_0", value: 77.25, formatted: "77.2" }],
    });
    expect(spec.cells[0]?.kind === "number" && spec.cells[0].value).toBe(77.25);
    expect(formatNumberValue(12.3456, 2, "$")).toBe("$12.35");
  });

  it("computes nice Axis2D ticks, parses Plot specs, and snaps hover tooltips", () => {
    const ticks = computeNiceTicks(2, 98, 5);
    expect(ticks.length).toBeGreaterThanOrEqual(3);
    expect(ticks[0]!).toBeLessThanOrEqual(2);
    expect(ticks[ticks.length - 1]!).toBeGreaterThanOrEqual(98);

    const plotSpec = parseFigureSpec({
      version: "0.1",
      id: "fig_plot",
      title: "Plot Test",
      rows: 1,
      cols: 1,
      size: [800, 450],
      fps: 24,
      dynamic: true,
      theme: { name: "dark" },
      cells: [
        {
          id: "p_0_0",
          row: 0,
          col: 0,
          row_span: 1,
          col_span: 1,
          kind: "plot",
          label: "Courbe",
          xlabel: "Temps",
          ylabel: "Valeur",
          grid: true,
          legend: true,
          dynamic: true,
          series: [
            {
              label: "S1",
              x: [0, 1, 2],
              y: [10, 20, 15],
              color: "#38bdf8",
              linewidth: 2.4,
              linestyle: "solid",
              marker: "circle",
              fill_alpha: 0.12,
            },
          ],
        },
      ],
    });

    const pCell = plotSpec.cells[0]!;
    expect(pCell.kind).toBe("plot");

    applyTickMessage(plotSpec, {
      type: "tick",
      t: 1.0,
      updates: [
        {
          id: "p_0_0",
          series_data: [{ x: [1, 2, 3], y: [20, 15, 35] }],
        },
      ],
    });
    if (pCell.kind === "plot") {
      expect(pCell.series[0]?.y).toEqual([20, 15, 35]);
      const nearest = findNearestPlotPoint(
        pCell,
        { x: 50, y: 50, width: 400, height: 200 },
        { xMin: 1, xMax: 3, yMin: 10, yMax: 40 },
        250, // midpoint X -> x = 2 -> y = 15
        160,
      );
      expect(nearest).not.toBeNull();
      expect(nearest!.dataX).toBe(2);
      expect(nearest!.dataY).toBe(15);
    }

    // Explicit xmin/xmax + xstep=2 & partial ymin=0
    const steppedBounds = computeAxis2DBounds(
      [{ x: [0, 5, 10], y: [15, 65, 40] }],
      null,
      null,
      0,
      10,
      0,
      null,
    );
    expect(steppedBounds.xMin).toBe(0);
    expect(steppedBounds.xMax).toBe(10);
    expect(steppedBounds.yMin).toBe(0);
    expect(steppedBounds.yMax).toBeGreaterThan(65);
    expect(computeAxisTicks(0, 10, 5, 2, 0)).toEqual([0, 2, 4, 6, 8, 10]);

    // Responsive typography scale stays 1.0 on normal windows and scales smoothly on QHD/4K
    expect(computeFigureUiScale(900, 520)).toBe(1.0);
    expect(computeFigureUiScale(2560, 1440)).toBeGreaterThan(1.7);
    expect(computeCardUiScale(420, 260)).toBe(1.0);
    expect(computeCardUiScale(1800, 900)).toBeGreaterThan(1.7);
  });
});
