"""Load generated patches into PureData itself and require a silent console.

Unit tests can confirm py2pd writes the bytes it meant to write. Only PureData
can confirm those bytes describe a patch it will accept -- an out-of-range
connection index, for instance, serializes perfectly and is rejected at load
time with "connection failed".

Skipped when no ``pd`` binary is found. Set ``PD_BIN`` to point at one.
"""

import glob
import os
import shutil
import subprocess

import pytest

from py2pd import Patcher, parse, to_builder
from py2pd.ast import serialize

_CANDIDATE_GLOBS = (
    "/Applications/Pd*.app/Contents/Resources/bin/pd",
    "/Applications/*/Pd*.app/Contents/Resources/bin/pd",
)


def _find_pd() -> str | None:
    override = os.environ.get("PD_BIN")
    if override:
        return override if os.path.isfile(override) else None
    found = shutil.which("pd")
    if found:
        return found
    for pattern in _CANDIDATE_GLOBS:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    return None


PD_BIN = _find_pd()

pytestmark = pytest.mark.skipif(
    PD_BIN is None, reason="no PureData binary found; set PD_BIN to run these"
)


def load_in_pd(path: str) -> str:
    """Open *path* in PureData and return whatever it wrote to the console."""
    assert PD_BIN is not None
    proc = subprocess.run(
        [
            PD_BIN,
            "-nogui",
            "-noaudio",
            "-stderr",
            "-open",
            os.path.basename(path),
            "-send",
            "pd quit",
        ],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(path),
        timeout=60,
    )
    return (proc.stdout + proc.stderr).strip()


def assert_loads_cleanly(patch: Patcher, tmp_path, name: str) -> None:
    target = tmp_path / name
    patch.save(str(target))
    output = load_in_pd(str(target))
    assert output == "", f"PureData rejected {name}:\n{output}\n\n{target.read_text()}"


class TestGeneratedPatchesLoad:
    def test_basic_signal_chain(self, tmp_path):
        p = Patcher()
        osc = p.add("osc~ 440")
        gain = p.add("*~ 0.3")
        dac = p.add("dac~")
        p.link(osc, gain)
        p.link(gain, dac)
        p.link(gain, dac, inlet=1)
        assert_loads_cleanly(p, tmp_path, "basic.pd")

    def test_argument_dependent_channel_counts(self, tmp_path):
        """[dac~ 1 2 3 4] really does accept a connection to inlet 3."""
        p = Patcher()
        osc = p.add("osc~ 440")
        dac = p.add("dac~ 1 2 3 4")
        p.link(osc, dac, inlet=3)
        assert_loads_cleanly(p, tmp_path, "channels.pd")

    def test_every_gui_type(self, tmp_path):
        p = Patcher()
        p.add_bang()
        p.add_toggle()
        p.add_numberbox()
        p.add_float()
        p.add_symbol()
        p.add_hslider()
        p.add_vslider()
        p.add_hradio()
        p.add_vradio()
        p.add_canvas()
        p.add_vu()
        assert_loads_cleanly(p, tmp_path, "guis.pd")

    def test_comment_with_separators(self, tmp_path):
        """An unescaped semicolon in a comment would split the statement."""
        p = Patcher()
        p.add_comment("gain stage; adjust, carefully")
        p.add("osc~ 440")
        assert_loads_cleanly(p, tmp_path, "comment.pd")

    def test_graph_on_parent_with_hidden_name(self, tmp_path):
        inner = Patcher()
        slider = inner.add_hslider(min_val=0, max_val=1000, label="freq")
        outlet = inner.add("outlet")
        inner.link(slider, outlet)
        p = Patcher()
        p.add_subpatch("controls", inner, graph_on_parent=True, hide_name=True, gop_width=150)
        assert_loads_cleanly(p, tmp_path, "gop.pd")

    def test_graph_canvas_with_array(self, tmp_path):
        inner = Patcher()
        inner.add_array("wavetable", 64)
        p = Patcher()
        p.add_subpatch("wavetable", inner, is_graph=True)
        assert_loads_cleanly(p, tmp_path, "graph.pd")

    def test_custom_canvas_geometry(self, tmp_path):
        p = Patcher(canvas_x=100, canvas_y=80, canvas_width=640, canvas_height=480, font_size=12)
        p.add("osc~ 440")
        assert_loads_cleanly(p, tmp_path, "canvas.pd")


class TestRoundTrippedPatchesLoad:
    def test_pd_authored_fixture_reserialized(self, tmp_path):
        source = os.path.join(os.path.dirname(__file__), "examples", "pd_authored.pd")
        with open(source, encoding="utf-8") as handle:
            ast = parse(handle.read())
        target = tmp_path / "reserialized.pd"
        target.write_text(serialize(ast) + "\n", encoding="utf-8")
        assert load_in_pd(str(target)) == ""

    def test_pd_authored_fixture_through_the_builder(self, tmp_path):
        source = os.path.join(os.path.dirname(__file__), "examples", "pd_authored.pd")
        with open(source, encoding="utf-8") as handle:
            ast = parse(handle.read())
        with pytest.warns(Warning):  # scalar and struct have no builder equivalent
            patch = to_builder(ast)
        assert_loads_cleanly(patch, tmp_path, "rebuilt.pd")

    def test_generated_fixture_through_the_builder(self, tmp_path):
        """Double-escaped dollar arguments load without error but mean the wrong thing."""
        source = os.path.join(os.path.dirname(__file__), "examples", "pd_example.pd")
        with open(source, encoding="utf-8") as handle:
            original = handle.read()
        patch = to_builder(parse(original))
        assert_loads_cleanly(patch, tmp_path, "rebuilt2.pd")
        # Escapes must survive unchanged, which loading alone cannot verify.
        assert str(patch).count("\\$") == original.count("\\$")
