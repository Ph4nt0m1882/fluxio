export interface GridCellInput {
  id: string;
  row: number;
  col: number;
  row_span: number;
  col_span: number;
}

export interface GridRect {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface GridLayoutParams {
  width: number;
  height: number;
  rows: number;
  cols: number;
  padding: number;
  gap: number;
  headerHeight: number;
  cells: GridCellInput[];
}

export interface Viewport {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export const MIN_SCALE = 0.25;
export const MAX_SCALE = 8.0;

export function createInitialViewport(): Viewport {
  return { scale: 1.0, offsetX: 0, offsetY: 0 };
}

export function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}

export function zoomViewportAt(
  vp: Viewport,
  factor: number,
  anchorScreenX: number,
  anchorScreenY: number,
): Viewport {
  const nextScale = clampScale(vp.scale * factor);
  const world = screenToWorld(vp, anchorScreenX, anchorScreenY);
  return {
    scale: nextScale,
    offsetX: anchorScreenX - world.x * nextScale,
    offsetY: anchorScreenY - world.y * nextScale,
  };
}

export function panViewport(vp: Viewport, dx: number, dy: number): Viewport {
  return {
    scale: vp.scale,
    offsetX: vp.offsetX + dx,
    offsetY: vp.offsetY + dy,
  };
}

export function worldToScreen(
  vp: Viewport,
  wx: number,
  wy: number,
): { x: number; y: number } {
  return {
    x: wx * vp.scale + vp.offsetX,
    y: wy * vp.scale + vp.offsetY,
  };
}

export function screenToWorld(
  vp: Viewport,
  sx: number,
  sy: number,
): { x: number; y: number } {
  return {
    x: (sx - vp.offsetX) / vp.scale,
    y: (sy - vp.offsetY) / vp.scale,
  };
}

export function computeGridRects(params: GridLayoutParams): GridRect[] {
  const { width, height, rows, cols, padding, gap, headerHeight, cells } = params;
  const innerX = padding;
  const innerY = padding + headerHeight;
  const innerW = Math.max(40, width - padding * 2);
  const innerH = Math.max(40, height - padding * 2 - headerHeight);

  const unitW = (innerW - gap * Math.max(0, cols - 1)) / Math.max(1, cols);
  const unitH = (innerH - gap * Math.max(0, rows - 1)) / Math.max(1, rows);

  return cells.map((cell) => {
    const cSpan = Math.max(1, Math.min(cell.col_span, cols - cell.col));
    const rSpan = Math.max(1, Math.min(cell.row_span, rows - cell.row));
    const x = innerX + cell.col * (unitW + gap);
    const y = innerY + cell.row * (unitH + gap);
    const w = unitW * cSpan + gap * (cSpan - 1);
    const h = unitH * rSpan + gap * (rSpan - 1);
    return {
      id: cell.id,
      x,
      y,
      width: Math.max(10, w),
      height: Math.max(10, h),
    };
  });
}

export function hitTestCell(
  rects: GridRect[],
  vp: Viewport,
  screenX: number,
  screenY: number,
): string | null {
  const world = screenToWorld(vp, screenX, screenY);
  for (let i = rects.length - 1; i >= 0; i--) {
    const r = rects[i]!;
    if (
      world.x >= r.x &&
      world.x <= r.x + r.width &&
      world.y >= r.y &&
      world.y <= r.y + r.height
    ) {
      return r.id;
    }
  }
  return null;
}
