import type { GridRect } from "../layout";
import type { NumberCellSpec } from "../protocol";
import { buildBlockMatrix, splitBlockRenderable } from "../text_digits";
import { MONOSPACE_STACK, rgbaString, type ResolvedCellStyle } from "../themes";
import {
  computeCardUiScale,
  renderCardSurfaceAndFrame,
  renderTuiHeaderAndBadge,
} from "./base";

/**
 * Level-3 `Number` chart renderer (family: `Indicator`).
 */
export function renderNumberChart(
  ctx: CanvasRenderingContext2D,
  cell: NumberCellSpec,
  rect: GridRect,
  cs: ResolvedCellStyle,
  rawHoverProgress: number,
  playing: boolean,
): void {
  renderCardSurfaceAndFrame(ctx, rect, cs, rawHoverProgress);

  if (cs.variant === "text") {
    renderNumberTextContent(ctx, cell, rect, cs, playing);
  } else {
    renderNumberModernContent(ctx, cell, rect, cs, playing);
  }
}

function renderNumberModernContent(
  ctx: CanvasRenderingContext2D,
  cell: NumberCellSpec,
  rect: GridRect,
  cs: ResolvedCellStyle,
  playing: boolean,
): void {
  const isReverse = cs.variant === "reverse";
  const padX = Math.min(64, Math.max(16, rect.width * 0.045));
  const padY = Math.min(48, Math.max(12, rect.height * 0.075));

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
      Math.max(11, Math.min(rect.height * 0.075, rect.width * 0.042, 40)) *
        cs.font_scale,
    );
    ctx.fillStyle = labelFill;
    ctx.font = `600 ${labelFontPx}px ${cs.font}`;
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(
      cell.label,
      rect.x + padX,
      rect.y + padY + 2,
      Math.max(40, rect.width - padX * 2 - (cell.dynamic ? 28 : 0)),
    );
  }

  if (cell.dynamic) {
    const dotR = Math.max(4.5, Math.min(9, rect.height * 0.016));
    const dotX = rect.x + rect.width - padX - dotR;
    const dotY = rect.y + padY + dotR + 4;
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
    Math.min(rect.height * 0.40, rect.width * 0.26, 280) * cs.font_scale,
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
    const descPx = Math.max(
      10,
      Math.round(
        Math.max(12, Math.min(rect.height * 0.046, rect.width * 0.026, 26)) *
          cs.font_scale,
      ),
    );
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
}

function renderNumberTextContent(
  ctx: CanvasRenderingContext2D,
  cell: NumberCellSpec,
  rect: GridRect,
  cs: ResolvedCellStyle,
  playing: boolean,
): void {
  const uiScale = computeCardUiScale(rect.width, rect.height);
  const padX = Math.round(18 * uiScale);
  const padY = Math.round(14 * uiScale);
  renderTuiHeaderAndBadge(
    ctx,
    rect,
    cs,
    cell.label,
    cell.dynamic,
    playing,
    padX,
    padY,
  );

  const { prefix, core } = splitBlockRenderable(cell.formatted);
  const matrix = buildBlockMatrix(core);
  const maxAvailW = Math.max(40, rect.width - padX * 2);
  const centerY = rect.y + rect.height * (cell.label ? 0.56 : 0.5);

  if (matrix && matrix[0]!.length > 0 && rect.height >= 115) {
    const cols = matrix[0]!.length;
    const unitStr = cell.unit ? ` ${cell.unit}` : "";
    const unitPx = Math.round(
      Math.min(64, Math.max(13, rect.height * 0.11)) * cs.font_scale,
    );
    ctx.font = `700 ${unitPx}px ${MONOSPACE_STACK}`;
    const prefixW = prefix ? ctx.measureText(`${prefix} `).width : 0;
    const unitW = unitStr ? ctx.measureText(unitStr).width + 6 * uiScale : 0;

    const maxBlockAreaW = Math.max(24, maxAvailW - prefixW - unitW);
    const cellSize = Math.floor(
      Math.min(
        (rect.height * 0.40 * cs.font_scale) / 6,
        maxBlockAreaW / cols,
        48,
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
    ctx.font = `400 ${Math.round(11.5 * cs.font_scale)}px ${MONOSPACE_STACK}`;
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
}

function drawMonospaceFallbackValue(
  ctx: CanvasRenderingContext2D,
  cell: NumberCellSpec,
  rect: GridRect,
  cs: ResolvedCellStyle,
  centerY: number,
  maxAvailW: number,
): void {
  const valPx = Math.max(
    16,
    Math.round(Math.min(rect.height * 0.32, 48) * cs.font_scale),
  );
  ctx.font = `700 ${valPx}px ${MONOSPACE_STACK}`;
  ctx.fillStyle = rgbaString(cs.text, cs.text_opacity);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const full = cell.unit ? `${cell.formatted} ${cell.unit}` : cell.formatted;
  ctx.fillText(full, rect.x + rect.width / 2, centerY, maxAvailW);
}
