"""Tests for py2pd.ast module."""

import os
import tempfile

import pytest

from py2pd import (
    ParseError,
    Patcher,
    from_builder,
    parse,
    parse_file,
    serialize,
    serialize_to_file,
    to_builder,
)
from py2pd.api import Abstraction, Comment, Subpatch, Symbol
from py2pd.ast import (
    CanvasProperties,
    PdArray,
    PdCnv,
    PdConnect,
    PdCoords,
    PdFloatAtom,
    PdHradio,
    PdHsl,
    PdMsg,
    PdNbx,
    PdObj,
    PdPatch,
    PdRestore,
    PdSubpatch,
    PdSymbolAtom,
    PdText,
    PdVradio,
    PdVsl,
    PdVu,
    Position,
    _preprocess,
    _split_statements,
    find_objects,
    rename_sends_receives,
    transform,
)


class TestPosition:
    """Tests for Position class."""

    def test_position_creation(self):
        pos = Position(100, 200)
        assert pos.x == 100
        assert pos.y == 200

    def test_position_str(self):
        pos = Position(100, 200)
        assert str(pos) == "100 200"

    def test_position_immutable(self):
        pos = Position(100, 200)
        with pytest.raises(AttributeError):
            pos.x = 300


class TestCanvasProperties:
    """Tests for CanvasProperties class."""

    def test_default_canvas(self):
        canvas = CanvasProperties()
        assert canvas.x == 0
        assert canvas.y == 50
        assert canvas.width == 1000
        assert canvas.height == 600
        assert canvas.font_size == 10

    def test_canvas_str_main(self):
        canvas = CanvasProperties(0, 50, 1000, 600, 10)
        assert str(canvas) == "0 50 1000 600 10"

    def test_canvas_str_subpatch(self):
        canvas = CanvasProperties(0, 0, 300, 200, 10, "mysubpatch", 0)
        assert "mysubpatch" in str(canvas)


class TestPdObj:
    """Tests for PdObj class."""

    def test_simple_obj(self):
        obj = PdObj(Position(100, 200), "osc~")
        assert obj.class_name == "osc~"
        assert obj.args == ()
        assert obj.text == "osc~"

    def test_obj_with_args(self):
        obj = PdObj(Position(100, 200), "osc~", ("440",))
        assert obj.class_name == "osc~"
        assert obj.args == ("440",)
        assert obj.text == "osc~ 440"

    def test_obj_str(self):
        obj = PdObj(Position(100, 200), "osc~", ("440",))
        assert str(obj) == "#X obj 100 200 osc~ 440;"


class TestPdMsg:
    """Tests for PdMsg class."""

    def test_msg_creation(self):
        msg = PdMsg(Position(100, 200), "bang")
        assert msg.content == "bang"

    def test_msg_str(self):
        msg = PdMsg(Position(100, 200), "bang")
        assert str(msg) == "#X msg 100 200 bang;"


class TestPdFloatAtom:
    """Tests for PdFloatAtom class."""

    def test_floatatom_defaults(self):
        fa = PdFloatAtom(Position(100, 200))
        assert fa.width == 5
        assert fa.lower_limit == 0
        assert fa.upper_limit == 0

    def test_floatatom_str(self):
        fa = PdFloatAtom(Position(100, 200), 5, 0, 127)
        result = str(fa)
        assert "#X floatatom 100 200" in result


class TestPdArray:
    """Tests for PdArray class."""

    def test_array_creation(self):
        arr = PdArray("myarray", 1024)
        assert arr.name == "myarray"
        assert arr.size == 1024
        assert arr.dtype == "float"

    def test_array_str(self):
        arr = PdArray("myarray", 1024, "float", 0)
        assert str(arr) == "#X array myarray 1024 float 0;"


class TestPdConnect:
    """Tests for PdConnect class."""

    def test_connect_creation(self):
        conn = PdConnect(0, 0, 1, 0)
        assert conn.source_id == 0
        assert conn.outlet_id == 0
        assert conn.sink_id == 1
        assert conn.inlet_id == 0

    def test_connect_str(self):
        conn = PdConnect(0, 0, 1, 0)
        assert str(conn) == "#X connect 0 0 1 0;"


class TestPdPatch:
    """Tests for PdPatch class."""

    def test_empty_patch(self):
        patch = PdPatch(CanvasProperties())
        assert patch.elements == []

    def test_patch_with_elements(self):
        elements = [
            PdObj(Position(25, 25), "osc~", ("440",)),
            PdObj(Position(25, 50), "dac~"),
            PdConnect(0, 0, 1, 0),
        ]
        patch = PdPatch(CanvasProperties(), elements)
        assert len(patch.elements) == 3

    def test_get_objects(self):
        elements = [
            PdObj(Position(25, 25), "osc~"),
            PdMsg(Position(25, 50), "bang"),
            PdConnect(0, 0, 1, 0),
        ]
        patch = PdPatch(CanvasProperties(), elements)
        objects = patch.get_objects()
        assert len(objects) == 2  # obj and msg, not connect

    def test_get_connections(self):
        elements = [
            PdObj(Position(25, 25), "osc~"),
            PdObj(Position(25, 50), "dac~"),
            PdConnect(0, 0, 1, 0),
            PdConnect(0, 0, 1, 1),
        ]
        patch = PdPatch(CanvasProperties(), elements)
        connections = patch.get_connections()
        assert len(connections) == 2


class TestParser:
    """Tests for parse function."""

    def test_parse_simple_patch(self):
        content = """#N canvas 0 50 450 300 10;
#X obj 50 50 osc~ 440;
#X obj 50 100 dac~;
#X connect 0 0 1 0;
#X connect 0 0 1 1;"""

        patch = parse(content)
        assert len(patch.elements) == 4
        assert isinstance(patch.elements[0], PdObj)
        assert isinstance(patch.elements[1], PdObj)
        assert isinstance(patch.elements[2], PdConnect)

    def test_parse_message(self):
        content = """#N canvas 0 50 450 300 10;
#X msg 50 50 bang;"""

        patch = parse(content)
        assert len(patch.elements) == 1
        assert isinstance(patch.elements[0], PdMsg)
        assert patch.elements[0].content == "bang"

    def test_parse_floatatom(self):
        content = """#N canvas 0 50 450 300 10;
#X floatatom 50 50 5 0 127 0 - - -;"""

        patch = parse(content)
        assert len(patch.elements) == 1
        assert isinstance(patch.elements[0], PdFloatAtom)

    def test_parse_array(self):
        content = """#N canvas 0 50 450 300 10;
#X array myarray 1024 float 0;"""

        patch = parse(content)
        assert len(patch.elements) == 1
        assert isinstance(patch.elements[0], PdArray)
        assert patch.elements[0].name == "myarray"

    def test_parse_text(self):
        content = """#N canvas 0 50 450 300 10;
#X text 50 50 This is a comment;"""

        patch = parse(content)
        assert len(patch.elements) == 1
        assert isinstance(patch.elements[0], PdText)

    def test_parse_subpatch(self):
        content = """#N canvas 0 50 450 300 10;
#N canvas 0 0 300 200 mysubpatch 0;
#X obj 50 50 inlet;
#X obj 50 100 outlet;
#X restore 100 100 pd mysubpatch;"""

        patch = parse(content)
        assert len(patch.elements) == 1
        assert isinstance(patch.elements[0], PdSubpatch)
        subpatch = patch.elements[0]
        assert len(subpatch.elements) == 2
        assert subpatch.restore.name == "mysubpatch"

    def test_parse_numeric_subpatch_name(self):
        content = """#N canvas 0 50 450 300 10;
#N canvas 0 0 300 200 42 0;
#X obj 50 50 inlet;
#X restore 100 100 pd 42;"""
        patch = parse(content)
        assert len(patch.elements) == 1
        assert isinstance(patch.elements[0], PdSubpatch)
        assert patch.elements[0].canvas.name == "42"
        assert patch.elements[0].restore.name == "42"

    def test_parse_empty_raises(self):
        with pytest.raises(ParseError):
            parse("")

    def test_parse_no_canvas_raises(self):
        with pytest.raises(ParseError):
            parse("#X obj 0 0 test;")


class TestSerializer:
    """Tests for serialize function."""

    def test_serialize_simple(self):
        elements = [
            PdObj(Position(50, 50), "osc~", ("440",)),
            PdObj(Position(50, 100), "dac~"),
            PdConnect(0, 0, 1, 0),
        ]
        patch = PdPatch(CanvasProperties(), elements)
        result = serialize(patch)

        assert "#N canvas" in result
        assert "#X obj 50 50 osc~ 440;" in result
        assert "#X obj 50 100 dac~;" in result
        assert "#X connect 0 0 1 0;" in result

    def test_serialize_subpatch(self):
        inner = [
            PdObj(Position(50, 50), "inlet"),
            PdObj(Position(50, 100), "outlet"),
        ]
        subpatch = PdSubpatch(
            CanvasProperties(0, 0, 300, 200, 10, "mysub", 0),
            inner,
            PdRestore(Position(100, 100), "mysub"),
        )
        patch = PdPatch(CanvasProperties(), [subpatch])
        result = serialize(patch)

        assert "pd mysub" in result
        assert "inlet" in result
        assert "outlet" in result


class TestRoundTrip:
    """Tests for round-trip conversion."""

    def test_roundtrip_simple(self):
        original = """#N canvas 0 50 1000 600 10;
#X obj 50 50 osc~ 440;
#X obj 50 100 dac~;
#X connect 0 0 1 0;"""

        # Parse
        ast = parse(original)
        # Serialize
        result = serialize(ast)
        # Parse again
        ast2 = parse(result)

        # Check structure preserved
        assert len(ast2.elements) == len(ast.elements)
        assert isinstance(ast2.elements[0], PdObj)
        assert ast2.elements[0].class_name == "osc~"

    def test_roundtrip_with_message(self):
        original = """#N canvas 0 50 1000 600 10;
#X msg 50 50 bang;
#X obj 50 100 print;
#X connect 0 0 1 0;"""

        ast = parse(original)
        result = serialize(ast)
        ast2 = parse(result)

        assert isinstance(ast2.elements[0], PdMsg)
        assert ast2.elements[0].content == "bang"

    def test_roundtrip_with_subpatch(self):
        original = """#N canvas 0 50 1000 600 10;
#N canvas 0 0 300 200 mysubpatch 0;
#X obj 50 50 inlet;
#X obj 50 100 outlet;
#X restore 100 100 pd mysubpatch;
#X obj 50 50 osc~ 440;
#X connect 1 0 0 0;"""

        ast = parse(original)
        result = serialize(ast)
        ast2 = parse(result)

        # Check subpatch preserved
        subpatches = [e for e in ast2.elements if isinstance(e, PdSubpatch)]
        assert len(subpatches) == 1


class TestFileIO:
    """Tests for file I/O functions."""

    def test_parse_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pd", delete=False) as f:
            f.write("#N canvas 0 50 1000 600 10;\n")
            f.write("#X obj 50 50 osc~ 440;\n")
            filepath = f.name

        try:
            ast = parse_file(filepath)
            assert len(ast.elements) == 1
            assert isinstance(ast.elements[0], PdObj)
        finally:
            os.unlink(filepath)

    def test_serialize_to_file(self):
        elements = [PdObj(Position(50, 50), "osc~", ("440",))]
        patch = PdPatch(CanvasProperties(), elements)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pd", delete=False) as f:
            filepath = f.name

        try:
            serialize_to_file(patch, filepath)
            with open(filepath, "r") as f:
                content = f.read()
            assert "#X obj 50 50 osc~ 440;" in content
        finally:
            os.unlink(filepath)


class TestBridgeFromBuilder:
    """Tests for from_builder function."""

    def test_from_builder_simple(self):
        patch = Patcher()
        patch.add("osc~ 440", x_pos=50, y_pos=50)
        patch.add("dac~", x_pos=50, y_pos=100)

        ast = from_builder(patch)
        assert len(ast.get_objects()) == 2
        assert isinstance(ast.elements[0], PdObj)

    def test_from_builder_with_connections(self):
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc, dac)

        ast = from_builder(patch)
        connections = ast.get_connections()
        assert len(connections) == 1

    def test_from_builder_with_msg(self):
        patch = Patcher()
        patch.add_msg("bang")

        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdMsg)

    def test_from_builder_with_array(self):
        patch = Patcher()
        patch.add_array("myarray", 1024)

        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdArray)

    def test_from_builder_with_subpatch(self):
        inner = Patcher()
        inner.add("inlet")
        inner.add("outlet")

        patch = Patcher()
        patch.add_subpatch("mysub", inner)

        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdSubpatch)

    def test_from_builder_with_bang(self):
        from py2pd.api import Bang as ApiBang

        patch = Patcher()
        patch.add_bang(size=20, send="s1", receive="r1")
        ast = from_builder(patch)
        from py2pd.ast import PdBng

        assert isinstance(ast.elements[0], PdBng)
        assert ast.elements[0].size == 20
        assert ast.elements[0].send == "s1"
        assert ast.elements[0].receive == "r1"

    def test_from_builder_with_toggle(self):
        patch = Patcher()
        patch.add_toggle(size=25, default_value=5)
        ast = from_builder(patch)
        from py2pd.ast import PdTgl

        assert isinstance(ast.elements[0], PdTgl)
        assert ast.elements[0].size == 25
        assert ast.elements[0].default_value == 5

    def test_from_builder_with_symbol(self):
        patch = Patcher()
        patch.add_symbol(width=15)
        ast = from_builder(patch)
        from py2pd.ast import PdSymbolAtom

        assert isinstance(ast.elements[0], PdSymbolAtom)
        assert ast.elements[0].width == 15

    def test_from_builder_with_numberbox(self):
        patch = Patcher()
        patch.add_numberbox(width=8, min_val=0, max_val=100)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdNbx)
        assert ast.elements[0].width == 8
        assert ast.elements[0].min_val == 0
        assert ast.elements[0].max_val == 100

    def test_from_builder_with_vslider(self):
        patch = Patcher()
        patch.add_vslider(width=20, height=150)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdVsl)
        assert ast.elements[0].width == 20
        assert ast.elements[0].height == 150

    def test_from_builder_with_hslider(self):
        patch = Patcher()
        patch.add_hslider(width=200, height=20)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdHsl)
        assert ast.elements[0].width == 200
        assert ast.elements[0].height == 20

    def test_from_builder_with_vradio(self):
        patch = Patcher()
        patch.add_vradio(number=4)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdVradio)
        assert ast.elements[0].number == 4

    def test_from_builder_with_hradio(self):
        patch = Patcher()
        patch.add_hradio(number=6)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdHradio)
        assert ast.elements[0].number == 6

    def test_from_builder_with_canvas(self):
        patch = Patcher()
        patch.add_canvas(width=200, height=100)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdCnv)
        assert ast.elements[0].width == 200
        assert ast.elements[0].height == 100

    def test_from_builder_with_vu(self):
        patch = Patcher()
        patch.add_vu(width=20, height=150)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdVu)
        assert ast.elements[0].width == 20
        assert ast.elements[0].height == 150


class TestBridgeToBuilder:
    """Tests for to_builder function."""

    def test_to_builder_simple(self):
        elements = [
            PdObj(Position(50, 50), "osc~", ("440",)),
            PdObj(Position(50, 100), "dac~"),
        ]
        ast = PdPatch(CanvasProperties(), elements)

        patch = to_builder(ast)
        assert len(patch.nodes) == 2

    def test_to_builder_with_connections(self):
        elements = [
            PdObj(Position(50, 50), "osc~", ("440",)),
            PdObj(Position(50, 100), "dac~"),
            PdConnect(0, 0, 1, 0),
        ]
        ast = PdPatch(CanvasProperties(), elements)

        patch = to_builder(ast)
        assert len(patch.connections) == 1

    def test_to_builder_roundtrip(self):
        # Create with builder
        original = Patcher()
        original.add("osc~ 440", x_pos=50, y_pos=50)
        original.add("dac~", x_pos=50, y_pos=100)

        # Convert to AST and back
        ast = from_builder(original)
        restored = to_builder(ast)

        assert len(restored.nodes) == len(original.nodes)

    def test_to_builder_with_bng(self):
        from py2pd.api import Bang as ApiBang
        from py2pd.ast import PdBng

        bng = PdBng(Position(10, 20), size=25, hold=300, send="s1")
        ast = PdPatch(CanvasProperties(), [bng])
        patch = to_builder(ast)
        assert len(patch.nodes) == 1
        node = patch.nodes[0]
        assert isinstance(node, ApiBang)
        assert node.parameters["size"] == 25
        assert node.parameters["hold"] == 300
        assert node.parameters["send"] == "s1"

    def test_to_builder_with_tgl(self):
        from py2pd.api import Toggle as ApiToggle
        from py2pd.ast import PdTgl

        tgl = PdTgl(Position(30, 40), size=20, default_value=5)
        ast = PdPatch(CanvasProperties(), [tgl])
        patch = to_builder(ast)
        assert len(patch.nodes) == 1
        node = patch.nodes[0]
        assert isinstance(node, ApiToggle)
        assert node.parameters["size"] == 20
        assert node.parameters["default_value"] == 5

    def test_bng_roundtrip(self):
        from py2pd.api import Bang as ApiBang
        from py2pd.ast import PdBng

        patch = Patcher()
        patch.add_bang(size=30, send="test_send")
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdBng)
        assert ast.elements[0].size == 30
        assert ast.elements[0].send == "test_send"
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, ApiBang)
        assert node.parameters["size"] == 30
        assert node.parameters["send"] == "test_send"

    def test_tgl_roundtrip(self):
        from py2pd.api import Toggle as ApiToggle
        from py2pd.ast import PdTgl

        patch = Patcher()
        patch.add_toggle(size=20, default_value=10)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdTgl)
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, ApiToggle)
        assert node.parameters["size"] == 20
        assert node.parameters["default_value"] == 10

    def test_to_builder_symbolatom(self):
        sa = PdSymbolAtom(
            Position(10, 20), width=15, lower_limit=0, upper_limit=0,
            label_pos=1, label="lbl", receive="r1", send="s1",
        )
        ast = PdPatch(CanvasProperties(), [sa])
        patch = to_builder(ast)
        assert len(patch.nodes) == 1
        node = patch.nodes[0]
        assert isinstance(node, Symbol)
        assert node.parameters["width"] == 15
        assert node.parameters["label_pos"] == 1
        assert node.parameters["label"] == "lbl"
        assert node.parameters["receive"] == "r1"
        assert node.parameters["send"] == "s1"

    def test_symbolatom_roundtrip(self):
        patch = Patcher()
        patch.add_symbol(width=15, label="test_label", send="s1", receive="r1")
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdSymbolAtom)
        assert ast.elements[0].width == 15
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, Symbol)
        assert node.parameters["width"] == 15
        assert node.parameters["label"] == "test_label"

    def test_to_builder_text_produces_comment(self):
        text = PdText(Position(50, 60), "This is a comment")
        ast = PdPatch(CanvasProperties(), [text])
        patch = to_builder(ast)
        assert len(patch.nodes) == 1
        node = patch.nodes[0]
        assert isinstance(node, Comment)
        assert node.parameters["content"] == "This is a comment"
        assert node.num_inlets == 0
        assert node.num_outlets == 0

    def test_comment_from_builder(self):
        patch = Patcher()
        comment = Comment(30, 40, "hello world")
        patch.nodes.append(comment)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdText)
        assert ast.elements[0].content == "hello world"
        assert ast.elements[0].position.x == 30
        assert ast.elements[0].position.y == 40

    def test_text_roundtrip(self):
        content = """#N canvas 0 50 1000 600 10;
#X text 50 60 This is a comment;"""
        ast = parse(content)
        assert isinstance(ast.elements[0], PdText)
        result = serialize(ast)
        ast2 = parse(result)
        assert isinstance(ast2.elements[0], PdText)
        assert ast2.elements[0].content == "This is a comment"

    def test_text_builder_roundtrip(self):
        text = PdText(Position(50, 60), "round trip text")
        ast = PdPatch(CanvasProperties(), [text])
        patch = to_builder(ast)
        ast2 = from_builder(patch)
        assert isinstance(ast2.elements[0], PdText)
        assert ast2.elements[0].content == "round trip text"
        assert ast2.elements[0].position.x == 50


class TestTransform:
    """Tests for transform function."""

    def test_transform_position(self):
        elements = [
            PdObj(Position(50, 50), "osc~"),
            PdObj(Position(50, 100), "dac~"),
        ]
        patch = PdPatch(CanvasProperties(), elements)

        def move_right(elem):
            if isinstance(elem, PdObj):
                return PdObj(
                    Position(elem.position.x + 100, elem.position.y),
                    elem.class_name,
                    elem.args,
                )
            return elem

        result = transform(patch, move_right)
        assert result.elements[0].position.x == 150
        assert result.elements[1].position.x == 150

    def test_transform_remove(self):
        elements = [
            PdObj(Position(50, 50), "osc~"),
            PdObj(Position(50, 100), "print"),
        ]
        patch = PdPatch(CanvasProperties(), elements)

        def remove_print(elem):
            if isinstance(elem, PdObj) and elem.class_name == "print":
                return None
            return elem

        result = transform(patch, remove_print)
        assert len(result.elements) == 1


class TestFindObjects:
    """Tests for find_objects function."""

    def test_find_by_class(self):
        elements = [
            PdObj(Position(50, 50), "osc~"),
            PdObj(Position(50, 100), "dac~"),
            PdMsg(Position(50, 150), "bang"),
        ]
        patch = PdPatch(CanvasProperties(), elements)

        oscillators = find_objects(patch, lambda e: isinstance(e, PdObj) and e.class_name == "osc~")
        assert len(oscillators) == 1

    def test_find_in_subpatch(self):
        inner = [PdObj(Position(50, 50), "osc~")]
        subpatch = PdSubpatch(
            CanvasProperties(0, 0, 300, 200),
            inner,
            PdRestore(Position(100, 100), "sub"),
        )
        patch = PdPatch(CanvasProperties(), [subpatch])

        oscillators = find_objects(patch, lambda e: isinstance(e, PdObj) and e.class_name == "osc~")
        assert len(oscillators) == 1


class TestRenameSendsReceives:
    """Tests for rename_sends_receives function."""

    def test_rename_in_floatatom(self):
        elements = [
            PdFloatAtom(Position(50, 50), send="old_name", receive="old_name"),
        ]
        patch = PdPatch(CanvasProperties(), elements)

        result = rename_sends_receives(patch, "old_name", "new_name")
        assert result.elements[0].send == "new_name"
        assert result.elements[0].receive == "new_name"

    def test_rename_in_send_obj(self):
        elements = [
            PdObj(Position(50, 50), "send", ("old_name",)),
        ]
        patch = PdPatch(CanvasProperties(), elements)

        result = rename_sends_receives(patch, "old_name", "new_name")
        assert result.elements[0].args[0] == "new_name"


class TestComplexPatches:
    """Tests for complex patch scenarios."""

    def test_nested_subpatches(self):
        content = """#N canvas 0 50 1000 600 10;
#N canvas 0 0 300 200 outer 0;
#N canvas 0 0 200 150 inner 0;
#X obj 50 50 inlet;
#X restore 100 100 pd inner;
#X restore 50 50 pd outer;"""

        ast = parse(content)
        outer = ast.elements[0]
        assert isinstance(outer, PdSubpatch)
        inner = outer.elements[0]
        assert isinstance(inner, PdSubpatch)

    def test_escaped_characters(self):
        content = r"""#N canvas 0 50 1000 600 10;
#X msg 50 50 hello \, world;"""

        ast = parse(content)
        msg = ast.elements[0]
        assert isinstance(msg, PdMsg)
        # The escaped comma should be preserved
        assert "\\," in msg.content


class TestASTExports:
    """Tests for AST exports from package."""

    def test_all_types_exportable(self):
        # AST types are exported from py2pd.ast
        from py2pd.ast import (
            PdPatch,
            Position,
        )

        # Just verify imports work
        assert PdPatch is not None
        assert Position is not None

    def test_functions_exportable(self):
        # Core functions are exported from py2pd
        from py2pd import (
            from_builder,
            parse,
        )

        assert parse is not None
        assert from_builder is not None

    def test_parse_error_exportable(self):
        from py2pd import ParseError

        assert issubclass(ParseError, Exception)


class TestPdNbx:
    """Tests for PdNbx AST type."""

    def test_parse_nbx(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 20 nbx 5 14 -1e+37 1e+37 0 0 "
            "empty empty empty 0 -8 0 10 -262144 -1 -1 0.0 256;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdNbx)
        assert elem.position == Position(10, 20)
        assert elem.width == 5
        assert elem.height == 14

    def test_to_builder_nbx(self):
        from py2pd.api import NumberBox
        nbx = PdNbx(Position(10, 20), width=8, min_val=0, max_val=100)
        ast = PdPatch(CanvasProperties(), [nbx])
        patch = to_builder(ast)
        assert len(patch.nodes) == 1
        node = patch.nodes[0]
        assert isinstance(node, NumberBox)
        assert node.parameters["width"] == 8
        assert node.parameters["min_val"] == 0
        assert node.parameters["max_val"] == 100

    def test_from_builder_nbx(self):
        patch = Patcher()
        patch.add_numberbox(width=6, height=16, min_val=-10, max_val=10)
        ast = from_builder(patch)
        elem = ast.elements[0]
        assert isinstance(elem, PdNbx)
        assert elem.width == 6
        assert elem.height == 16
        assert elem.min_val == -10
        assert elem.max_val == 10

    def test_nbx_roundtrip(self):
        from py2pd.api import NumberBox
        patch = Patcher()
        patch.add_numberbox(width=7, min_val=-5, max_val=50)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdNbx)
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, NumberBox)
        assert node.parameters["width"] == 7
        assert node.parameters["min_val"] == -5
        assert node.parameters["max_val"] == 50


class TestPdVsl:
    """Tests for PdVsl AST type."""

    def test_parse_vsl(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 20 vsl 15 128 0 127 0 0 "
            "empty empty empty 0 -9 0 10 -262144 -1 -1 0 1;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdVsl)
        assert elem.width == 15
        assert elem.height == 128

    def test_to_builder_vsl(self):
        from py2pd.api import VSlider
        vsl = PdVsl(Position(10, 20), width=20, height=150)
        ast = PdPatch(CanvasProperties(), [vsl])
        patch = to_builder(ast)
        node = patch.nodes[0]
        assert isinstance(node, VSlider)
        assert node.parameters["width"] == 20
        assert node.parameters["height"] == 150

    def test_vsl_roundtrip(self):
        from py2pd.api import VSlider
        patch = Patcher()
        patch.add_vslider(width=20, height=200, min_val=0, max_val=1000)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdVsl)
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, VSlider)
        assert node.parameters["width"] == 20
        assert node.parameters["height"] == 200


class TestPdHsl:
    """Tests for PdHsl AST type."""

    def test_parse_hsl(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 20 hsl 128 15 0 127 0 0 "
            "empty empty empty -2 -8 0 10 -262144 -1 -1 0 1;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdHsl)
        assert elem.width == 128
        assert elem.height == 15

    def test_to_builder_hsl(self):
        from py2pd.api import HSlider
        hsl = PdHsl(Position(10, 20), width=200, height=20)
        ast = PdPatch(CanvasProperties(), [hsl])
        patch = to_builder(ast)
        node = patch.nodes[0]
        assert isinstance(node, HSlider)
        assert node.parameters["width"] == 200
        assert node.parameters["height"] == 20

    def test_hsl_roundtrip(self):
        from py2pd.api import HSlider
        patch = Patcher()
        patch.add_hslider(width=256, height=20, min_val=0, max_val=1000)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdHsl)
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, HSlider)
        assert node.parameters["width"] == 256
        assert node.parameters["height"] == 20


class TestPdVradio:
    """Tests for PdVradio AST type."""

    def test_parse_vradio(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 20 vradio 15 0 0 8 "
            "empty empty empty 0 -8 0 10 -262144 -1 -1 0;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdVradio)
        assert elem.size == 15
        assert elem.number == 8

    def test_to_builder_vradio(self):
        from py2pd.api import VRadio
        vr = PdVradio(Position(10, 20), number=4)
        ast = PdPatch(CanvasProperties(), [vr])
        patch = to_builder(ast)
        node = patch.nodes[0]
        assert isinstance(node, VRadio)
        assert node.parameters["number"] == 4

    def test_vradio_roundtrip(self):
        from py2pd.api import VRadio
        patch = Patcher()
        patch.add_vradio(size=20, number=5)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdVradio)
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, VRadio)
        assert node.parameters["size"] == 20
        assert node.parameters["number"] == 5


class TestPdHradio:
    """Tests for PdHradio AST type."""

    def test_parse_hradio(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 20 hradio 15 0 0 8 "
            "empty empty empty 0 -8 0 10 -262144 -1 -1 0;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdHradio)
        assert elem.size == 15
        assert elem.number == 8

    def test_to_builder_hradio(self):
        from py2pd.api import HRadio
        hr = PdHradio(Position(10, 20), number=6)
        ast = PdPatch(CanvasProperties(), [hr])
        patch = to_builder(ast)
        node = patch.nodes[0]
        assert isinstance(node, HRadio)
        assert node.parameters["number"] == 6

    def test_hradio_roundtrip(self):
        from py2pd.api import HRadio
        patch = Patcher()
        patch.add_hradio(size=20, number=3)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdHradio)
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, HRadio)
        assert node.parameters["size"] == 20
        assert node.parameters["number"] == 3


class TestPdCnv:
    """Tests for PdCnv AST type."""

    def test_parse_cnv(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 20 cnv 15 100 60 "
            "empty empty empty 20 12 0 14 -233017 -1 0;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdCnv)
        assert elem.size == 15
        assert elem.width == 100
        assert elem.height == 60

    def test_to_builder_cnv(self):
        from py2pd.api import Canvas
        cnv = PdCnv(Position(10, 20), width=200, height=100)
        ast = PdPatch(CanvasProperties(), [cnv])
        patch = to_builder(ast)
        node = patch.nodes[0]
        assert isinstance(node, Canvas)
        assert node.parameters["width"] == 200
        assert node.parameters["height"] == 100

    def test_cnv_roundtrip(self):
        from py2pd.api import Canvas
        patch = Patcher()
        patch.add_canvas(width=300, height=150, label="test_label")
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdCnv)
        assert ast.elements[0].label == "test_label"
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, Canvas)
        assert node.parameters["width"] == 300
        assert node.parameters["height"] == 150

    def test_cnv_str_trailing_zero(self):
        cnv = PdCnv(Position(10, 20))
        result = str(cnv)
        assert result.endswith("0;")


class TestPdVu:
    """Tests for PdVu AST type."""

    def test_parse_vu(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 10 20 vu 15 120 "
            "empty empty -1 -8 0 10 -262144 -1 1 0;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdVu)
        assert elem.width == 15
        assert elem.height == 120

    def test_to_builder_vu(self):
        from py2pd.api import VU
        vu = PdVu(Position(10, 20), width=20, height=150)
        ast = PdPatch(CanvasProperties(), [vu])
        patch = to_builder(ast)
        node = patch.nodes[0]
        assert isinstance(node, VU)
        assert node.parameters["width"] == 20
        assert node.parameters["height"] == 150

    def test_vu_roundtrip(self):
        from py2pd.api import VU
        patch = Patcher()
        patch.add_vu(width=25, height=200)
        ast = from_builder(patch)
        assert isinstance(ast.elements[0], PdVu)
        restored = to_builder(ast)
        node = restored.nodes[0]
        assert isinstance(node, VU)
        assert node.parameters["width"] == 25
        assert node.parameters["height"] == 200

    def test_vu_str_trailing_zero(self):
        vu = PdVu(Position(10, 20))
        result = str(vu)
        assert result.endswith("0;")


class TestPreprocess:
    """Tests for _preprocess function."""

    def test_crlf_normalization(self):
        result = _preprocess("line1\r\nline2\r\n")
        assert "\r" not in result
        assert result == "line1\nline2\n"

    def test_cr_normalization(self):
        result = _preprocess("line1\rline2\r")
        assert "\r" not in result
        assert result == "line1\nline2\n"

    def test_line_continuation(self):
        result = _preprocess("hello \\\nworld")
        assert result == "hello world"

    def test_multiple_continuations(self):
        result = _preprocess("a \\\nb \\\nc")
        assert result == "a b c"

    def test_mixed_endings_and_continuation(self):
        result = _preprocess("a \\\r\nb")
        assert result == "a b"

    def test_noop(self):
        result = _preprocess("no special chars")
        assert result == "no special chars"


class TestSplitStatements:
    """Tests for _split_statements function."""

    def test_basic_splitting(self):
        stmts = _split_statements("#X obj 0 0 test;#X msg 0 0 bang;")
        assert len(stmts) == 2
        assert stmts[0] == "#X obj 0 0 test;"
        assert stmts[1] == "#X msg 0 0 bang;"

    def test_escaped_semicolons(self):
        stmts = _split_statements(r"#X msg 0 0 hello \; world;")
        assert len(stmts) == 1
        assert r"\;" in stmts[0]

    def test_empty_input(self):
        stmts = _split_statements("")
        assert stmts == []

    def test_whitespace_only(self):
        stmts = _split_statements("   \n\t  ")
        assert stmts == []

    def test_consecutive_semicolons(self):
        stmts = _split_statements("a;b;;c;")
        # The bare ";" from ";;" is kept as a non-empty statement
        assert len(stmts) == 4
        assert stmts[0] == "a;"
        assert stmts[1] == "b;"
        assert stmts[2] == ";"
        assert stmts[3] == "c;"

    def test_trailing_content_without_semicolon(self):
        stmts = _split_statements("#X obj 0 0 test;trailing")
        assert len(stmts) == 2
        assert stmts[1] == "trailing"


class TestParserRobustness:
    """Tests for parser handling of malformed input."""

    def test_truncated_obj_line(self):
        content = "#N canvas 0 50 450 300 10;\n#X obj 50;"
        with pytest.raises(ParseError):
            parse(content)

    def test_missing_connect_fields(self):
        content = "#N canvas 0 50 450 300 10;\n#X connect 0 0;"
        with pytest.raises(ParseError):
            parse(content)

    def test_binary_garbage(self):
        content = b"\x00\x01\x02\xff\xfe".decode("utf-8", errors="replace")
        with pytest.raises(ParseError):
            parse(content)

    def test_truncated_canvas_line(self):
        content = "#N canvas 0 50;"
        with pytest.raises(ParseError):
            parse(content)


class TestPdCoords:
    """Tests for PdCoords AST type."""

    def test_parse_with_all_fields(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X coords 0 1 1 0 200 140 1 0 0 0;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdCoords)
        assert elem.x_from == 0
        assert elem.y_from == 1
        assert elem.x_to == 1
        assert elem.y_to == 0
        assert elem.width == 200
        assert elem.height == 140
        assert elem.graph_on_parent == 1

    def test_parse_with_minimal_fields(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X coords 0 1 1 0 100 80 1;"
        )
        ast = parse(content)
        elem = ast.elements[0]
        assert isinstance(elem, PdCoords)
        assert elem.hide_name == 0
        assert elem.x_margin == 0
        assert elem.y_margin == 0

    def test_str_roundtrip(self):
        coords = PdCoords(0, 1, 1, 0, 200, 140, 1, 0, 5, 10)
        result = str(coords)
        assert result == "#X coords 0 1 1 0 200 140 1 0 5 10;"

    def test_coords_in_patch_context(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X obj 50 50 osc~ 440;\n"
            "#X coords 0 1 1 0 200 140 1 0 0 0;"
        )
        ast = parse(content)
        assert len(ast.elements) == 2
        assert isinstance(ast.elements[0], PdObj)
        assert isinstance(ast.elements[1], PdCoords)


class TestGOPBridge:
    """Tests for Graph-on-Parent round-trip through from_builder/to_builder."""

    def test_gop_from_builder(self):
        inner = Patcher()
        inner.add("inlet", x_pos=50, y_pos=50)
        parent = Patcher()
        parent.add_subpatch(
            "controls", inner,
            graph_on_parent=True, gop_width=120, gop_height=80,
            x_pos=100, y_pos=200,
        )
        ast = from_builder(parent)
        subpatch = ast.elements[0]
        assert isinstance(subpatch, PdSubpatch)
        # Should contain inlet + PdCoords
        coords_elems = [e for e in subpatch.elements if isinstance(e, PdCoords)]
        assert len(coords_elems) == 1
        coords = coords_elems[0]
        assert coords.graph_on_parent == 1
        assert coords.width == 120
        assert coords.height == 80
        assert coords.hide_name == 0

    def test_gop_from_builder_hide_name(self):
        inner = Patcher()
        parent = Patcher()
        parent.add_subpatch(
            "ui", inner,
            graph_on_parent=True, hide_name=True,
            x_pos=10, y_pos=20,
        )
        ast = from_builder(parent)
        subpatch = ast.elements[0]
        coords_elems = [e for e in subpatch.elements if isinstance(e, PdCoords)]
        assert len(coords_elems) == 1
        assert coords_elems[0].hide_name == 1

    def test_gop_from_builder_no_coords_when_off(self):
        inner = Patcher()
        parent = Patcher()
        parent.add_subpatch("plain", inner, x_pos=10, y_pos=20)
        ast = from_builder(parent)
        subpatch = ast.elements[0]
        coords_elems = [e for e in subpatch.elements if isinstance(e, PdCoords)]
        assert len(coords_elems) == 0

    def test_gop_to_builder(self):
        # Build an AST with a subpatch containing PdCoords
        inner_canvas = CanvasProperties(0, 0, 400, 300, 10, "(subpatch)", 0)
        inner_elements = [
            PdObj(Position(50, 50), "inlet"),
            PdCoords(0, 1, 1, 0, 150, 100, 1, 1, 0, 0),
        ]
        restore = PdRestore(Position(100, 200), "controls")
        subpatch = PdSubpatch(inner_canvas, inner_elements, restore)
        ast = PdPatch(CanvasProperties(), [subpatch])
        patch = to_builder(ast)
        assert len(patch.nodes) == 1
        sp = patch.nodes[0]
        assert isinstance(sp, Subpatch)
        assert sp.parameters["graph_on_parent"] is True
        assert sp.parameters["hide_name"] is True
        assert sp.parameters["gop_width"] == 150
        assert sp.parameters["gop_height"] == 100
        assert sp.canvas_width == 400
        assert sp.canvas_height == 300

    def test_gop_roundtrip(self):
        inner = Patcher()
        inner.add("inlet", x_pos=50, y_pos=50)
        parent = Patcher()
        parent.add_subpatch(
            "controls", inner,
            graph_on_parent=True, hide_name=True,
            gop_width=200, gop_height=150,
            canvas_width=500, canvas_height=400,
            x_pos=100, y_pos=200,
        )
        # builder -> AST -> builder
        ast = from_builder(parent)
        rebuilt = to_builder(ast)
        sp = rebuilt.nodes[0]
        assert isinstance(sp, Subpatch)
        assert sp.parameters["graph_on_parent"] is True
        assert sp.parameters["hide_name"] is True
        assert sp.parameters["gop_width"] == 200
        assert sp.parameters["gop_height"] == 150
        assert sp.canvas_width == 500
        assert sp.canvas_height == 400

    def test_gop_canvas_dimensions_preserved(self):
        inner = Patcher()
        parent = Patcher()
        parent.add_subpatch(
            "test", inner,
            canvas_width=600, canvas_height=450,
            x_pos=10, y_pos=20,
        )
        ast = from_builder(parent)
        subpatch = ast.elements[0]
        assert isinstance(subpatch, PdSubpatch)
        assert subpatch.canvas.width == 600
        assert subpatch.canvas.height == 450


class TestAbstractionBridge:
    """Tests for Abstraction round-trip through from_builder/to_builder."""

    def test_abstraction_from_builder(self):
        parent = Patcher()
        parent.add_abstraction("my-synth", "440", x_pos=100, y_pos=200, num_inlets=1)
        ast = from_builder(parent)
        assert len(ast.elements) == 1
        obj = ast.elements[0]
        assert isinstance(obj, PdObj)
        assert obj.class_name == "my-synth"
        assert obj.args == ("440",)
        assert obj.position.x == 100
        assert obj.position.y == 200

    def test_abstraction_from_builder_no_args(self):
        parent = Patcher()
        parent.add_abstraction("reverb", x_pos=50, y_pos=50)
        ast = from_builder(parent)
        obj = ast.elements[0]
        assert isinstance(obj, PdObj)
        assert obj.class_name == "reverb"
        assert obj.args == ()

    def test_abstraction_roundtrip_produces_obj(self):
        """Abstraction -> AST -> builder produces Obj (not Abstraction).

        This is expected: the distinction is purely at the builder level.
        At the file format level, abstractions are indistinguishable from
        regular objects.
        """
        parent = Patcher()
        parent.add_abstraction("my-synth", "440", x_pos=100, y_pos=200)
        ast = from_builder(parent)
        rebuilt = to_builder(ast)
        assert len(rebuilt.nodes) == 1
        # Should come back as Obj, not Abstraction
        from py2pd.api import Obj
        assert type(rebuilt.nodes[0]) is Obj
        assert rebuilt.nodes[0].parameters["text"] == "my-synth 440"
