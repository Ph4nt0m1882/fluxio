import ast
import inspect
import subprocess
import sys
from pathlib import Path
import fluxio as fx
from fluxio.ai_docs import (
    generate_llms_full_txt,
    generate_llms_txt,
    generate_stub_pyi,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Utility / lifecycle methods on Figure that are NOT chart constructors
NON_CHART_FIGURE_METHODS = {
    "add",
    "evaluate_frame",
    "is_dynamic",
    "print",
    "reset_print",
    "resolved_theme",
    "save",
    "show",
    "style",
    "to_spec",
    "to_text",
}


def test_py_typed_and_agents_md_exist():
    py_typed = REPO_ROOT / "src" / "fluxio" / "py.typed"
    agents_md = REPO_ROOT / "AGENTS.md"
    assert py_typed.exists()
    assert agents_md.exists()
    content = agents_md.read_text(encoding="utf-8")
    assert "Fluxio" in content
    assert "TODO.md" in content


def test_generated_pyi_stub_is_valid_python_and_covers_public_api():
    stub_src = fx.llm_context("stub")
    assert stub_src == generate_stub_pyi()

    # Must parse cleanly as valid Python / .pyi AST
    tree = ast.parse(stub_src)
    defined_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    for expected in (
        "Figure",
        "FigureStyle",
        "SubplotSlot",
        "Gradient",
        "BackgroundImage",
        "show",
        "save",
        "print",
        "llm_context",
    ):
        assert expected in defined_names

    # Every public method of Figure must appear in the .pyi stub
    fig_cls_node = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Figure"
    )
    stub_fig_methods = {
        n.name for n in fig_cls_node.body if isinstance(n, ast.FunctionDef)
    }
    real_public_methods = {
        name
        for name, member in inspect.getmembers(fx.Figure, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert real_public_methods.issubset(stub_fig_methods)


def test_every_chart_method_has_dedicated_mkdocs_page():
    chart_methods = [
        name
        for name, _ in inspect.getmembers(fx.Figure, predicate=inspect.isfunction)
        if not name.startswith("_") and name not in NON_CHART_FIGURE_METHODS
    ]
    assert "number" in chart_methods
    assert "plot" in chart_methods

    gallery_index = (REPO_ROOT / "docs" / "charts" / "index.md").read_text(encoding="utf-8")
    for chart in chart_methods:
        page = REPO_ROOT / "docs" / "charts" / f"{chart}.md"
        thumb = REPO_ROOT / "docs" / "assets" / "charts" / f"{chart}.png"
        notebook = REPO_ROOT / "examples" / "all_examples" / f"{chart}.ipynb"
        assert page.exists(), f"Missing MkDocs chart page: {page}"
        assert thumb.exists(), f"Missing generated gallery thumbnail: {thumb}"
        assert notebook.exists(), f"Missing per-chart showcase notebook: {notebook}"
        assert f'href="{chart}/"' in gallery_index, f"Chart '{chart}' missing from Gallery Overview!"
        chart_doc = fx.llm_context(chart=chart)
        assert f"fig.{chart}" in chart_doc


def test_llms_txt_and_llms_full_txt_are_in_sync():
    llms_path = REPO_ROOT / "llms.txt"
    llms_full_path = REPO_ROOT / "llms-full.txt"
    assert llms_path.exists()
    assert llms_full_path.exists()

    assert llms_path.read_text(encoding="utf-8") == generate_llms_txt()
    assert llms_full_path.read_text(encoding="utf-8") == generate_llms_full_txt()

    compact = fx.llm_context("compact")
    full = fx.llm_context("full")
    assert "# Fluxio" in compact
    assert "def number(" in compact
    assert len(full) > len(compact)


def test_mkdocs_strict_build_passes(tmp_path):
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "--strict",
            "--site-dir",
            str(tmp_path / "site"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"mkdocs --strict failed:\n{res.stderr}\n{res.stdout}"
    assert (tmp_path / "site" / "index.html").exists()
    assert (tmp_path / "site" / "tutorial" / "index.html").exists()
    assert (tmp_path / "site" / "developer" / "index.html").exists()
    assert (tmp_path / "site" / "charts" / "index.html").exists()
    assert (tmp_path / "site" / "charts" / "number" / "index.html").exists()
    assert (tmp_path / "site" / "charts" / "plot" / "index.html").exists()
    assert (tmp_path / "site" / "assets" / "charts" / "tutorial_live.gif").exists()
    assert (tmp_path / "site" / "assets" / "charts" / "plot_anim.gif").exists()
    assert (tmp_path / "site" / "llms.txt").exists()
    # Verify Prev/Next footer navigation is rendered on inner pages
    plot_html = (tmp_path / "site" / "charts" / "plot" / "index.html").read_text(encoding="utf-8")
    assert "md-footer__link" in plot_html
