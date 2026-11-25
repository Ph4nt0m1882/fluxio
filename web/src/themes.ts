export type AccentSide = "left" | "right" | "top" | "bottom" | "none";
export type StyleVariant = "classic" | "reverse" | "text";

export type BackgroundSpec =
  | { type: "solid"; color: string }
  | { type: "transparent" }
  | {
      type: "gradient";
      kind: "linear" | "radial";
      angle: number;
      stops: string[];
    }
  | {
      type: "image";
      data_url: string;
      fit: "cover" | "contain" | "stretch";
      opacity: number;
      overlay: string | null;
      overlay_opacity: number;
      luminance?: number;
    };

export interface CellStyleOverride {
  variant?: StyleVariant;
  surface?: string;
  surface_opacity?: number;
  border?: string;
  border_opacity?: number;
  border_width?: number;
  hover_border_width?: number;
  radius?: number;
  accent?: string;
  accent_side?: AccentSide;
  accent_width?: number;
  text?: string;
  text_opacity?: number;
  muted?: string;
  unit_color?: string;
  font?: string;
  font_scale?: number;
}

export interface ResolvedCellStyle {
  variant: StyleVariant;
  surface: string;
  surface_opacity: number;
  border: string;
  border_opacity: number;
  border_width: number;
  hover_border_width: number;
  radius: number;
  accent: string;
  accent_side: AccentSide;
  accent_width: number;
  text: string;
  text_opacity: number;
  muted: string;
  muted_opacity: number;
  unit_color: string;
  reverse_ink: string;
  font: string;
  font_scale: number;
}

export interface ThemeSpec extends ResolvedCellStyle {
  name: string;
  background: string;
  background_spec: BackgroundSpec;
  title_color: string;
  subtitle_color: string;
  padding: number;
  gap: number;
  transparent: boolean;
  hover_ms: number;
}

export const MONOSPACE_STACK =
  "'Noto Sans Mono', 'DejaVu Sans Mono', 'JetBrains Mono', 'Fira Code', ui-monospace, monospace";

export function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.trim().replace(/^#/, "");
  if (clean.length === 3) {
    const r = parseInt(clean[0]! + clean[0]!, 16);
    const g = parseInt(clean[1]! + clean[1]!, 16);
    const b = parseInt(clean[2]! + clean[2]!, 16);
    return [r || 0, g || 0, b || 0];
  }
  if (clean.length >= 6) {
    const r = parseInt(clean.slice(0, 2), 16);
    const g = parseInt(clean.slice(2, 4), 16);
    const b = parseInt(clean.slice(4, 6), 16);
    return [r || 0, g || 0, b || 0];
  }
  return [15, 23, 42];
}

export function hexLuminance(hex: string): number {
  const [r8, g8, b8] = hexToRgb(hex);
  const toLinear = (v: number): number => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * toLinear(r8) + 0.7152 * toLinear(g8) + 0.0722 * toLinear(b8);
}

export function contrastInkForAccent(accentHex: string): string {
  return hexLuminance(accentHex) < 0.48 ? "#ffffff" : "#090d16";
}

export function computeBackgroundLuminance(
  bgSpec: BackgroundSpec | undefined,
  fallbackHex: string,
): number {
  if (!bgSpec) return hexLuminance(fallbackHex);
  if (bgSpec.type === "solid") return hexLuminance(bgSpec.color);
  if (bgSpec.type === "gradient" && bgSpec.stops.length > 0) {
    const sum = bgSpec.stops.reduce((acc, c) => acc + hexLuminance(c), 0);
    return sum / bgSpec.stops.length;
  }
  if (bgSpec.type === "image") {
    const baseLum = typeof bgSpec.luminance === "number" ? bgSpec.luminance : 0.5;
    if (bgSpec.overlay && bgSpec.overlay_opacity > 0) {
      const ovLum = hexLuminance(bgSpec.overlay);
      const a = Math.max(0, Math.min(1, bgSpec.overlay_opacity));
      return baseLum * (1 - a) + ovLum * a;
    }
    return baseLum;
  }
  return hexLuminance(fallbackHex);
}

export function rgbaString(hex: string, alpha: number): string {
  const [r, g, b] = hexToRgb(hex);
  const a = Number(Math.max(0, Math.min(1, alpha)).toFixed(3));
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export function lerpRgba(
  hexA: string,
  alphaA: number,
  hexB: string,
  alphaB: number,
  t: number,
): string {
  const p = Math.max(0, Math.min(1, t));
  const [r1, g1, b1] = hexToRgb(hexA);
  const [r2, g2, b2] = hexToRgb(hexB);
  const r = Math.round(r1 + (r2 - r1) * p);
  const g = Math.round(g1 + (g2 - g1) * p);
  const b = Math.round(b1 + (b2 - b1) * p);
  const a = Number((alphaA + (alphaB - alphaA) * p).toFixed(3));
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export function smoothstep(t: number): number {
  const x = Math.max(0, Math.min(1, t));
  return x * x * (3 - 2 * x);
}

export function stepHoverMap(
  map: Map<string, number>,
  cellIds: string[],
  hoveredId: string | null,
  dtSec: number,
  durationMs: number,
): boolean {
  let active = false;
  const durSec = Math.max(0, durationMs) / 1000;
  for (const id of cellIds) {
    const current = map.get(id) ?? 0;
    const target = id === hoveredId ? 1 : 0;
    if (durSec <= 0) {
      map.set(id, target);
      continue;
    }
    const maxDelta = dtSec / durSec;
    const diff = target - current;
    if (Math.abs(diff) <= maxDelta || Math.abs(diff) < 1e-4) {
      map.set(id, target);
    } else {
      map.set(id, current + Math.sign(diff) * maxDelta);
      active = true;
    }
  }
  return active;
}

const PRESET_BASES: Record<
  string,
  { background: string; accent: string; radius: number; padding: number; gap: number }
> = {
  dark: {
    background: "#0b1120",
    accent: "#38bdf8",
    radius: 14,
    padding: 24,
    gap: 16,
  },
  light: {
    background: "#f8fafc",
    accent: "#2563eb",
    radius: 14,
    padding: 24,
    gap: 16,
  },
  presentation: {
    background: "#ffffff",
    accent: "#1d4ed8",
    radius: 12,
    padding: 28,
    gap: 20,
  },
};

export function resolveTheme(
  partial?: Partial<ThemeSpec> & { name?: string },
): ThemeSpec {
  const baseName =
    partial?.name && PRESET_BASES[partial.name] ? partial.name : "dark";
  const preset = PRESET_BASES[baseName]!;
  const variant: StyleVariant = (partial?.variant as StyleVariant) ?? "classic";

  const transparent = Boolean(
    partial?.transparent ||
      partial?.background === "transparent" ||
      partial?.background_spec?.type === "transparent",
  );
  const defaultBg = variant === "text" ? "#0a0e14" : preset.background;
  const bgHex =
    typeof partial?.background === "string" && partial.background !== "transparent"
      ? partial.background
      : defaultBg;

  const bgSpec: BackgroundSpec = partial?.background_spec
    ? partial.background_spec
    : transparent
      ? { type: "transparent" }
      : { type: "solid", color: bgHex };

  const lum = computeBackgroundLuminance(bgSpec, defaultBg);
  const isDarkBg = lum < 0.5;

  const autoSurface = isDarkBg ? "#ffffff" : "#0f172a";
  const autoSurfaceOpacity = variant === "reverse" ? 1.0 : isDarkBg ? 0.10 : 0.08;
  const autoText = isDarkBg ? "#f8fafc" : "#0f172a";
  const autoMuted = isDarkBg ? "#cbd5e1" : "#475569";

  const accent = partial?.accent ?? preset.accent;
  const revInk = contrastInkForAccent(accent);
  const text = partial?.text ?? autoText;
  const muted = partial?.muted ?? autoMuted;
  const defaultTextOpacity = variant === "reverse" ? 0.90 : 1.0;
  const textOpacity = Number(partial?.text_opacity ?? defaultTextOpacity);
  const mutedOpacity =
    variant === "reverse" ? Number((textOpacity * 0.75).toFixed(3)) : 1.0;

  const defaultFont =
    variant === "text"
      ? MONOSPACE_STACK
      : "Inter, 'Noto Sans', system-ui, -apple-system, sans-serif";

  return {
    name: partial?.name ?? baseName,
    variant,
    background: bgHex,
    background_spec: bgSpec,
    transparent,
    padding: Number(partial?.padding ?? preset.padding),
    gap: Number(partial?.gap ?? preset.gap),
    hover_ms: Number(partial?.hover_ms ?? 200),
    title_color: partial?.title_color ?? text,
    subtitle_color: partial?.subtitle_color ?? muted,
    surface: partial?.surface ?? autoSurface,
    surface_opacity: Number(partial?.surface_opacity ?? autoSurfaceOpacity),
    border: partial?.border ?? accent,
    border_opacity: Number(partial?.border_opacity ?? 0.45),
    border_width: Number(partial?.border_width ?? 1.6),
    hover_border_width: Number(partial?.hover_border_width ?? 2.6),
    radius: Number(partial?.radius ?? (variant === "text" ? 8 : preset.radius)),
    accent,
    accent_side: (partial?.accent_side as AccentSide) ?? "top",
    accent_width: Number(partial?.accent_width ?? 7.0),
    text,
    text_opacity: textOpacity,
    muted,
    muted_opacity: mutedOpacity,
    unit_color: partial?.unit_color ?? accent,
    reverse_ink: revInk,
    font: partial?.font ?? defaultFont,
    font_scale: Number(partial?.font_scale ?? 1.0),
  };
}

export function resolveCellStyle(
  theme: ThemeSpec,
  override?: CellStyleOverride | null,
  legacyColor?: string | null,
): ResolvedCellStyle {
  const variant: StyleVariant = override?.variant ?? theme.variant;
  const accent = override?.accent ?? legacyColor ?? theme.accent;
  const revInk = contrastInkForAccent(accent);
  const text = override?.text ?? legacyColor ?? theme.text;
  const border =
    override?.border ??
    (override?.accent || legacyColor ? accent : theme.border);

  const surfaceOpacity =
    override?.surface_opacity !== undefined
      ? Number(override.surface_opacity)
      : variant === "reverse" && theme.variant !== "reverse"
        ? 1.0
        : theme.surface_opacity;

  const textOpacity =
    override?.text_opacity !== undefined
      ? Number(override.text_opacity)
      : variant === "reverse" && theme.variant !== "reverse"
        ? 0.90
        : theme.text_opacity;

  const mutedOpacity =
    variant === "reverse" ? Number((textOpacity * 0.75).toFixed(3)) : 1.0;

  const font =
    override?.font ??
    (variant === "text" && theme.variant !== "text"
      ? MONOSPACE_STACK
      : theme.font);

  return {
    variant,
    surface: override?.surface ?? theme.surface,
    surface_opacity: surfaceOpacity,
    border,
    border_opacity:
      override?.border_opacity !== undefined
        ? Number(override.border_opacity)
        : theme.border_opacity,
    border_width:
      override?.border_width !== undefined
        ? Number(override.border_width)
        : theme.border_width,
    hover_border_width:
      override?.hover_border_width !== undefined
        ? Number(override.hover_border_width)
        : theme.hover_border_width,
    radius:
      override?.radius !== undefined
        ? Number(override.radius)
        : variant === "text" && theme.variant !== "text"
          ? 8
          : theme.radius,
    accent,
    accent_side: override?.accent_side ?? theme.accent_side,
    accent_width:
      override?.accent_width !== undefined
        ? Number(override.accent_width)
        : theme.accent_width,
    text,
    text_opacity: textOpacity,
    muted: override?.muted ?? theme.muted,
    muted_opacity: mutedOpacity,
    unit_color: override?.unit_color ?? accent,
    reverse_ink: revInk,
    font,
    font_scale:
      override?.font_scale !== undefined
        ? Number(override.font_scale)
        : theme.font_scale,
  };
}
