"""Standalone HTML and Jupyter inline HTML bundle generation."""

from __future__ import annotations
import html
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_BUNDLE_PATH = Path(__file__).parent / "_assets" / "viewer.bundle.js"


@lru_cache(maxsize=1)
def get_viewer_bundle_js() -> str:
    if not _BUNDLE_PATH.exists():
        raise FileNotFoundError(
            f"Fluxio viewer bundle missing at {_BUNDLE_PATH}. Run 'pnpm build' first."
        )
    return _BUNDLE_PATH.read_text(encoding="utf-8")


def _safe_json_for_script(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def render_standalone_html(
    spec: dict[str, Any],
    *,
    ws_url: str | None = None,
    full_viewport: bool = True,
) -> str:
    """Generate a 100% self-contained single HTML document with zero external network links."""
    bundle_js = get_viewer_bundle_js()
    spec_json = _safe_json_for_script(spec)
    opts_json = _safe_json_for_script({"wsUrl": ws_url} if ws_url else {})
    title = html.escape(spec.get("title") or "Fluxio Visualization")
    bg = html.escape(
        "transparent"
        if spec.get("theme", {}).get("transparent")
        else spec.get("theme", {}).get("background", "#0b1120")
    )
    width, height = spec.get("size", [900, 520])

    container_css = (
        "width: 100vw; height: 100vh;"
        if full_viewport
        else f"width: 100%; height: {int(height)}px;"
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      background: {bg};
      overflow: hidden;
    }}
    #fluxio-mount {{
      {container_css}
    }}
  </style>
</head>
<body>
  <div id="fluxio-mount"></div>
  <script>{bundle_js}</script>
  <script>
    window.Fluxio.mount("fluxio-mount", {spec_json}, {opts_json});
  </script>
</body>
</html>
"""


def render_jupyter_html(spec: dict[str, Any]) -> str:
    """Render an isolated srcdoc iframe so figures persist cleanly across Jupyter Notebook cells."""
    inner_doc = render_standalone_html(spec, ws_url=None, full_viewport=True)
    escaped_srcdoc = html.escape(inner_doc, quote=True)
    _, height = spec.get("size", [900, 420])
    h = max(240, int(height))
    return (
        f'<div style="width:100%; max-width:{int(spec.get("size", [900, 420])[0])}px; margin:6px 0;">'
        f'<iframe srcdoc="{escaped_srcdoc}" '
        f'style="width:100%; height:{h}px; border:none; border-radius:12px; display:block;" '
        f'allowfullscreen></iframe>'
        f"</div>"
    )
