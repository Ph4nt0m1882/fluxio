import subprocess
import xml.etree.ElementTree as ET
from PIL import Image
import fluxio as fx


def test_export_png_and_transparent_presentation(tmp_path):
    fig = fx.Figure(
        rows=1,
        cols=2,
        title="Slide PowerPoint",
        theme="presentation",
        style={"transparent": True, "accent": "#2563eb"},
        size=(800, 450),
    )
    fig.number(42.5, unit="°C", label="Température", precision=1)
    fig.number(99.9, unit="%", label="Disponibilité", precision=1)

    png_path = tmp_path / "slide.png"
    fig.save(png_path, scale=1.0)

    assert png_path.exists()
    with Image.open(png_path) as img:
        assert img.size == (800, 450)
        assert img.mode == "RGBA"
        # Top-left corner pixel is transparent when style.transparent=True
        assert img.getpixel((2, 2))[3] == 0


def test_export_svg(tmp_path):
    fig = fx.Figure(title="Vector Export", theme="light", size=(640, 360))
    fig.number(1024, unit="req/s", label="Débit")

    svg_path = tmp_path / "vector.svg"
    fig.save(svg_path)

    assert svg_path.exists()
    content = svg_path.read_text(encoding="utf-8")
    root = ET.fromstring(content)
    assert root.tag.endswith("svg")
    assert "1024" in content
    assert "Débit" in content


def test_export_animated_gif(tmp_path):
    fig = fx.Figure(title="Compteur Dynamique", theme="dark", size=(480, 300))
    fig.number(lambda t: round(10 + t * 20, 1), unit="m/s", label="Vitesse", precision=1)

    gif_path = tmp_path / "anim.gif"
    fig.save(gif_path, duration=1.0, fps=10, scale=1.0)

    assert gif_path.exists()
    with Image.open(gif_path) as img:
        assert getattr(img, "is_animated", False) is True
        assert getattr(img, "n_frames", 0) == 10


def test_export_mp4_video(tmp_path):
    fig = fx.Figure(title="Vidéo Temps Réel", theme="dark", size=(480, 300))
    fig.number(lambda t: 50 + t * 10, unit="Hz", label="Fréquence", precision=1)

    mp4_path = tmp_path / "video.mp4"
    fig.save(mp4_path, duration=1.0, fps=12, scale=1.0)

    assert mp4_path.exists()
    assert mp4_path.stat().st_size > 1000

    # Verify valid video stream with ffprobe
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height",
            "-of",
            "csv=p=0",
            str(mp4_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "h264" in probe.stdout
    assert "480,300" in probe.stdout


def test_export_standalone_html(tmp_path):
    fig = fx.Figure(title="HTML Autonome", theme="dark")
    fig.number(lambda t: t * 5, unit="s", label="Chrono", precision=1)

    html_path = tmp_path / "standalone.html"
    fig.save(html_path, duration=2.0, fps=10)

    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "Fluxio" in html
    assert "HTML Autonome" in html
    # Zero external CDN links so it works 100% offline on RasPi/phone
    assert "https://cdn" not in html
