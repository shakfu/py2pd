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
from py2pd.api import Raw, Subpatch
from py2pd.ast import (
    PdArray,
    PdCoords,
    PdFloatAtom,
    PdMsg,
    PdObj,
    PdRaw,
    PdSubpatch,
    PdText,
    PdTgl,
    PdVsl,
    from_builder,
    serialize,
)
from tests.gui_params import (
    GUI_METHODS,
    NON_GUI_METHODS,
    PARAM_VALUES,
    all_add_methods,
    ast_node_for,
    gui_parameters,
    kwargs_for,
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
            "#X f 27;\n"
            "#X obj 10 60 dac~;\n"
            "#X connect 0 0 2 0;\n"
        )
        patch = to_builder(parse(content))

        # Four statements, four nodes: nothing was dropped on the way in.
        assert len(patch.nodes) == 4
        conn = patch.connections[0]
        # The scalar took index 1, so dac~ is 2. "#X f" took none, so it is
        # still 2 and not 3.
        assert (conn.source, conn.sink) == (0, 2)
        assert serialize(from_builder(patch)).strip() == content.strip()

    def test_to_builder_carries_what_it_cannot_model(self):
        content = "#N canvas 0 50 450 300 12;\n#X scalar point 40 50 12;\n"
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            patch = to_builder(parse(content))
        assert serialize(from_builder(patch)).strip() == content.strip()


class TestBuilderRoundTripIsLossless:
    """parse -> to_builder -> from_builder -> serialize must change nothing.

    One fixture carrying every statement the builder does not model, and every
    field the bridge used to hardcode. The corpus test proves this at scale but
    needs a PureData install; this one runs everywhere.
    """

    CONTENT = (
        "#N struct kitchen float x float y symbol label;\n"
        "#N canvas 12 34 640 480 12;\n"
        "#X declare -path ./externals -lib mylib;\n"
        "#X obj 20 20 osc~ 440;\n"
        "#X floatatom 20 60 5 0 127 1 freq - - 12;\n"
        "#X symbolatom 20 90 10 0 0 2 name rcv snd 9;\n"
        "#X scalar kitchen 40 50 hello;\n"
        "#A 0 0.5 0.25;\n"
        "#X f 27;\n"
        "#N canvas 101 202 305 406 guts 1;\n"
        "#X obj 10 10 inlet~;\n"
        "#X obj 10 40 outlet~;\n"
        "#X restore 20 130 pd guts;\n"
        "#N canvas 0 0 450 250 (subpatch) 0;\n"
        "#X array wave 64 float 2;\n"
        "#A 0 1 0.5;\n"
        "#X coords 0 1 64 -1 200 140 1;\n"
        "#X xlabel -0.2 0 1 2;\n"
        "#X restore 300 20 graph;\n"
        "#X obj 20 170 dac~;\n"
        # A trailing escaped space is an atom; splitting the text on whitespace
        # would swallow it and rewrite the object.
        "#X obj 20 200 drawnumber dog 0 -15 900 dog\\ =\\ ;\n"
        # PureData writes kinds beyond "pd" and "graph"; "page" is a real one.
        "#N canvas 47 74 450 300 (subpatch) 0;\n"
        "#X restore 260 200 page;\n"
        "#X connect 0 0 6 0;\n"
        "#X connect 3 0 6 0;\n"
        "#X coords 0 0 1 1 85 60 0;\n"
    )

    def test_the_fixture_round_trips_through_the_ast(self):
        """Guards the test itself: a builder difference must not be the parser's."""
        assert serialize(parse(self.CONTENT)).strip() == self.CONTENT.strip()

    def test_bridge_round_trip_is_byte_identical(self):
        patch = to_builder(parse(self.CONTENT))
        assert serialize(from_builder(patch)).strip() == self.CONTENT.strip()

    def test_builder_writes_the_same_bytes(self):
        """str(patch) and the AST writer must not diverge."""
        assert str(to_builder(parse(self.CONTENT))).strip() == self.CONTENT.strip()

    def test_nothing_is_dropped_on_the_way_in(self):
        patch = to_builder(parse(self.CONTENT))
        assert patch.preamble == ["#N struct kitchen float x float y symbol label"]
        assert len(patch.nodes) == 13

    def test_connect_indices_count_objects_not_nodes(self):
        """#X declare, #A and #X f sit in the node list without taking an index."""
        patch = to_builder(parse(self.CONTENT))
        # osc~ is node 1 and dac~ node 9, but PureData numbers them 0 and 6.
        assert [(c.source, c.sink) for c in patch.connections] == [(0, 6), (3, 6)]

    def test_a_scalar_can_still_be_connected(self):
        """The scalar is index 3; a connection to it must survive the trip."""
        patch = to_builder(parse(self.CONTENT))
        assert patch.connections[1].source == 3
        assert isinstance(patch.nodes[4], Raw)
        assert patch.nodes[4].occupies_connect_index

    def test_subpatch_keeps_its_canvas_line(self):
        """A subpatch canvas carries a name and an open-on-load flag, not a font size."""
        node = [n for n in to_builder(parse(self.CONTENT)).nodes if isinstance(n, Subpatch)][0]
        p = node.parameters
        assert (p["canvas_x"], p["canvas_y"]) == (101, 202)
        assert (p["canvas_name"], p["open_on_load"]) == ("guts", 1)
        assert (node.canvas_width, node.canvas_height) == (305, 406)


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


class TestBuilderOutputRoundTrips:
    """What the builder writes, the parser must read back unchanged.

    Nothing else covers this direction. The builder's own tests assert on
    substrings, so they passed while ``#X floatatom`` was written with the
    label_pos field missing and the limits in the wrong order.
    """

    @staticmethod
    def assert_stable(patch: Patcher) -> None:
        written = str(patch)
        assert serialize(parse(written)).strip() == written.strip()

    def test_float_atom(self):
        p = Patcher()
        p.add_float(width=8, lower_limit=0, upper_limit=127, label_pos=2, label="freq")
        self.assert_stable(p)

    def test_symbol_atom(self):
        p = Patcher()
        p.add_symbol(width=15, label_pos=1, label="name")
        self.assert_stable(p)

    def test_message_with_comma(self):
        p = Patcher()
        p.add_msg("0, 1 10")
        self.assert_stable(p)

    def test_message_with_semicolon(self):
        p = Patcher()
        p.add_msg("1; note 440 0.8")
        self.assert_stable(p)

    def test_every_gui_type_at_defaults(self):
        p = Patcher()
        for method in GUI_METHODS:
            getattr(p, method)()
        self.assert_stable(p)

    @pytest.mark.parametrize("method", GUI_METHODS)
    def test_every_gui_parameter(self, method):
        """Each GUI type with every parameter set to a distinctive value.

        Defaults alone are not enough: two adjacent fields that both default to
        0 round-trip whichever order they are written in.
        """
        p = Patcher()
        getattr(p, method)(**kwargs_for(method))
        self.assert_stable(p)

    @pytest.mark.parametrize("method", GUI_METHODS)
    def test_every_gui_parameter_survives_the_writer(self, method):
        """Every parameter must parse back as the value it was given.

        The byte round-trip above cannot see this. Two fields of the same type
        written in the wrong order serialize identically, so the writer and the
        parser agree with each other while both disagree with PureData. Only
        checking the parsed field values catches a swap or an omitted field.
        """
        p = Patcher()
        requested = kwargs_for(method)
        getattr(p, method)(**requested)
        node = parse(str(p)).elements[0]
        assert isinstance(node, ast_node_for(method))
        for name, value in requested.items():
            assert getattr(node, name) == value, f"{method}: {name} came back wrong"

    def test_every_gui_parameter_has_a_value(self):
        """A new GUI parameter must be added to PARAM_VALUES to be covered."""
        for method in GUI_METHODS:
            for name in gui_parameters(method):
                assert name in PARAM_VALUES, f"{method}({name}=...) is not covered"

    def test_signal_chain_with_subpatch(self):
        inner = Patcher()
        inner.link(inner.add("inlet~"), inner.add("outlet~"))
        p = Patcher()
        p.add_subpatch("passthrough", inner)
        p.add_comment("gain stage; adjust, carefully")
        self.assert_stable(p)


class TestBuilderStructureSurvivesTheWriter:
    """The non-GUI builder methods, checked the same way as the GUI matrix.

    These write shapes rather than a flat field list -- a subpatch is a nested
    canvas plus a restore line, an array is a single statement -- so each is
    asserted explicitly instead of through a parameter table. The property is
    the same: what the parser reads back must be what the caller asked for.
    """

    @staticmethod
    def only_element(patch: Patcher):
        elements = parse(str(patch)).elements
        assert len(elements) == 1, f"expected one element, got {elements}"
        return elements[0]

    def test_message_content(self):
        p = Patcher()
        p.add_msg("0, 1 10")
        node = self.only_element(p)
        assert isinstance(node, PdMsg)
        # One space after the separator, and the comma is escaped, not dropped.
        assert node.content == r"0 \, 1 10"

    def test_message_already_escaped_is_not_escaped_again(self):
        p = Patcher()
        p.add_msg(r"0 \, 1 \$1", escaped=True)
        assert self.only_element(p).content == r"0 \, 1 \$1"

    def test_comment_content(self):
        p = Patcher()
        p.add_comment("gain stage; adjust, carefully")
        node = self.only_element(p)
        assert isinstance(node, PdText)
        assert node.content == r"gain stage \; adjust \, carefully"

    def test_comment_already_escaped_is_not_escaped_again(self):
        p = Patcher()
        p.add_comment(r"a \; b", escaped=True)
        assert self.only_element(p).content == r"a \; b"

    def test_array_name_and_size(self):
        p = Patcher()
        p.add_array("wavetable", 64)
        node = self.only_element(p)
        assert isinstance(node, PdArray)
        assert (node.name, node.size) == ("wavetable", 64)

    def test_abstraction_writes_its_name_as_the_object(self):
        p = Patcher()
        node = p.add_abstraction("myabs", num_inlets=2, num_outlets=3)
        parsed = self.only_element(p)
        assert isinstance(parsed, PdObj)
        assert parsed.class_name == "myabs"
        assert parsed.args == ()
        # Arity is builder-side metadata; PureData infers it from the file.
        assert (node.num_inlets, node.num_outlets) == (2, 3)

    def test_subpatch_canvas_and_restore(self):
        inner = Patcher()
        inner.link(inner.add("inlet~"), inner.add("outlet~"))
        p = Patcher()
        p.add_subpatch("voice", inner, canvas_width=321, canvas_height=177)
        node = self.only_element(p)
        assert isinstance(node, PdSubpatch)
        assert (node.canvas.width, node.canvas.height) == (321, 177)
        assert (node.restore.name, node.restore.kind) == ("voice", "pd")
        objects = [e for e in node.elements if isinstance(e, PdObj)]
        assert [o.class_name for o in objects] == ["inlet~", "outlet~"]

    def test_subpatch_graph_on_parent_coords(self):
        inner = Patcher()
        inner.add_hslider()
        p = Patcher()
        p.add_subpatch(
            "controls",
            inner,
            graph_on_parent=True,
            hide_name=True,
            gop_width=151,
            gop_height=63,
            gop_rect=(0, 1, 1, 0),
            gop_margins=(7, 9),
        )
        node = self.only_element(p)
        coords = [e for e in node.elements if isinstance(e, PdCoords)]
        assert len(coords) == 1, "graph_on_parent must write exactly one #X coords"
        c = coords[0]
        assert (c.x_from, c.y_from, c.x_to, c.y_to) == (0, 1, 1, 0)
        assert (c.width, c.height) == (151, 63)
        # hide_name is encoded in the flag itself: 2 rather than 1.
        assert c.hide_name is True
        assert (c.x_margin, c.y_margin) == (7, 9)

    def test_subpatch_without_graph_on_parent_writes_no_coords(self):
        inner = Patcher()
        inner.add_hslider()
        p = Patcher()
        p.add_subpatch("controls", inner)
        node = self.only_element(p)
        assert not [e for e in node.elements if isinstance(e, PdCoords)]

    def test_graph_canvas_restore_kind(self):
        inner = Patcher()
        inner.add_array("wt", 32)
        p = Patcher()
        p.add_subpatch("wt", inner, is_graph=True)
        node = self.only_element(p)
        assert (node.restore.kind, node.restore.name) == ("graph", "")

    def test_every_builder_method_is_covered_by_a_matrix(self):
        """A new add_* method must join one of the two lists to be tested."""
        uncovered = set(all_add_methods()) - set(GUI_METHODS) - set(NON_GUI_METHODS)
        assert not uncovered, f"add_* methods with no writer test: {sorted(uncovered)}"
