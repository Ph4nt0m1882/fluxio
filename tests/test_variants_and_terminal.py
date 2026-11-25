from PIL import Image
import pytest
import fluxio as fx


def test_print_fig_ansi_truecolor_and_grid_spans(capsys):
    fig = fx.Figure(rows=2, cols=2, title="Terminal Dashboard")
    fig.style(accent="#38bdf8", accent_side="left")
    fig.number(99.95, unit="%", precision=2, label="Uptime Global", row=0, col=0, col_span=2)
    fig[1, 0].style(accent="#34d399", accent_side="left").number(42.5, unit="°C", precision=1, label="SoC")
    fig[1, 1].style(accent="#f59e0b", accent_side="right").number(1280, unit="req/s", label="Trafic")

    # print(fig) works on ANY figure (even classic!)
    print(fig)
    captured = capsys.readouterr().out

    assert "Terminal Dashboard" in captured
    assert "Uptime Global" in captured
    assert "SoC" in captured
    assert "Trafic" in captured
    # Contains ANSI 24-bit TrueColor escape sequence and Unicode rounded box / block chars
    assert "\x1b[38;2;" in captured
    assert "╭" in captured and "╯" in captured
    assert any(ch in captured for ch in ("█", "▀", "▄"))


def test_export_plain_txt_without_ansi(tmp_path):
    fig = fx.Figure(rows=1, cols=2, title="Rapport Brut")
    fig.number(12.4, unit="ms", precision=1, label="Latence")
    fig.number(98, unit="%", label="Succès")

    txt_path = tmp_path / "rapport.txt"
    fig.save(txt_path)

    content = txt_path.read_text(encoding="utf-8")
    assert "Rapport Brut" in content
    assert "Latence" in content
    assert "Succès" in content
    assert "\x1b[" not in content
    assert "╭" in content


def test_reverse_variant_fills_card_with_accent_and_translucent_text(tmp_path):
    fig = fx.Figure(rows=1, cols=2, title="Comparaison Classic vs Reverse", size=(800, 400))
    fig.style(theme="presentation", accent="#2563eb", accent_side="left")
    # Cell (0,0): classic
    fig[0, 0].number(84.2, unit="%", precision=1, label="Mode Classic")
    # Cell (0,1): reverse with custom accent & text_opacity
    fig[0, 1].style(variant="reverse", accent="#dc2626", text_opacity=0.88).number(
        99.1, unit="%", precision=1, label="Mode Reverse Critique"
    )

    spec = fig.to_spec()
    assert spec["cells"][0]["resolved_style"]["variant"] == "classic"
    assert spec["cells"][1]["resolved_style"]["variant"] == "reverse"
    assert spec["cells"][1]["resolved_style"]["text_opacity"] == pytest.approx(0.88)

    png_path = tmp_path / "reverse.png"
    svg_path = tmp_path / "reverse.svg"
    fig.save(png_path, scale=1.0)
    fig.save(svg_path)

    with Image.open(png_path) as img:
        # Sample background inside top-left corner of Reverse card (away from white text)
        # Card (0,1) starts around x=410, y=75 -> sample (445, 145)
        r, g, b, _ = img.getpixel((445, 145))
        # Red channel dominates strongly (#dc2626 = 220, 38, 38)
        assert r > 180 and g < 80 and b < 80

    assert "#dc2626" in svg_path.read_text(encoding="utf-8")


def test_text_variant_graphical_exports_and_html(tmp_path):
    fig = fx.Figure(rows=1, cols=2, title="Mode TUI Graphique", size=(800, 400))
    fig.style(variant="text", accent="#38bdf8", accent_side="left")
    fig[0, 0].number(42.5, unit="°C", precision=1, label="CPU")
    fig[0, 1].style(accent="#34d399", accent_side="right").number(1024, unit="Mo", label="RAM")

    png_path = tmp_path / "tui.png"
    svg_path = tmp_path / "tui.svg"
    html_path = tmp_path / "tui.html"

    fig.save(png_path, scale=1.0)
    fig.save(svg_path)
    fig.save(html_path)

    assert png_path.exists() and png_path.stat().st_size > 2000
    assert svg_path.exists() and "Mode TUI Graphique" in svg_path.read_text(encoding="utf-8")
    assert '"variant": "text"' in html_path.read_text(encoding="utf-8") or '"variant":"text"' in html_path.read_text(encoding="utf-8")
