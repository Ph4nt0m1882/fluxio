import type { GridRect } from "../layout";
import {
  lerpRgba,
  MONOSPACE_STACK,
  rgbaString,
  smoothstep,
  type AccentSide,
  type ResolvedCellStyle,
} from "../themes";

export function addRoundedRectSubpath(
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

export function roundedRectSvgSubpath(
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

export function computeCrescentInnerRect(
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

export function fillInsetRoundedRing(
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

export function fillTaperedAccentCrescent(
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

/**
 * Shared Level-1 Card Chrome renderer (`classic`, `reverse`, `text` surface + border + crescent + header/live badge).
 * Reusable across all chart families (`Indicator`, `Axis2D`, `Field2D`, `Polar2D`, `Space3D`, `Scene`).
 */
export function renderCardSurfaceAndFrame(
  ctx: CanvasRenderingContext2D,
  rect: GridRect,
  cs: ResolvedCellStyle,
  rawHoverProgress: number,
): { eased: number; effectiveRadius: number } {
  const eased = smoothstep(rawHoverProgress);

  if (cs.variant === "text") {
    const radius = Math.min(10, cs.radius);
    ctx.beginPath();
    addRoundedRectSubpath(ctx, rect.x, rect.y, rect.width, rect.height, radius);
    ctx.fillStyle = rgbaString("#090d16", 0.72 + 0.08 * eased);
    ctx.fill();

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
    return { eased, effectiveRadius: radius };
  }

  const isReverse = cs.variant === "reverse";
  if (isReverse) {
    const revAlpha = Math.min(1, Math.max(0, cs.surface_opacity));
    ctx.beginPath();
    addRoundedRectSubpath(ctx, rect.x, rect.y, rect.width, rect.height, cs.radius);
    ctx.fillStyle = rgbaString(cs.accent, revAlpha);
    ctx.fill();
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

  return { eased, effectiveRadius: cs.radius };
}

export function computeCardUiScale(width: number, height: number): number {
  const r = Math.min(width / 620, height / 360);
  return r > 1.05 ? Math.min(2.2, 1 + (r - 1) * 0.52) : 1.0;
}

export function renderTuiHeaderAndBadge(
  ctx: CanvasRenderingContext2D,
  rect: GridRect,
  cs: ResolvedCellStyle,
  label: string,
  dynamic: boolean,
  playing: boolean,
  padX = 18,
  padY = 14,
): void {
  const uiScale = computeCardUiScale(rect.width, rect.height);
  if (label) {
    const lblPx = Math.round(13 * cs.font_scale * uiScale);
    ctx.font = `700 ${lblPx}px ${MONOSPACE_STACK}`;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";
    ctx.fillStyle = cs.accent;
    ctx.fillText("┤ ", rect.x + padX, rect.y + padY);
    const wLeft = ctx.measureText("┤ ").width;
    ctx.fillStyle = cs.text;
    ctx.fillText(label, rect.x + padX + wLeft, rect.y + padY);
    const wLbl = ctx.measureText(label).width;
    ctx.fillStyle = cs.accent;
    ctx.fillText(" ├", rect.x + padX + wLeft + wLbl, rect.y + padY);
  }

  if (dynamic) {
    const statusTxt = playing ? "● LIVE" : "⏸ PAUSE";
    const livePx = Math.round(11 * uiScale);
    ctx.font = `700 ${livePx}px ${MONOSPACE_STACK}`;
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillStyle = playing ? "#22c55e" : "#eab308";
    ctx.fillText(statusTxt, rect.x + rect.width - padX, rect.y + padY + 1);
  }
}
