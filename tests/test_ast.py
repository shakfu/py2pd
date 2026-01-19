"""Tests for py2pd.ast module."""

import pytest
import tempfile
import os
from py2pd import (
    # Builder API
    Patcher,
    # AST types
    PdPatch,
    PdObj,
    PdMsg,
    PdFloatatom,
    PdText,
    PdArray,
    PdConnect,
    PdSubpatch,
    PdRestore,
    Position,
    CanvasProperties,
    # Functions
    parse,
    parse_file,
    serialize,
    serialize_to_file,
    ParseError,
    from_builder,
    to_builder,
    transform,
    find_objects,
    rename_sends_receives,
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


class TestPdFloatatom:
    """Tests for PdFloatatom class."""

    def test_floatatom_defaults(self):
        fa = PdFloatatom(Position(100, 200))
        assert fa.width == 5
        assert fa.lower_limit == 0
        assert fa.upper_limit == 0

    def test_floatatom_str(self):
        fa = PdFloatatom(Position(100, 200), 5, 0, 127)
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
        assert isinstance(patch.elements[0], PdFloatatom)

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

        oscillators = find_objects(
            patch, lambda e: isinstance(e, PdObj) and e.class_name == "osc~"
        )
        assert len(oscillators) == 1

    def test_find_in_subpatch(self):
        inner = [PdObj(Position(50, 50), "osc~")]
        subpatch = PdSubpatch(
            CanvasProperties(0, 0, 300, 200),
            inner,
            PdRestore(Position(100, 100), "sub"),
        )
        patch = PdPatch(CanvasProperties(), [subpatch])

        oscillators = find_objects(
            patch, lambda e: isinstance(e, PdObj) and e.class_name == "osc~"
        )
        assert len(oscillators) == 1


class TestRenameSendsReceives:
    """Tests for rename_sends_receives function."""

    def test_rename_in_floatatom(self):
        elements = [
            PdFloatatom(Position(50, 50), send="old_name", receive="old_name"),
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
        from py2pd import (
            PdPatch,
            Position,
        )

        # Just verify imports work
        assert PdPatch is not None
        assert Position is not None

    def test_functions_exportable(self):
        from py2pd import (
            parse,
            from_builder,
        )

        assert parse is not None
        assert from_builder is not None

    def test_parse_error_exportable(self):
        from py2pd import ParseError

        assert issubclass(ParseError, Exception)
