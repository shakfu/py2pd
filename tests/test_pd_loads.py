"""Load generated patches into PureData itself and require a silent console.

Unit tests can confirm py2pd writes the bytes it meant to write. Only PureData
can confirm those bytes describe a patch it will accept -- an out-of-range
connection index, for instance, serializes perfectly and is rejected at load
time with "connection failed".

Skipped when no ``pd`` binary is found. Set ``PD_BIN`` to point at one.
"""

import os

import pytest

from py2pd import Patcher, parse, to_builder
from py2pd.ast import serialize
from tests.gui_params import GUI_METHODS, kwargs_for
from tests.pd_runner import PD_BIN, SKIP_REASON, run_in_pd

pytestmark = pytest.mark.skipif(PD_BIN is None, reason=SKIP_REASON)


def assert_loads_cleanly(patch: Patcher, tmp_path, name: str) -> None:
    target = tmp_path / name
    patch.save(str(target))
    output = run_in_pd(str(target))
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
        for method in GUI_METHODS:
            getattr(p, method)()
        assert_loads_cleanly(p, tmp_path, "guis.pd")

    @pytest.mark.parametrize("method", GUI_METHODS)
    def test_every_gui_parameter(self, method, tmp_path):
        """Each GUI type with every parameter set, opened in PureData.

        Serializing correctly is not the same as writing a statement PureData
        accepts: a field that lands in the wrong slot still serializes.
        """
        p = Patcher()
        getattr(p, method)(**kwargs_for(method))
        assert_loads_cleanly(p, tmp_path, f"{method}.pd")

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

    def test_array_in_a_graph_canvas(self, tmp_path):
        p = Patcher()
        p.add_array("wavetable", 64)
        assert_loads_cleanly(p, tmp_path, "array.pd")

    def test_message_with_separators(self, tmp_path):
        """An escaped comma must stay one atom separator, not become two."""
        p = Patcher()
        p.add_msg("0, 1 10")
        p.add_msg("1; note 440 0.8")
        assert_loads_cleanly(p, tmp_path, "msgs.pd")

    def test_abstraction_resolves_against_a_real_file(self, tmp_path):
        """add_abstraction writes a bare object; PureData must find the file."""
        (tmp_path / "myabs.pd").write_text(
            "#N canvas 0 50 450 300 12;\n#X obj 25 25 inlet;\n#X obj 25 75 outlet;\n"
            "#X connect 0 0 1 0;\n",
            encoding="utf-8",
        )
        p = Patcher()
        p.add_abstraction("myabs", num_inlets=1, num_outlets=1)
        assert_loads_cleanly(p, tmp_path, "usesabs.pd")

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
        assert run_in_pd(str(target)) == ""

    def test_pd_authored_fixture_through_the_builder(self, tmp_path):
        source = os.path.join(os.path.dirname(__file__), "examples", "pd_authored.pd")
        with open(source, encoding="utf-8") as handle:
            ast = parse(handle.read())
        patch = to_builder(ast)
        assert_loads_cleanly(patch, tmp_path, "rebuilt.pd")
        # The struct and scalars must come back too, not merely load.
        assert str(patch).strip() == serialize(ast).strip()

    def test_generated_fixture_through_the_builder(self, tmp_path):
        """Double-escaped dollar arguments load without error but mean the wrong thing."""
        source = os.path.join(os.path.dirname(__file__), "examples", "pd_example.pd")
        with open(source, encoding="utf-8") as handle:
            original = handle.read()
        patch = to_builder(parse(original))
        assert_loads_cleanly(patch, tmp_path, "rebuilt2.pd")
        # Escapes must survive unchanged, which loading alone cannot verify.
        assert str(patch).count("\\$") == original.count("\\$")
