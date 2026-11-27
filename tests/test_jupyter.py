import nbformat
from nbclient import NotebookClient
import fluxio as fx


def test_jupyter_notebook_persistence_across_cells(tmp_path):
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_code_cell(
            "import fluxio as fx\n"
            "fig = fx.Figure(rows=1, cols=2, title='Cellule 1 Persistante', theme='dark')\n"
            "fig.number(42, unit='°C', label='Capteur A')\n"
            "fig"
        ),
        nbformat.v4.new_code_cell(
            "# Cellule 2 : calcul indépendant, la sortie de la Cellule 1 doit rester intacte\n"
            "x = 21 * 2\n"
            "x"
        ),
        nbformat.v4.new_code_cell(
            "# Cellule 3 : on enrichit la MÊME figure et on l'affiche mise à jour !\n"
            "fig.number(x * 2, unit='%', label='Capteur B')\n"
            "fig"
        ),
        nbformat.v4.new_code_cell(
            "# Cellule 4 : print(fig) et fig.print(duration=...) dans Jupyter\n"
            "dyn = fx.Figure(title='Live Console Jupyter', fps=15)\n"
            "dyn.number(lambda t: round(10 + t * 100, 1), unit='pts', precision=1, label='Score')\n"
            "dyn.print(duration=0.25, fps=15)"
        ),
    ]

    client = NotebookClient(nb, timeout=30, kernel_name="python3")
    executed_nb = client.execute()

    # Save and reload from disk to prove .ipynb persistence
    ipynb_path = tmp_path / "test_persist.ipynb"
    nbformat.write(executed_nb, ipynb_path)
    reloaded = nbformat.read(ipynb_path, as_version=4)

    # Cell 0 still has its rich HTML output with Capteur A
    out0 = reloaded.cells[0].outputs
    assert any("text/html" in o.get("data", {}) for o in out0)
    html0 = next(
        o["data"]["text/html"] for o in out0 if "text/html" in o.get("data", {})
    )
    assert "Capteur A" in html0

    # Cell 1 has 42
    out1 = reloaded.cells[1].outputs
    assert any("42" in o.get("data", {}).get("text/plain", "") for o in out1)

    # Cell 2 has BOTH Capteur A and Capteur B in its rendered figure!
    out2 = reloaded.cells[2].outputs
    html2 = next(
        o["data"]["text/html"] for o in out2 if "text/html" in o.get("data", {})
    )
    assert "Capteur A" in html2
    assert "Capteur B" in html2

    # Cell 3 (`dyn.print(duration=0.25)`) updates in-place via clear_output and leaves final frame!
    out3 = reloaded.cells[3].outputs
    stdout3 = "".join(
        o.get("text", "") for o in out3 if o.get("output_type") == "stream"
    )
    assert "╭" in stdout3 and "╯" in stdout3
    assert "Live Console Jupyter" in stdout3
    # Only the final in-place frame remains in the cell output (not 4 stacked frames!)
    assert stdout3.count("Live Console Jupyter") == 1
