import itertools
import math
import xml.etree.ElementTree as ET
from PIL import Image
import pytest
import fluxio as fx


def test_plot_three_level_hierarchy_and_single_arg_y():
    assert issubclass(fx.Plot, fx.Axis2D)
    assert issubclass(fx.Axis2D, fx.Visual)
    ancestors = [c for c in fx.Plot.__mro__ if c is not object]
    assert ancestors == [fx.Plot, fx.Axis2D, fx.Visual]

    # Passing only y auto-generates x = [0, 1, 2, 3]
    p = fx.Plot([10, 25, 18, 30], label="Série Y", title="Courbe Simple")
    spec = p.to_spec()
    cell = spec["cells"][0]
    assert cell["kind"] == "plot"
    assert cell["series"][0]["x"] == [0.0, 1.0, 2.0, 3.0]
    assert cell["series"][0]["y"] == [10.0, 25.0, 18.0, 30.0]
    assert cell["series"][0]["fill_alpha"] == pytest.approx(0.12)


def test_multi_series_superposition_on_standalone_and_figure_slot():
    fig = fx.Figure(rows=1, cols=2, title="Dashboard Mixte")
    fig[0, 0].number(42.5, unit="°C", label="Température")

    # Calling .plot() twice on slot (0, 1) superposes two series on the SAME Plot!
    xs = [0, 1, 2, 3, 4]
    p1 = fig[0, 1].plot(
        xs, [100, 80, 65, 55, 48], label="Modèle", xlabel="t (s)", ylabel="°C"
    )
    p2 = fig[0, 1].plot(
        xs,
        [98, 83, 62, 57, 46],
        label="Mesure",
        color="#f97316",
        linestyle="dashed",
        marker="circle",
    )
    assert p1 is p2
    assert len(fig.cells) == 2

    spec = fig.to_spec()
    plot_cell = spec["cells"][1]
    assert len(plot_cell["series"]) == 2
    assert plot_cell["series"][0]["label"] == "Modèle"
    assert plot_cell["series"][1]["label"] == "Mesure"
    assert plot_cell["series"][1]["linestyle"] == "dashed"
    assert plot_cell["series"][1]["marker"] == "circle"
    assert plot_cell["xlabel"] == "t (s)"
    assert plot_cell["ylabel"] == "°C"


def test_plot_dynamic_rolling_scalar_and_animated_wave():
    # 1. Scalar generator -> rolling Grafana-like window of max_points=4
    gen = (float(i * 5) for i in itertools.count(1))
    rolling = fx.Plot(gen, label="Flux", max_points=4)
    assert rolling.is_dynamic is True

    for step in range(6):
        upd = rolling.evaluate_tick_update(step * 0.1, step_index=step)
    # Kept last 4 points: steps 2, 3, 4, 5 -> values 15, 20, 25, 30
    assert upd["series_data"][0]["y"] == [15.0, 20.0, 25.0, 30.0]

    # 2. Sequence callable f(t) -> animated wave replaced at each frame
    xs = [0.0, 1.0, 2.0, 3.0]
    wave = fx.Plot(lambda t: (xs, [math.sin(x + t) for x in xs]), label="Onde")
    assert wave.is_dynamic is True
    upd0 = wave.evaluate_tick_update(0.0)
    upd1 = wave.evaluate_tick_update(1.0)
    assert upd0["series_data"][0]["y"] != upd1["series_data"][0]["y"]


def test_plot_braille_terminal_print_and_all_exports(tmp_path, capsys):
    xs = [i * 0.2 for i in range(25)]
    ys1 = [math.sin(x) * 50 + 50 for x in xs]
    ys2 = [math.cos(x) * 40 + 50 for x in xs]

    p = fx.Plot(
        xs,
        ys1,
        label="Sinus",
        xlabel="Temps (s)",
        ylabel="Amplitude",
        title="Oscilloscope Fluxio",
        size=(800, 440),
    )
    p.plot(xs, ys2, label="Cosinus", color="#f97316", linestyle="dashed")

    # 1. Terminal Braille print(p)
    print(p)
    term_out = capsys.readouterr().out
    assert "Oscilloscope Fluxio" in term_out
    assert "Sinus" in term_out and "Cosinus" in term_out
    # Contains Unicode Braille characters (U+2801..U+28FF)
    assert any(0x2801 <= ord(ch) <= 0x28FF for ch in term_out)

    # 2. Exports: PNG, SVG, HTML, TXT, and animated GIF
    png_p = p.save(tmp_path / "plot.png", scale=1.0)
    svg_p = p.save(tmp_path / "plot.svg")
    html_p = p.save(tmp_path / "plot.html")
    txt_p = p.save(tmp_path / "plot.txt")

    with Image.open(png_p) as im:
        assert im.size == (800, 440)

    svg_text = svg_p.read_text(encoding="utf-8")
    ET.fromstring(svg_text)
    assert "Sinus" in svg_text and "<path" in svg_text
    assert "Oscilloscope Fluxio" in html_p.read_text(encoding="utf-8")
    assert any(0x2801 <= ord(ch) <= 0x28FF for ch in txt_p.read_text(encoding="utf-8"))

    # Animated wave GIF export (including fractional scale=0.85 + dashed line IEEE-754 regression check)
    anim_p = fx.Plot(
        lambda t: ([i * 0.16 for i in range(30)], [math.sin(i * 0.16 - t * 2) for i in range(30)]),
        label="Wave",
        size=(420, 260),
    )
    anim_p.plot(
        lambda t: ([i * 0.16 for i in range(30)], [0.5 * math.cos(i * 0.2 + t * 2) for i in range(30)]),
        label="Dashed",
        linestyle="dashed",
    )
    gif_p = anim_p.save(tmp_path / "wave.gif", duration=0.5, fps=8, scale=0.85)
    with Image.open(gif_p) as gim:
        assert getattr(gim, "is_animated", False) is True


def test_plot_legend_positions_top_bottom_none_and_long_titles(tmp_path):
    xs = [0.0, 1.0, 2.0, 3.0]
    fig = fx.Figure(rows=1, cols=3, title="Legend Positions", size=(960, 360))

    # 1. Default ("top", dedicated row underneath bold card_title)
    p_top = fig[0, 0].plot(
        xs,
        [10, 40, 25, 60],
        label="Onde Primaire",
        card_title="Mode Onde — f(t) -> (xs, ys)",
        xlabel="Position (m)",
        ylabel="Amplitude",
    )
    p_top.plot(xs, [50, 20, 45, 15], label="Écho Secondaire", linestyle="dashed")
    assert p_top.legend == "top"

    # 2. Explicit "bottom" (Grafana-style below xlabel)
    p_bot = fig[0, 1].plot(
        xs,
        [-12500, 0, 8400, 15200],
        label="Série A",
        card_title="Légende en bas",
        xlabel="Temps (s)",
        ylabel="Flux (req/s)",
        legend="bottom",
    )
    p_bot.plot(xs, [4000, -3000, 9000, 11000], label="Série B", linestyle="dotted")
    assert p_bot.legend == "bottom"

    # 3. Disabled legend (False -> "none")
    p_none = fig[0, 2].plot(xs, [1, 2, 3, 4], label="Cachée", legend=False)
    assert p_none.legend == "none"

    png_out = fig.save(tmp_path / "legends.png", scale=1.0)
    svg_out = fig.save(tmp_path / "legends.svg")
    txt_out = fig.to_text(ansi=False, width=96)

    with Image.open(png_out) as im:
        assert im.size == (960, 360)
    ET.fromstring(svg_out.read_text(encoding="utf-8"))
    assert "Onde Primaire" in txt_out
    assert "Série A" in txt_out
    assert "Cachée" not in txt_out


def test_axis2d_partial_bounds_xstep_ystep_and_xlim_3tuple(tmp_path):
    from fluxio.charts.families import compute_axis2d_bounds, compute_axis_ticks

    # 1. Explicit xmin/xmax + xstep=2 -> exact columns at 0, 2, 4, 6, 8, 10
    p = fx.Plot(
        [0, 5, 10],
        [15, 65, 40],
        xmin=0,
        xmax=10,
        xstep=2,
        ymin=0,       # partial bound: floor locked at 0, ceiling auto-scales above 65!
        ystep=20,
    )
    spec = p.to_spec()
    c = spec["cells"][0]
    assert c["xmin"] == 0.0
    assert c["xmax"] == 10.0
    assert c["xstep"] == 2.0
    assert c["ymin"] == 0.0
    assert c["ymax"] is None
    assert c["ystep"] == 20.0

    x0, x1, y0, y1 = compute_axis2d_bounds(
        c["series"],
        xlim=c["xlim"],
        ylim=c["ylim"],
        xmin=c["xmin"],
        xmax=c["xmax"],
        ymin=c["ymin"],
        ymax=c["ymax"],
    )
    assert (x0, x1) == (0.0, 10.0)
    assert y0 == 0.0
    assert y1 > 65.0  # auto-padded top while bottom stays pinned at 0.0!

    assert compute_axis_ticks(x0, x1, step=c["xstep"], explicit_min=c["xmin"]) == [
        0.0,
        2.0,
        4.0,
        6.0,
        8.0,
        10.0,
    ]
    assert compute_axis_ticks(y0, y1, step=c["ystep"], explicit_min=c["ymin"]) == [
        0.0,
        20.0,
        40.0,
        60.0,
    ]

    # 2. 3-tuple shorthand xlim=(min, max, step) & ylim=(min, max, step)
    p3 = fx.Plot([1, 2, 3], [10, 50, 90], xlim=(0, 6, 1.5), ylim=(0, 100, 25))
    assert (p3.xmin, p3.xmax, p3.xstep) == (0.0, 6.0, 1.5)
    assert (p3.ymin, p3.ymax, p3.ystep) == (0.0, 100.0, 25.0)

    # Exports & TUI work cleanly with stepped grids
    png_p = p3.save(tmp_path / "stepped.png", scale=1.0)
    svg_p = p3.save(tmp_path / "stepped.svg")
    txt = p3.to_text(ansi=False, width=72)
    with Image.open(png_p) as im:
        assert im.size == p3.size
    svg_src = svg_p.read_text(encoding="utf-8")
    ET.fromstring(svg_src)
    assert "1.5" in svg_src and "4.5" in svg_src
    assert "0" in txt and "6" in txt

    with pytest.raises(ValueError, match="step"):
        fx.Plot([1, 2, 3], xstep=0)
