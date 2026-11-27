"""AI-optimized documentation, visual gallery & thumbnail generator (`python -m fluxio.ai_docs`)."""

from __future__ import annotations
import inspect
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from PIL import Image

_ASSETS_DIR = Path(__file__).parent / "_assets"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_DIR = _REPO_ROOT / "docs"

_STUB_HEADER = '''"""Auto-generated condensed PEP 484 type stub for Fluxio (token-optimized for LLMs & IDEs)."""

from __future__ import annotations
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any

NumberSource = int | float | Callable[[float], int | float] | Iterator[int | float]
'''


@dataclass(frozen=True)
class GalleryEntry:
    slug: str
    title: str
    family: str
    category: str
    accent_class: str
    summary: str
    builder: Callable[[], Any]


def _build_number_thumb() -> Any:
    import fluxio as fx

    fig = fx.Figure(rows=1, cols=2, title="Number — Classic & Reverse", size=(760, 428))
    fig.style(
        background=fx.Gradient(["#090d16", "#1e1b4b"], angle=135),
        radius=20,
        accent_width=7.5,
    )
    fig[0, 0].style(accent="#38bdf8", accent_side="left").number(
        42.5, unit="°C", precision=1, label="SoC Temp", description="Classic translucent"
    )
    fig[0, 1].style(variant="reverse", accent="#059669", accent_side="right").number(
        99.95, unit="%", precision=2, label="Uptime", description="Reverse solid accent"
    )
    return fig


def _build_plot_thumb() -> Any:
    import fluxio as fx

    xs = [round(i * 0.2, 2) for i in range(36)]
    y1 = [75.0 * math.exp(-0.22 * x) + 20.0 for x in xs]
    y2 = [75.0 * math.exp(-0.22 * x) + 20.0 + 9.0 * math.sin(x * 2.4) for x in xs]
    p = fx.Plot(
        xs,
        y1,
        label="Model",
        xlabel="Time (s)",
        ylabel="Temp (°C)",
        title="Plot — Multi-Series & Area Glow",
        size=(760, 428),
    )
    p.style(
        background=fx.Gradient(["#090d16", "#0f172a", "#1e1b4b"], angle=135),
        accent="#38bdf8",
        accent_side="left",
        radius=20,
    )
    p.plot(xs, y2, label="Sensor", color="#f97316", linestyle="dashed", marker="circle", fill_alpha=0.05)
    return p


GALLERY_ENTRIES: tuple[GalleryEntry, ...] = (
    GalleryEntry(
        slug="plot",
        title="Plot — fig.plot()",
        family="Axis2D",
        category="1. Basic 1D / 2D Charts",
        accent_class="fx-cyan",
        summary="Continuous & dashed multi-series curves, Grafana-style area glow, magnetic hover tooltip, and Braille TUI.",
        builder=_build_plot_thumb,
    ),
    GalleryEntry(
        slug="number",
        title="Number — fig.number()",
        family="Indicator",
        category="8. Indicators & KPIs",
        accent_class="fx-emerald",
        summary="Single KPI metric card supporting static values, f(t) functions, generators, and classic/reverse/text variants.",
        builder=_build_number_thumb,
    ),
)


def generate_gallery_markdown() -> str:
    """Generate `docs/charts/index.md` displaying visual thumbnail cards grouped by category."""
    by_cat: dict[str, list[GalleryEntry]] = {}
    for entry in GALLERY_ENTRIES:
        by_cat.setdefault(entry.category, []).append(entry)

    lines: list[str] = [
        "# Visualizations Gallery",
        "",
        "Every preview below is **auto-generated directly by Python** (`uv run python -m fluxio.ai_docs`). Click any card to view its full signature, parameters, and copy-pasteable examples.",
        "",
    ]

    for cat, items in by_cat.items():
        lines.append(f"## {cat}")
        lines.append("")
        lines.append('<div class="fx-gallery">')
        for item in items:
            lines.append(
                f'  <a class="fx-gallery-card {item.accent_class}" href="{item.slug}/">\n'
                f'    <img class="fx-gallery-thumb" src="../assets/charts/{item.slug}.png" alt="{item.title}" />\n'
                f'    <div class="fx-gallery-body">\n'
                f'      <span class="fx-gallery-badge">{item.family}</span>\n'
                f'      <h3 class="fx-gallery-title">{item.title}</h3>\n'
                f'      <p class="fx-gallery-desc">{item.summary}</p>\n'
                f"    </div>\n"
                f"  </a>"
            )
        lines.append("</div>")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_visual_assets() -> list[Path]:
    """Render chart thumbnails and web-optimized docs banner into `docs/assets/`."""
    charts_assets_dir = _DOCS_DIR / "assets" / "charts"
    charts_assets_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Copy/downscale `.github/assets/banner.webp` to `docs/assets/banner.webp` for instant page load
    src_banner = _REPO_ROOT / ".github" / "assets" / "banner.webp"
    dst_banner = _DOCS_DIR / "assets" / "banner.webp"
    if src_banner.exists() and not dst_banner.exists():
        with Image.open(src_banner) as im:
            target_w = min(1600, im.width)
            target_h = int(round(im.height * (target_w / im.width)))
            im.resize((target_w, target_h), resample=Image.Resampling.LANCZOS).save(
                dst_banner, format="WEBP", quality=86
            )
        written.append(dst_banner)

    for entry in GALLERY_ENTRIES:
        out_png = charts_assets_dir / f"{entry.slug}.png"
        vis = entry.builder()
        vis.save(out_png, scale=1.5)
        written.append(out_png)

    # Extra tutorial static & seamless-loop animated GIF assets
    import itertools
    import fluxio as fx

    # 1. Minimal 2-line examples
    min_plot = fx.Plot([12, 28, 19, 37, 31, 46], size=(720, 340))
    p_min_plot = charts_assets_dir / "tutorial_minimal_plot.png"
    min_plot.save(p_min_plot, scale=1.5)
    written.append(p_min_plot)

    min_num = fx.Number(42.5, unit="°C", label="Core Temp", size=(680, 280))
    p_min_num = charts_assets_dir / "tutorial_minimal_number.png"
    min_num.save(p_min_num, scale=1.5)
    written.append(p_min_num)

    # 2. Graphical `text` TUI variant preview
    tui_fig = fx.Figure(rows=1, cols=2, title="Variant 'text' — Graphical TUI", size=(760, 340))
    tui_fig.style(variant="text", accent="#38bdf8", accent_side="left")
    tui_fig[0, 0].number(43.8, unit="°C", precision=1, label="SoC RasPi", description="Nominal sensor")
    tui_fig[0, 1].style(accent="#34d399", accent_side="right").number(
        1280, unit="req/s", precision=0, label="API Rate", description="10s rolling mean"
    )
    p_tui = charts_assets_dir / "tutorial_text_variant.png"
    tui_fig.save(p_tui, scale=1.5)
    written.append(p_tui)

    # 3. Seamless 2-second animated GIF for `Number`
    num_anim = fx.Figure(rows=1, cols=2, title="Live KPI Stream", size=(720, 300), fps=14)
    num_anim.style(background=fx.Gradient(["#090d16", "#1e1b4b"], angle=135), radius=18)
    num_anim[0, 0].style(accent="#f97316", accent_side="left").number(
        lambda t: 850.0 + 110.0 * math.sin(2.0 * math.pi * t / 2.0),
        unit="°C",
        precision=1,
        label="Magma Temp",
    )
    num_anim[0, 1].style(variant="reverse", accent="#2563eb", accent_side="right").number(
        (i * 15 for i in itertools.count(1)),
        unit="pkt",
        precision=0,
        label="Network Packets",
    )
    p_num_gif = charts_assets_dir / "number_anim.gif"
    num_anim.save(p_num_gif, duration=2.0, fps=14, scale=0.85)
    written.append(p_num_gif)

    # 4. Seamless 2-second animated GIF for `Plot`
    w_xs = [i * 0.16 for i in range(42)]
    plot_anim = fx.Plot(
        lambda t: (
            w_xs,
            [math.sin(x - 2.0 * math.pi * t / 2.0) * math.cos(x * 0.28) for x in w_xs],
        ),
        label="Wave Mode",
        xlabel="Position (m)",
        ylabel="Displacement",
        ylim=(-1.15, 1.15),
        title="Travelling Wave Packet",
        size=(720, 340),
        fps=14,
    )
    plot_anim.style(background=fx.Gradient(["#090d16", "#0f172a", "#1e1b4b"], angle=135), radius=18)
    plot_anim.plot(
        lambda t: (
            w_xs,
            [0.55 * math.cos(x * 1.3 + 2.0 * math.pi * t / 2.0) for x in w_xs],
        ),
        label="Counter-Wave",
        color="#f97316",
        linestyle="dashed",
        fill_alpha=0.04,
    )
    p_plot_gif = charts_assets_dir / "plot_anim.gif"
    plot_anim.save(p_plot_gif, duration=2.0, fps=14, scale=0.85)
    written.append(p_plot_gif)

    # 5. Seamless 2-second combined tutorial GIF (also copied to .github/assets/ for README.md!)
    tut_anim = fx.Figure(
        rows=1,
        cols=2,
        title="Live Sensor & Travelling Wave",
        size=(780, 330),
        fps=14,
    )
    tut_anim.style(background=fx.Gradient(["#090d16", "#0f172a", "#1e1b4b"], angle=135), radius=18)
    tut_anim[0, 0].style(variant="reverse", accent="#059669", accent_side="left").number(
        lambda t: 850.0 + 95.0 * math.sin(2.0 * math.pi * t / 2.0),
        unit="°C",
        precision=1,
        label="Magma Chamber",
    )
    t_xs = [i * 0.18 for i in range(36)]
    tut_anim[0, 1].style(accent="#38bdf8", accent_side="right").plot(
        lambda t: (
            t_xs,
            [math.sin(x - 2.0 * math.pi * t / 2.0) * math.cos(x * 0.3) for x in t_xs],
        ),
        label="Seismic Wave",
        xlabel="Distance (km)",
        ylim=(-1.15, 1.15),
    )
    p_tut_gif = charts_assets_dir / "tutorial_live.gif"
    tut_anim.save(p_tut_gif, duration=2.0, fps=14, scale=0.85)
    written.append(p_tut_gif)

    gh_assets = _REPO_ROOT / ".github" / "assets"
    if gh_assets.exists():
        (gh_assets / "demo_04_live_plot.gif").write_bytes(p_tut_gif.read_bytes())

    # 6. Pixel-locked ANSI TrueColor Terminal SVGs (zero font misalignment in docs & README!)
    from .text_render import render_ansi_to_svg

    term_plot_xs = [i * 0.25 for i in range(28)]
    term_plot = fx.Plot(term_plot_xs, [math.sin(x) for x in term_plot_xs], label="sin(x)", xlabel="x")
    term_plot.plot(
        term_plot_xs,
        [math.cos(x) for x in term_plot_xs],
        label="cos(x)",
        linestyle="dashed",
        color="#f97316",
    )
    p_plot_term = charts_assets_dir / "plot_terminal.svg"
    p_plot_term.write_text(
        render_ansi_to_svg(term_plot.to_text(ansi=True, width=74), title="python3 — print(p)"),
        encoding="utf-8",
    )
    written.append(p_plot_term)

    term_num = fx.Number(
        99.95, unit="%", precision=2, label="Availability", description="SLA > 99.9%"
    ).style(accent="#34d399", accent_side="left")
    p_num_term = charts_assets_dir / "number_terminal.svg"
    p_num_term.write_text(
        render_ansi_to_svg(term_num.to_text(ansi=True, width=72), title="python3 — print(n)"),
        encoding="utf-8",
    )
    written.append(p_num_term)

    term_tut = fx.Plot([12, 28, 19, 37, 31, 46], label="Requests")
    p_tut_term = charts_assets_dir / "tutorial_terminal.svg"
    p_tut_term.write_text(
        render_ansi_to_svg(term_tut.to_text(ansi=True, width=74), title="python3 — print(p)"),
        encoding="utf-8",
    )
    written.append(p_tut_term)

    if gh_assets.exists():
        readme_tui = fx.Figure(
            rows=1,
            cols=2,
            title="Variante Texte (TUI / Console)",
            subtitle="Rendu identique dans une fenêtre graphique, Jupyter ou le terminal via print(fig)",
        )
        readme_tui.style(variant="text", accent="#38bdf8", accent_side="left")
        readme_tui[0, 0].number(
            43.8, unit="°C", precision=1, label="SoC RasPi", description="Capteur thermique nominal"
        )
        readme_tui[0, 1].style(accent="#34d399", accent_side="right").number(
            1280, unit="req/s", precision=0, label="Débit API", description="Moyenne glissante 10s"
        )
        (gh_assets / "demo_03_terminal.svg").write_text(
            render_ansi_to_svg(readme_tui.to_text(ansi=True, width=78), title="zsh — print(fig)"),
            encoding="utf-8",
        )

    gallery_md_path = _DOCS_DIR / "charts" / "index.md"
    gallery_md_path.parent.mkdir(parents=True, exist_ok=True)
    gallery_md_path.write_text(generate_gallery_markdown(), encoding="utf-8")
    written.append(gallery_md_path)
    return written


def _one_line_doc(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.strip().splitlines()[0].strip() if doc.strip() else ""


def _clean_type_str(ann: Any) -> str:
    text = ann if isinstance(ann, str) else getattr(ann, "__name__", repr(ann))
    replacements = {
        "fluxio.figure.Figure": "Figure",
        "fluxio.figure.SubplotSlot": "SubplotSlot",
        "fluxio.charts.base.Visual": "Visual",
        "fluxio.charts.number.Number": "Number",
        "fluxio.charts.plot.Plot": "Plot",
        "fluxio.protocol.NumberCell": "Number",
        "fluxio.theme.Gradient": "Gradient",
        "fluxio.theme.BackgroundImage": "BackgroundImage",
        "pathlib._local.Path": "Path",
        "pathlib.Path": "Path",
        "int | float | collections.abc.Callable[[float], int | float] | collections.abc.Iterator[int | float]": "NumberSource",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\bcollections\.abc\.", "", text)
    text = re.sub(r"\btyping\.", "", text)
    return text


def _clean_sig_str(sig: inspect.Signature) -> str:
    params_out: list[str] = []
    inserted_kw_star = False
    for p in sig.parameters.values():
        if p.name != "self" and p.name.startswith("_"):
            continue
        if p.kind == inspect.Parameter.KEYWORD_ONLY and not inserted_kw_star:
            params_out.append("*")
            inserted_kw_star = True
        if p.kind == inspect.Parameter.VAR_POSITIONAL:
            prefix = "*"
            inserted_kw_star = True
        elif p.kind == inspect.Parameter.VAR_KEYWORD:
            prefix = "**"
        else:
            prefix = ""

        piece = f"{prefix}{p.name}"
        if p.annotation is not inspect.Parameter.empty:
            piece += f": {_clean_type_str(p.annotation)}"
        if p.default is not inspect.Parameter.empty:
            d_repr = repr(p.default)
            if d_repr.startswith("<") and d_repr.endswith(">"):
                d_repr = "..."
            piece += f" = {d_repr}"
        params_out.append(piece)

    ret = ""
    if sig.return_annotation is not inspect.Signature.empty:
        ret = f" -> {_clean_type_str(sig.return_annotation)}"
    return f"({', '.join(params_out)}){ret}"


def _format_func_stub(name: str, fn: Any, indent: str = "") -> list[str]:
    sig = _clean_sig_str(inspect.signature(fn))
    doc = _one_line_doc(fn)
    lines: list[str] = []
    if doc:
        lines.append(f"{indent}def {name}{sig}:")
        lines.append(f'{indent}    """{doc}"""')
        lines.append(f"{indent}    ...")
    else:
        lines.append(f"{indent}def {name}{sig}: ...")
    return lines


def _format_class_stub(cls: type[Any]) -> list[str]:
    bases = [
        b.__name__
        for b in cls.__bases__
        if b is not object and not b.__name__.startswith("MutableMapping")
    ]
    base_str = f"({', '.join(bases)})" if bases else ""
    lines: list[str] = [f"class {cls.__name__}{base_str}:"]
    cls_doc = _one_line_doc(cls)
    if cls_doc:
        lines.append(f'    """{cls_doc}"""')

    if "__init__" in cls.__dict__:
        lines.extend(_format_func_stub("__init__", cls.__dict__["__init__"], indent="    "))
    if "__call__" in cls.__dict__:
        lines.extend(_format_func_stub("__call__", cls.__dict__["__call__"], indent="    "))
    if "__getitem__" in cls.__dict__:
        lines.extend(_format_func_stub("__getitem__", cls.__dict__["__getitem__"], indent="    "))
    if "__setitem__" in cls.__dict__:
        lines.extend(_format_func_stub("__setitem__", cls.__dict__["__setitem__"], indent="    "))

    for attr_name, attr_val in cls.__dict__.items():
        if attr_name.startswith("_"):
            continue
        if isinstance(attr_val, property) and attr_val.fget is not None:
            sig = _clean_sig_str(inspect.signature(attr_val.fget))
            ret = sig.split("->")[1].strip() if "->" in sig else "Any"
            lines.append("    @property")
            lines.append(f"    def {attr_name}(self) -> {ret}: ...")
        elif inspect.isfunction(attr_val):
            lines.extend(_format_func_stub(attr_name, attr_val, indent="    "))

    if len(lines) == 1:
        lines.append("    ...")
    return lines


def generate_stub_pyi() -> str:
    """Introspect Fluxio's live public Python objects and emit a condensed, valid `.pyi` stub."""
    import fluxio as fx

    blocks: list[str] = [_STUB_HEADER.rstrip()]
    classes = [
        fx.Gradient,
        fx.BackgroundImage,
        fx.ToolbarConfig,
        fx.Visual,
        fx.Indicator,
        fx.Axis2D,
        fx.Field2D,
        fx.Polar2D,
        fx.Space3D,
        fx.Scene,
        fx.Number,
        fx.Plot,
        fx.FigureStyle,
        fx.SubplotSlot,
        fx.Figure,
    ]
    for cls in classes:
        blocks.append("\n".join(_format_class_stub(cls)))

    fn_lines: list[str] = []
    for fn_name in ("show", "save", "print", "llm_context"):
        fn_obj = getattr(fx, fn_name)
        fn_lines.extend(_format_func_stub(fn_name, fn_obj))
    blocks.append("\n".join(fn_lines))

    return "\n\n".join(blocks).rstrip() + "\n"


def _strip_visual_html_for_llm(md_text: str) -> str:
    """Strip YAML frontmatter, decorative HTML wrappers, and image tags to save LLM tokens."""
    # Strip YAML frontmatter
    if md_text.startswith("---\n"):
        end_fm = md_text.find("\n---\n", 4)
        if end_fm != -1:
            md_text = md_text[end_fm + 5 :]
    # Strip decorative <div class="fx-..."> ... </div> blocks
    md_text = re.sub(r'<div class="fx-[^"]*">.*?</div>\s*(?:</div>)?', "", md_text, flags=re.DOTALL)
    # Strip Markdown image embeds `![...](...){ ... }`
    md_text = re.sub(r"!\[[^\]]*\]\([^)]+\)(?:\{[^}]*\})?\n*", "", md_text)
    return md_text.strip()


def generate_llms_txt() -> str:
    """Generate the compact `llms.txt` index + rules + condensed `.pyi` signatures."""
    stub = generate_stub_pyi().strip()
    chart_pages = (
        [p for p in sorted((_DOCS_DIR / "charts").glob("*.md")) if p.name != "index.md"]
        if (_DOCS_DIR / "charts").exists()
        else []
    )
    chart_bullets = []
    for p in chart_pages:
        first_heading = next(
            (ln.lstrip("# ").strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.startswith("# ")),
            p.stem,
        )
        chart_bullets.append(f"- [{first_heading}](charts/{p.name})")
    charts_section = "\n".join(chart_bullets) if chart_bullets else "- [number()](charts/number.md)"

    return f"""# Fluxio

> Fluxio (`import fluxio as fx`) is a modern, lightweight, real-time Python + TypeScript `<canvas>` visualization library supporting desktop windows (`fx.show`), persistent Jupyter notebooks, ANSI TrueColor terminals (`print(fig)` / `fig.print()`), and headless exports (`.png`, `.svg`, `.gif`, `.mp4`, `.html`, `.txt`).

## Golden Rules for AI Code Generation

1. Create a standalone chart (`fx.Plot(...)`, `fx.Number(...)`) or a multi-cell grid (`fig = fx.Figure(rows=R, cols=C, title="...", theme="dark" | "light" | "presentation")`).
2. Customize global aesthetics with `fig.style(variant="classic" | "reverse" | "text", background=..., accent="#...", accent_side="left" | "right" | "top" | "bottom" | "none", radius=...)`.
3. Customize a single grid cell via `fig[row, col].style(...).plot(...)` or `fig[row, col].number(...)`.
4. Pass a static float/sequence, a time function `lambda t: ...`, or a Python generator `(x for x in ...)` to dynamic-capable widgets.
5. Display or export with `fx.show(fig)`, `fig` (last line in Jupyter), `print(fig)` / `fig.print()` (terminal), or `fig.save("out.png" | "out.svg" | "out.gif" | "out.mp4" | "out.html" | "out.txt")`.

## Documentation Index

- [Overview & Quickstart](index.md)
- [Step-by-Step Tutorial](tutorial.md)
- [Styling, Themes, Gradients & Variants](styling.md)
- [Architecture & 3-Level OOP Hierarchy](developer.md)
- [Outputs: Window, Jupyter, Terminal & Exports](outputs.md)
- [Visualizations Gallery](charts/index.md)
- [AI & Chatbot Integration](ai-integration.md)
- [Complete Documentation Bundle](llms-full.txt)

## Available Charts & Widgets

{charts_section}

## Condensed Python API Signatures (`fluxio.pyi`)

```python
{stub}
```
"""


def generate_llms_full_txt() -> str:
    """Generate `llms-full.txt` concatenating clean Markdown pages + condensed `.pyi` stub."""
    ordered_files: list[Path] = []
    for rel in ("index.md", "tutorial.md", "styling.md", "developer.md", "outputs.md"):
        p = _DOCS_DIR / rel
        if p.exists():
            ordered_files.append(p)
    if (_DOCS_DIR / "charts").exists():
        ordered_files.extend(
            p for p in sorted((_DOCS_DIR / "charts").glob("*.md")) if p.name != "index.md"
        )
    ai_p = _DOCS_DIR / "ai-integration.md"
    if ai_p.exists():
        ordered_files.append(ai_p)

    sections: list[str] = [
        "# Fluxio — Complete LLM Reference (`llms-full.txt`)",
        "## Condensed API Type Stub (`fluxio.pyi`)\n\n```python\n"
        + generate_stub_pyi().strip()
        + "\n```",
    ]
    for md_path in ordered_files:
        rel_name = md_path.relative_to(_DOCS_DIR).as_posix()
        body = _strip_visual_html_for_llm(md_path.read_text(encoding="utf-8"))
        if body:
            sections.append(f"---\n\n<!-- source: docs/{rel_name} -->\n\n{body}")

    return "\n\n".join(sections).rstrip() + "\n"


def build_all_ai_docs() -> dict[str, Path]:
    """Render gallery thumbnails + write `charts/index.md`, `fluxio.pyi`, `llms.txt`, and `llms-full.txt`."""
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (_DOCS_DIR / "charts").mkdir(parents=True, exist_ok=True)

    _build_visual_assets()

    stub = generate_stub_pyi()
    llms = generate_llms_txt()
    llms_full = generate_llms_full_txt()

    written: dict[str, Path] = {}
    targets = {
        "root_llms": (_REPO_ROOT / "llms.txt", llms),
        "root_llms_full": (_REPO_ROOT / "llms-full.txt", llms_full),
        "docs_llms": (_DOCS_DIR / "llms.txt", llms),
        "docs_llms_full": (_DOCS_DIR / "llms-full.txt", llms_full),
        "docs_pyi": (_DOCS_DIR / "fluxio.pyi", stub),
        "asset_llms": (_ASSETS_DIR / "llms.txt", llms),
        "asset_llms_full": (_ASSETS_DIR / "llms-full.txt", llms_full),
        "asset_pyi": (_ASSETS_DIR / "fluxio.pyi", stub),
    }
    for key, (path, content) in targets.items():
        path.write_text(content, encoding="utf-8")
        written[key] = path

    asset_charts = _ASSETS_DIR / "charts"
    asset_charts.mkdir(parents=True, exist_ok=True)
    for chart_md in sorted((_DOCS_DIR / "charts").glob("*.md")):
        if chart_md.name != "index.md":
            (asset_charts / chart_md.name).write_text(
                _strip_visual_html_for_llm(chart_md.read_text(encoding="utf-8")) + "\n",
                encoding="utf-8",
            )

    return written


def llm_context(
    mode: str = "compact",
    *,
    chart: str | None = None,
) -> str:
    """Return AI-optimized Fluxio documentation at runtime (`'compact'`, `'full'`, `'stub'`, or `chart='...'`)."""
    if chart is not None:
        clean = chart.strip().removesuffix(".md")
        asset_candidate = _ASSETS_DIR / "charts" / f"{clean}.md"
        if asset_candidate.exists():
            return asset_candidate.read_text(encoding="utf-8")
        doc_candidate = _DOCS_DIR / "charts" / f"{clean}.md"
        if doc_candidate.exists():
            return _strip_visual_html_for_llm(doc_candidate.read_text(encoding="utf-8")) + "\n"
        raise ValueError(f"Unknown Fluxio chart documentation: '{chart}'")

    if mode == "stub":
        p = _ASSETS_DIR / "fluxio.pyi"
        return p.read_text(encoding="utf-8") if p.exists() else generate_stub_pyi()
    if mode == "compact":
        p = _ASSETS_DIR / "llms.txt"
        return p.read_text(encoding="utf-8") if p.exists() else generate_llms_txt()
    if mode == "full":
        p = _ASSETS_DIR / "llms-full.txt"
        return p.read_text(encoding="utf-8") if p.exists() else generate_llms_full_txt()

    raise ValueError("Invalid mode. Expected 'compact', 'full', or 'stub'.")


if __name__ == "__main__":
    paths = build_all_ai_docs()
    for label, p in paths.items():
        if label.startswith("root_") or label == "docs_pyi":
            size_kb = p.stat().st_size / 1024
            print(f"Generated {p.relative_to(_REPO_ROOT)} ({size_kb:.1f} KB)")
    print("Generated docs/charts/index.md & docs/assets/charts/*.png thumbnails")
