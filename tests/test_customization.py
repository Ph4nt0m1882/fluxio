from PIL import Image, ImageDraw
import pytest
import fluxio as fx


def test_global_and_cell_style_methods_cascade():
    fig = fx.Figure(rows=1, cols=2, title="Charte Entreprise")
    # Global style method (chainable)
    ret = fig.style(
        accent="#2563eb",
        accent_side="left",
        radius=18,
        surface_opacity=0.12,
        hover_ms=240,
    )
    assert ret is fig

    fig[0, 0].number(98.4, unit="%", label="Qualité")
    # Per-cell style method (can be called before or after .number)
    fig[0, 1].style(
        accent="#10b981",
        accent_side="right",
        surface_opacity=0.05,
        font_scale=1.15,
    ).number(12.3, unit="ms", label="Réponse")

    spec = fig.to_spec()
    assert spec["theme"]["accent_side"] == "left"
    assert spec["theme"]["radius"] == 18
    assert spec["theme"]["hover_ms"] == 240

    c0 = spec["cells"][0]
    c1 = spec["cells"][1]
    assert c0["resolved_style"]["accent_side"] == "left"
    assert c0["resolved_style"]["accent"] == "#2563eb"

    assert c1["resolved_style"]["accent_side"] == "right"
    assert c1["resolved_style"]["accent"] == "#10b981"
    assert c1["resolved_style"]["surface_opacity"] == pytest.approx(0.05)
    assert c1["resolved_style"]["radius"] == 18  # Inherited from global!


def test_adaptive_translucent_veil_dark_vs_light():
    # Dark gradient -> light translucent veil (#ffffff) and light text
    dark_fig = fx.Figure(title="Dark Slide").style(
        background=fx.Gradient(["#090d16", "#1e1b4b"], angle=135)
    )
    dark_fig.number(42, label="KPI")
    dark_theme = dark_fig.resolved_theme
    assert dark_theme["surface"].lower() == "#ffffff"
    assert 0.08 <= dark_theme["surface_opacity"] <= 0.14
    assert dark_theme["text"].lower() == "#f8fafc"

    # Light gradient -> dark translucent veil (#0f172a) and dark text
    light_fig = fx.Figure(title="Light Slide").style(
        background=fx.Gradient(["#ffffff", "#e0f2fe"], angle=90)
    )
    light_fig.number(42, label="KPI")
    light_theme = light_fig.resolved_theme
    assert light_theme["surface"].lower() == "#0f172a"
    assert 0.06 <= light_theme["surface_opacity"] <= 0.12
    assert light_theme["text"].lower() == "#0f172a"


def test_gradient_background_and_translucent_cards_export(tmp_path):
    fig = fx.Figure(rows=1, cols=2, title="Slide Dégradé", size=(640, 360))
    fig.style(
        background=fx.Gradient(["#7c2d12", "#1e3a8a"], angle=90),
        surface_opacity=0.10,
        accent_side="left",
    )
    fig[0, 0].number(125, unit="k€", label="Gauche")
    fig[0, 1].style(accent_side="right", accent="#34d399").number(240, unit="k€", label="Droite")

    png_path = tmp_path / "grad.png"
    svg_path = tmp_path / "grad.svg"
    html_path = tmp_path / "grad.html"

    fig.save(png_path, scale=1.0)
    fig.save(svg_path)
    fig.save(html_path)

    with Image.open(png_path) as img:
        # Left card interior vs right card interior reflect underlying horizontal gradient!
        left_px = img.getpixel((120, 180))
        right_px = img.getpixel((520, 180))
        # Left side has warm red/orange dominance (#7c2d12), right side has blue dominance (#1e3a8a)
        assert left_px[0] > right_px[0]
        assert right_px[2] > left_px[2]

    svg_text = svg_path.read_text(encoding="utf-8")
    assert "<linearGradient" in svg_text
    assert "grad.html" in str(html_path)
    assert "gradient" in html_path.read_text(encoding="utf-8")


def test_background_image_and_all_accent_sides(tmp_path):
    # Create a synthetic bright corporate background image (top-half cyan, bottom-half amber)
    bg_img_path = tmp_path / "corporate_bg.png"
    bg = Image.new("RGB", (400, 240), (224, 242, 254))
    draw = ImageDraw.Draw(bg)
    draw.rectangle([0, 120, 400, 240], fill=(254, 243, 199))
    bg.save(bg_img_path)

    fig = fx.Figure(rows=2, cols=3, title="Charte Image", size=(720, 420))
    fig.style(background=fx.BackgroundImage(bg_img_path, fit="cover", overlay_opacity=0.05))

    sides = ["left", "right", "top", "bottom", "none", "left"]
    for idx, side in enumerate(sides):
        r, c = divmod(idx, 3)
        fig[r, c].style(accent_side=side, accent_width=4.0).number(idx * 10, label=f"Side {side}")

    # Bright background image should auto-select dark veil (#0f172a)
    assert fig.resolved_theme["surface"].lower() == "#0f172a"

    out_png = tmp_path / "with_image.png"
    out_svg = tmp_path / "with_image.svg"
    out_html = tmp_path / "with_image.html"
    fig.save(out_png, scale=1.0)
    fig.save(out_svg)
    fig.save(out_html)

    assert out_png.exists() and out_png.stat().st_size > 2000
    assert "data:image/png;base64," in out_svg.read_text(encoding="utf-8")
    assert "data:image/png;base64," in out_html.read_text(encoding="utf-8")
