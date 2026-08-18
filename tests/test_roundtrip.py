"""Round-trip fidelity tests against PureData-authored input.

Every other parser test in this suite feeds the parser input that py2pd itself
would have written, which cannot detect a disagreement between py2pd and
PureData. The fixture used here (``tests/examples/pd_authored.pd``) was written
by PureData 0.55 itself -- a hand-written draft opened in Pd and saved back out,
so its formatting is Pd's canonical output, not py2pd's.

Each test below pins a specific defect that this fixture would have caught.
"""

from pathlib import Path
import warnings

import pytest

from py2pd import Patcher, parse, parse_file, to_builder
from py2pd.ast import (
    PdCoords,
    PdFloatAtom,
    PdObj,
    PdRaw,
    PdSubpatch,
    PdTgl,
    PdVsl,
    UnsupportedElementWarning,
    serialize,
)

FIXTURE = Path(__file__).parent / "examples" / "pd_authored.pd"


@pytest.fixture
def pd_source() -> str:
    return FIXTURE.read_text(encoding="utf-8")


class TestPdAuthoredRoundTrip:
    """The whole file must survive parse -> serialize unchanged, byte for byte."""

    def test_byte_identical_roundtrip(self, pd_source):
        assert serialize(parse(pd_source)).strip() == pd_source.strip()

    def test_roundtrip_is_idempotent(self, pd_source):
        once = serialize(parse(pd_source))
        twice = serialize(parse(once))
        assert once == twice

    def test_parse_file(self):
        patch = parse_file(str(FIXTURE))
        assert patch.canvas.width == 560
        assert patch.canvas.font_size == 12


class TestNewlineIsAnAtomSeparator:
    """PureData wraps long statements across lines with no continuation marker."""

    def test_wrapped_object_arguments(self):
        content = (
            "#N canvas 0 50 450 300 12;\n"
            "#X obj 60 150 route one two three four five six seven eight nine ten\n"
            "eleven twelve;\n"
        )
        obj = parse(content).elements[0]
        assert isinstance(obj, PdObj)
        assert obj.class_name == "route"
        assert obj.args == (
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        )

    def test_wrapped_gui_object_is_still_recognised(self):
        """A wrapped [tgl] has all 14 arguments and must not degrade to a plain PdObj."""
        content = (
            "#N canvas 0 50 450 300 12;\n"
            "#X obj 60 200 tgl 15 0 empty empty empty 17 7 0 10 #fcfcfc #000000 #000000\n"
            "0 1;\n"
        )
        elem = parse(content).elements[0]
        assert isinstance(elem, PdTgl)
        assert elem.default_value == 1

    def test_no_token_contains_a_newline(self, pd_source):
        for elem in parse(pd_source).elements:
            if isinstance(elem, PdObj):
                assert all("\n" not in arg for arg in elem.args)


class TestIemColors:
    """Pd >= 0.47 writes colours as hex strings; both forms must survive."""

    def test_hex_colors_preserved(self):
        line = "#X obj 57 55 bng 19 250 50 0 empty empty empty 17 7 0 10 #dfdfdf #000000 #000000;"
        content = f"#N canvas 0 50 450 300 12;\n{line}\n"
        assert serialize(parse(content)).strip().endswith(line)

    def test_legacy_integer_colors_preserved(self):
        line = "#X obj 57 55 bng 19 250 50 0 empty empty empty 17 7 0 10 -262144 -1 -1;"
        content = f"#N canvas 0 50 450 300 12;\n{line}\n"
        assert serialize(parse(content)).strip().endswith(line)

    def test_fixture_slider_keeps_its_colors(self, pd_source):
        sliders = [e for e in parse(pd_source).elements if isinstance(e, PdVsl)]
        assert len(sliders) == 1
        assert sliders[0].bg_color == "#0800fc"
        assert sliders[0].fg_color == "#fcfcfc"
        assert sliders[0].label_color == "#000000"


class TestGraphCanvas:
    """``#X restore <x> <y> graph;`` closes an array canvas and must parse."""

    def test_graph_restore_parses(self):
        content = (
            "#N canvas 0 50 450 300 12;\n"
            "#N canvas 0 50 450 250 (subpatch) 0;\n"
            "#X array arr 4 float 2;\n"
            "#X coords 0 1 4 -1 200 140 1;\n"
            "#X restore 250 200 graph;\n"
        )
        sub = parse(content).elements[0]
        assert isinstance(sub, PdSubpatch)
        assert sub.restore is not None
        assert sub.restore.is_graph
        assert serialize(parse(content)).strip() == content.strip()

    def test_fixture_contains_a_graph(self, pd_source):
        subs = [e for e in parse(pd_source).elements if isinstance(e, PdSubpatch)]
        assert [s.restore.is_graph for s in subs if s.restore] == [True, False]

    def test_builder_emits_graph_restore(self):
        inner = Patcher()
        inner.add_array("arr", 4)
        parent = Patcher()
        sub = parent.add_subpatch("arr", inner, is_graph=True, x_pos=10, y_pos=20)
        assert "#X restore 10 20 graph;" in str(sub)


class TestCoords:
    """``#X coords`` has 7 or 9 values, and hiding the name is gop == 2."""

    def test_seven_value_form_roundtrips(self):
        line = "#X coords 0 1 4 -1 200 140 1;"
        content = f"#N canvas 0 50 450 300 12;\n{line}\n"
        assert serialize(parse(content)).strip().endswith(line)

    def test_nine_value_form_roundtrips(self):
        line = "#X coords 0 -1 1 1 85 60 2 100 100;"
        content = f"#N canvas 0 50 450 300 12;\n{line}\n"
        assert serialize(parse(content)).strip().endswith(line)

    def test_margins_are_not_read_as_a_hide_flag(self):
        content = "#N canvas 0 50 450 300 12;\n#X coords 0 -1 1 1 85 60 2 100 100;\n"
        coords = parse(content).elements[0]
        assert isinstance(coords, PdCoords)
        assert coords.hide_name is True
        assert (coords.x_margin, coords.y_margin) == (100, 100)

    def test_hide_name_roundtrips_through_the_builder(self):
        inner = Patcher()
        inner.add("inlet")
        parent = Patcher()
        parent.add_subpatch("ctl", inner, graph_on_parent=True, hide_name=True)
        rebuilt = to_builder(parse(str(parent)))
        sub = rebuilt.nodes[0]
        assert sub.parameters["hide_name"] is True
        assert sub.parameters["graph_on_parent"] is True


class TestUnmodelledStatements:
    """Statements outside the modelled subset are preserved, never rewritten."""

    @pytest.mark.parametrize(
        "line",
        [
            "#X scalar point 40 50 12 \\;",
            "#A 0 0.5 0.25 0.125",
            "#X f 27",
            "#X listbox 644 353 15 0 0 0 - - - 0",
        ],
    )
    def test_statement_survives_roundtrip(self, line):
        content = f"#N canvas 0 50 450 300 12;\n{line};\n"
        assert serialize(parse(content)).strip() == content.strip()

    def test_struct_is_written_above_the_canvas_line(self):
        content = "#N struct point float x float y;\n#N canvas 0 50 450 300 12;\n#X obj 1 1 f;\n"
        patch = parse(content)
        assert len(patch.preamble) == 1
        assert serialize(patch).strip() == content.strip()

    def test_unknown_statement_is_not_turned_into_an_object(self):
        content = "#N canvas 0 50 450 300 12;\n#X scalar point 40 50 12;\n"
        elem = parse(content).elements[0]
        assert isinstance(elem, PdRaw)
        assert not isinstance(elem, PdObj)

    def test_scalar_occupies_a_connect_index_but_array_data_does_not(self):
        """Pd counts a scalar as an object; #A is not one. Indices must not shift."""
        content = (
            "#N canvas 0 50 450 300 12;\n"
            "#X obj 10 10 osc~ 440;\n"
            "#X scalar point 40 50 12;\n"
            "#X obj 10 60 dac~;\n"
            "#X connect 0 0 2 0;\n"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UnsupportedElementWarning)
            patch = to_builder(parse(content))
        assert len(patch.connections) == 1
        conn = patch.connections[0]
        assert (patch.nodes[conn.source], patch.nodes[conn.sink]) == (
            patch.nodes[0],
            patch.nodes[1],
        )

    def test_to_builder_warns_rather_than_dropping_silently(self):
        content = "#N canvas 0 50 450 300 12;\n#X scalar point 40 50 12;\n"
        with pytest.warns(UnsupportedElementWarning):
            to_builder(parse(content))


class TestDeclare:
    def test_stdpath_value_is_preserved(self):
        line = "#X declare -stdpath ./"
        content = f"#N canvas 0 50 450 300 12;\n{line};\n"
        assert serialize(parse(content)).strip().endswith(line + ";")

    def test_declare_still_parses_paths_and_libs(self):
        content = "#N canvas 0 50 450 300 12;\n#X declare -path extra -lib foo -stdpath ./;\n"
        declare = parse(content).elements[0]
        assert declare.paths == ("extra",)
        assert declare.libs == ("foo",)
        assert declare.stdpath is True


class TestAtomBoxes:
    def test_font_size_field_is_preserved(self):
        line = "#X floatatom 225 125 0 0 0 0 - - - 0;"
        content = f"#N canvas 0 50 450 300 12;\n{line}\n"
        assert serialize(parse(content)).strip().endswith(line)

    def test_absent_font_size_field_is_not_invented(self):
        line = "#X floatatom 225 125 0 0 0 0 - - -;"
        content = f"#N canvas 0 50 450 300 12;\n{line}\n"
        parsed = parse(content).elements[0]
        assert isinstance(parsed, PdFloatAtom)
        assert parsed.font_size is None
        assert serialize(parse(content)).strip().endswith(line)

    def test_integral_limits_are_not_rewritten_as_floats(self):
        line = "#X floatatom 142 146 4 0 1000 0 - - - 0;"
        content = f"#N canvas 0 50 450 300 12;\n{line}\n"
        assert serialize(parse(content)).strip().endswith(line)


class TestBuilderBridgeDoesNotDoubleEscape:
    """``to_builder()`` receives text that is already escaped."""

    def test_message_escapes_survive(self):
        line = "#X msg 25 200 0 \\, 1 \\$2 \\, \\$1 \\$3 \\$2;"
        content = f"#N canvas 0 50 1000 600 10;\n{line}\n"
        assert str(to_builder(parse(content))).strip().endswith(line)

    def test_semicolon_escapes_survive(self):
        line = "#X msg 25 100 1 \\; note 440 0.8 80;"
        content = f"#N canvas 0 50 1000 600 10;\n{line}\n"
        assert str(to_builder(parse(content))).strip().endswith(line)

    def test_object_text_escapes_survive(self):
        line = "#X obj 238 746 tabread4~ \\$0-tab;"
        content = f"#N canvas 0 50 1000 600 10;\n{line}\n"
        assert str(to_builder(parse(content))).strip().endswith(line)

    def test_builder_roundtrip_of_the_legacy_fixture(self):
        """The generated-patch fixture must survive AST -> builder -> text."""
        source = (Path(__file__).parent / "examples" / "pd_example.pd").read_text()
        rebuilt = str(to_builder(parse(source)))
        # Escaped separators must come back unchanged, not doubled.
        assert "\\\\" not in rebuilt
        assert rebuilt.count("\\;") == source.count("\\;")
        assert rebuilt.count("\\$") == source.count("\\$")

    def test_escaped_flag_is_opt_in(self):
        """Ordinary builder use still escapes, so display text keeps working."""
        patch = Patcher()
        patch.add_msg("0 , 1")
        assert "\\," in str(patch)


class TestParsingDoesNotEnforceTheObjectRegistry:
    """A patch PureData accepts must be representable, whatever the registry knows."""

    def test_out_of_range_inlet_warns_instead_of_raising(self):
        from py2pd.api import PdConnectionWarning

        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 10 f;\n"
            "#X obj 10 60 print;\n"
            "#X connect 0 0 1 4;\n"
        )
        with pytest.warns(PdConnectionWarning):
            patch = to_builder(parse(content))
        assert len(patch.connections) == 1
        assert patch.connections[0].inlet_index == 4

    def test_authoring_still_raises_by_default(self):
        from py2pd.api import PdConnectionError

        patch = Patcher()
        osc = patch.add("osc~ 440")
        printer = patch.add("print")
        with pytest.raises(PdConnectionError):
            patch.link(osc, printer, inlet=3)

    def test_argument_dependent_arity_accepts_real_patches(self):
        """[dac~ 1 2 3 4] has four inlets; a fixed table said two."""
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 10 osc~ 440;\n"
            "#X obj 10 60 dac~ 1 2 3 4;\n"
            "#X connect 0 0 1 3;\n"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # no warning may be raised
            patch = to_builder(parse(content))
        assert len(patch.connections) == 1


class TestPopTerminator:
    """Older patches close a canvas with a bare ``#X pop;``."""

    def test_pop_closes_the_canvas(self):
        content = (
            "#N canvas 0 50 450 300 12;\n"
            "#N canvas 0 50 450 250 sub 0;\n"
            "#X obj 10 10 f;\n"
            "#X pop;\n"
            "#X obj 20 20 osc~ 440;\n"
        )
        elements = parse(content).elements
        # Ignoring the pop left the canvas open, so the osc~ landed inside it.
        assert [type(e).__name__ for e in elements] == ["PdSubpatch", "PdObj"]
        assert serialize(parse(content)).strip() == content.strip()

    def test_unmatched_pop_is_an_error(self):
        with pytest.raises(Exception):
            parse("#N canvas 0 50 450 300 12;\n#X pop;\n#X pop;\n")
