# Styling & Themes

Fluxio uses a CSS-like **style cascade**:

1. **Preset Theme** (`theme="dark" | "light" | "presentation"`)
2. **Global Figure Style** (`fig.style(...)` — chainable, sets figure background & default card aesthetics)
3. **Per-Cell Style** (`fig[row, col].style(...)` or `cell.style(...)` — overrides only that specific cell)

## Style Variants (`variant`)

Every figure or individual cell supports three visual variants via `.style(variant=...)`:

| Variant | Description |
| :--- | :--- |
| `"classic"` *(default)* | Adaptive translucent glass veil (~10% light veil on dark backgrounds, ~8% dark veil on light backgrounds) with a tapered rounded crescent on `accent_side`. |
| `"reverse"` | Solid `accent` background fill with auto-contrasted ink (`#ffffff` or `#090d16`) at `text_opacity` (default `0.90` for value, `~0.68` for label/unit). Ideal to highlight a critical KPI card. |
| `"text"` | Modern TUI / console aesthetic (`btop`-style `┤ Label ├` frame, monospace font, and segmented 6-row block-matrix digits) across windows, Jupyter, and PNG/SVG exports. |

## Custom Backgrounds (`background`)

`fig.style(background=...)` accepts:

- **Hex color string**: `"#0b1120"` or `"transparent"` (or `fig.style(transparent=True)` for alpha-transparent PowerPoint exports).
- **Linear or Radial Gradient**:
  ```python
  fig.style(
      background=fx.Gradient(["#090d16", "#1e1b4b", "#0f172a"], angle=135, kind="linear")
  )
  ```
- **Self-contained Image** (auto-encoded to Base64 for offline `.html` & Jupyter):
  ```python
  fig.style(
      background=fx.BackgroundImage("corporate_slide.png", fit="cover", opacity=1.0)
  )
  ```

Fluxio automatically measures the perceived WCAG luminance of solid colors, gradients, and images to pick a harmonious light or dark translucent veil and readable text colors unless explicitly overridden.

## Tapered Crescent Borders & Smooth Hover

- `accent_side`: `"left"` | `"right"` | `"top"` | `"bottom"` | `"none"` (default `"top"`). Renders a CSS-like tapered rounded crescent (`accent_width`, default `7.0`) that merges seamlessly into the thin card border (`border_width`, `border_opacity`).
- `hover_ms`: Smooth `smoothstep` transition duration in milliseconds (default `200` ms) when hovering cards in interactive views — eliminating abrupt visual popping while dropping back to 0% CPU once settled.
