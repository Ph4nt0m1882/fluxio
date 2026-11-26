"""AI-optimized documentation generator (`llms.txt`, `llms-full.txt`, condensed `.pyi`) and runtime `llm_context()`."""

from __future__ import annotations
import inspect
import re
from pathlib import Path
from typing import Any

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


def _one_line_doc(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    first = doc.strip().splitlines()[0].strip() if doc.strip() else ""
    return first


def _clean_type_str(ann: Any) -> str:
    text = ann if isinstance(ann, str) else getattr(ann, "__name__", repr(ann))
    replacements = {
        "fluxio.figure.Figure": "Figure",
        "fluxio.figure.SubplotSlot": "SubplotSlot",
        "fluxio.protocol.NumberCell": "NumberCell",
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
        lines.append(f'{indent}def {name}{sig}:')
        lines.append(f'{indent}    """{doc}"""')
        lines.append(f"{indent}    ...")
    else:
        lines.append(f"{indent}def {name}{sig}: ...")
    return lines


def _format_class_stub(cls: type[Any]) -> list[str]:
    lines: list[str] = [f"class {cls.__name__}:"]
    cls_doc = _one_line_doc(cls)
    if cls_doc:
        lines.append(f'    """{cls_doc}"""')

    # Constructor
    if "__init__" in cls.__dict__:
        lines.extend(_format_func_stub("__init__", cls.__dict__["__init__"], indent="    "))

    # Call operator (e.g. FigureStyle)
    if "__call__" in cls.__dict__:
        lines.extend(_format_func_stub("__call__", cls.__dict__["__call__"], indent="    "))

    # Indexing operator (e.g. Figure[row, col])
    if "__getitem__" in cls.__dict__:
        lines.extend(_format_func_stub("__getitem__", cls.__dict__["__getitem__"], indent="    "))

    # Public properties & methods in definition order
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
        fx.NumberCell,
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


def generate_llms_txt() -> str:
    """Generate the compact `llms.txt` index + rules + condensed `.pyi` signatures."""
    stub = generate_stub_pyi().strip()
    chart_pages = sorted((_DOCS_DIR / "charts").glob("*.md")) if (_DOCS_DIR / "charts").exists() else []
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

1. Create a container with `fig = fx.Figure(rows=R, cols=C, title="...", theme="dark" | "light" | "presentation")`.
2. Customize global aesthetics with `fig.style(variant="classic" | "reverse" | "text", background=..., accent="#...", accent_side="left" | "right" | "top" | "bottom" | "none", radius=...)`.
3. Customize a single grid cell via `fig[row, col].style(...).number(...)`.
4. Pass a static float/int, a time function `lambda t: ...`, or a Python generator `(x for x in ...)` to dynamic-capable widgets.
5. Display or export with `fx.show(fig)`, `fig` (last line in Jupyter), `print(fig)` / `fig.print()` (terminal), or `fig.save("out.png" | "out.svg" | "out.gif" | "out.mp4" | "out.html" | "out.txt")`.

## Documentation Index

- [Overview & Quickstart](index.md)
- [Styling, Themes, Gradients & Variants](styling.md)
- [Outputs: Window, Jupyter, Terminal & Exports](outputs.md)
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
    """Generate `llms-full.txt` concatenating all MkDocs Markdown pages + condensed `.pyi` stub."""
    ordered_files: list[Path] = []
    for rel in ("index.md", "styling.md", "outputs.md"):
        p = _DOCS_DIR / rel
        if p.exists():
            ordered_files.append(p)
    if (_DOCS_DIR / "charts").exists():
        ordered_files.extend(sorted((_DOCS_DIR / "charts").glob("*.md")))
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
        body = md_path.read_text(encoding="utf-8").strip()
        sections.append(f"---\n\n<!-- source: docs/{rel_name} -->\n\n{body}")

    return "\n\n".join(sections).rstrip() + "\n"


def build_all_ai_docs() -> dict[str, Path]:
    """Write `fluxio.pyi`, `llms.txt`, and `llms-full.txt` to repo root, `docs/`, and `_assets/`."""
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (_DOCS_DIR / "charts").mkdir(parents=True, exist_ok=True)

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

    # Also copy per-chart markdown docs into _assets/charts/ for offline wheel usage
    asset_charts = _ASSETS_DIR / "charts"
    asset_charts.mkdir(parents=True, exist_ok=True)
    for chart_md in sorted((_DOCS_DIR / "charts").glob("*.md")):
        (asset_charts / chart_md.name).write_text(
            chart_md.read_text(encoding="utf-8"), encoding="utf-8"
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
        for candidate in (_DOCS_DIR / "charts" / f"{clean}.md", _ASSETS_DIR / "charts" / f"{clean}.md"):
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
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
