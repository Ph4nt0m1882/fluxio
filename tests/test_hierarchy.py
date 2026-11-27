from PIL import Image
import pytest
import fluxio as fx


def test_strict_three_level_inheritance_hierarchy():
    # Level 1: Visual
    # Level 2: 6 geometric families
    families = (
        fx.Indicator,
        fx.Axis2D,
        fx.Field2D,
        fx.Polar2D,
        fx.Space3D,
        fx.Scene,
    )
    for fam in families:
        assert issubclass(fam, fx.Visual)
        # Visual (1) -> Family (2) -> object
        fluxio_ancestors = [cls for cls in fam.__mro__ if cls is not object]
        assert len(fluxio_ancestors) == 2

    # Level 3: Concrete Number chart -> strictly 3 Fluxio levels!
    assert issubclass(fx.Number, fx.Indicator)
    assert issubclass(fx.Number, fx.Visual)
    number_ancestors = [cls for cls in fx.Number.__mro__ if cls is not object]
    assert number_ancestors == [fx.Number, fx.Indicator, fx.Visual]


def test_standalone_number_object_supports_style_print_jupyter_and_exports(
    tmp_path, capsys
):
    num = fx.Number(
        73.6,
        unit="%",
        precision=1,
        label="Humidité",
        title="Capteur Autonome",
        size=(640, 320),
    )
    ret = num.style(
        variant="reverse",
        accent="#0284c7",
        accent_side="left",
        background=fx.Gradient(["#090d16", "#1e293b"], angle=120),
    )
    assert ret is num

    # 1. Terminal print(num)
    print(num)
    out_term = capsys.readouterr().out
    assert "Capteur Autonome" in out_term
    assert "Humidité" in out_term
    assert "╭" in out_term

    # 2. Jupyter inline HTML
    jupyter_html = num._repr_html_()
    assert "<iframe" in jupyter_html
    assert "Humidité" in jupyter_html

    # 3. File exports (.png, .svg, .html, .txt)
    png_p = num.save(tmp_path / "standalone_num.png", scale=1.0)
    svg_p = num.save(tmp_path / "standalone_num.svg")
    html_p = num.save(tmp_path / "standalone_num.html")
    txt_p = num.save(tmp_path / "standalone_num.txt")

    with Image.open(png_p) as im:
        assert im.size == (640, 320)
    assert "73.6" in svg_p.read_text(encoding="utf-8")
    assert "Capteur Autonome" in html_p.read_text(encoding="utf-8")
    assert "Humidité" in txt_p.read_text(encoding="utf-8")


def test_hybrid_composition_inside_figure_grid():
    fig = fx.Figure(rows=1, cols=2, title="Dashboard Hybride")
    fig.style(accent_side="left", accent="#38bdf8", radius=18)

    # Slot (0, 0): direct object assignment `fig[0, 0] = fx.Number(...)`
    n0 = fx.Number(42.0, unit="°C", precision=1, label="Objet Direct")
    fig[0, 0] = n0

    # Slot (0, 1): classic builder method `fig[0, 1].number(...)` returns a `fx.Number` instance
    n1 = (
        fig[0, 1]
        .style(accent_side="right", accent="#10b981")
        .number(99.9, unit="%", precision=1, label="Méthode Builder")
    )
    assert isinstance(n1, fx.Number)

    spec = fig.to_spec()
    assert len(spec["cells"]) == 2
    assert spec["cells"][0]["label"] == "Objet Direct"
    assert spec["cells"][0]["resolved_style"]["accent_side"] == "left"
    assert spec["cells"][1]["label"] == "Méthode Builder"
    assert spec["cells"][1]["resolved_style"]["accent_side"] == "right"

    with pytest.raises(TypeError, match="Visual"):
        fig[0, 0] = "not_a_visual"  # type: ignore[assignment]
