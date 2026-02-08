"""Tests for py2pd.api module."""

import warnings

import pytest

from py2pd import (
    CycleWarning,
    InvalidConnectionError,
    LayoutManager,
    NodeNotFoundError,
    PdConnectionError,
    Patcher,
)
from py2pd.api import (
    CHAR_WIDTH,
    COLUMN_WIDTH,
    DEFAULT_MARGIN,
    ELEMENT_BASE_HEIGHT,
    ELEMENT_PADDING,
    FLOATATOM_HEIGHT,
    FLOATATOM_WIDTH,
    IEM_BG_COLOR,
    IEM_DEFAULT_SIZE,
    IEM_FG_COLOR,
    IEM_LABEL_COLOR,
    LINE_HEIGHT,
    MIN_ELEMENT_WIDTH,
    PD_OBJECT_REGISTRY,
    ROW_HEIGHT,
    SUBPATCH_CANVAS_HEIGHT,
    SUBPATCH_CANVAS_WIDTH,
    TEXT_WRAP_WIDTH,
    VU,
    Array,
    Bang,
    Canvas,
    Comment,
    Connection,
    Float,
    HRadio,
    HSlider,
    Msg,
    Node,
    NumberBox,
    Obj,
    Subpatch,
    Symbol,
    Toggle,
    VRadio,
    VSlider,
    escape,
    get_display_lines,
    unescape,
)


class TestEscape:
    """Tests for the escape function."""

    def test_escape_backslash(self):
        assert escape("a\\b") == "a\\\\b"

    def test_escape_semicolon(self):
        assert escape("a;b") == "a \\; b"

    def test_escape_comma(self):
        assert escape("a,b") == "a \\, b"

    def test_escape_dollar_before_digit(self):
        assert escape("$1") == "\\$1"
        assert escape("$9") == "\\$9"

    def test_escape_dollar_not_before_digit(self):
        assert escape("$a") == "$a"
        assert escape("$ ") == "$ "

    def test_escape_empty_string(self):
        assert escape("") == ""

    def test_escape_no_special_chars(self):
        assert escape("hello world") == "hello world"

    def test_escape_multiple_specials(self):
        result = escape("a;b,c\\d$1")
        assert "\\;" in result
        assert "\\," in result
        assert "\\\\" in result
        assert "\\$1" in result


class TestUnescape:
    """Tests for the unescape function."""

    def test_unescape_semicolon(self):
        # Note: escape adds spaces around \;
        assert "\n" in unescape(" \\; ")

    def test_unescape_comma(self):
        assert "," in unescape(" \\, ")

    def test_unescape_dollar(self):
        assert "$" in unescape("\\$")

    def test_unescape_strips_lines(self):
        result = unescape("  hello  ")
        assert result == "hello"


class TestGetDisplayLines:
    """Tests for the get_display_lines function."""

    def test_single_line(self):
        lines = get_display_lines("hello")
        assert lines == ["hello"]

    def test_empty_string(self):
        lines = get_display_lines("")
        assert lines == []

    def test_multiline_via_semicolon(self):
        # Semicolons become newlines when unescaped
        escaped = escape("line1;line2")
        lines = get_display_lines(escaped)
        assert len(lines) == 2

    def test_long_line_wraps(self):
        long_text = "x" * 100
        lines = get_display_lines(long_text)
        assert len(lines) > 1
        # Each line should be at most TEXT_WRAP_WIDTH
        for line in lines:
            assert len(line) <= TEXT_WRAP_WIDTH + 10  # Allow some tolerance


class TestConstants:
    """Tests that constants have expected values."""

    def test_layout_constants(self):
        assert ROW_HEIGHT == 25
        assert COLUMN_WIDTH == 50
        assert DEFAULT_MARGIN == 25

    def test_text_constants(self):
        assert TEXT_WRAP_WIDTH == 60
        assert CHAR_WIDTH == 6
        assert MIN_ELEMENT_WIDTH == 50
        assert ELEMENT_PADDING == 20
        assert LINE_HEIGHT == 15
        assert ELEMENT_BASE_HEIGHT == 10

    def test_floatatom_constants(self):
        assert FLOATATOM_WIDTH == 50
        assert FLOATATOM_HEIGHT == 25


class TestNode:
    """Tests for Node base class."""

    def test_outlet_access(self):
        patch = Patcher()
        obj = patch.add("test")
        outlet = obj[0]
        assert isinstance(outlet, Node.Outlet)
        assert outlet.owner is obj
        assert outlet.index == 0

    def test_outlet_multiple_indices(self):
        patch = Patcher()
        obj = patch.add("test")
        assert obj[0].index == 0
        assert obj[1].index == 1
        assert obj[99].index == 99

    def test_outlet_invalid_type(self):
        patch = Patcher()
        obj = patch.add("test")
        with pytest.raises(TypeError):
            obj["invalid"]

    def test_outlet_negative_index(self):
        patch = Patcher()
        obj = patch.add("test")
        with pytest.raises(ValueError):
            obj[-1]

    def test_outlet_repr(self):
        patch = Patcher()
        obj = patch.add("test")
        outlet = obj[0]
        repr_str = repr(outlet)
        assert "Outlet" in repr_str
        assert "0" in repr_str


class TestObj:
    """Tests for Obj class."""

    def test_str_format(self):
        obj = Obj(100, 200, "osc~ 440")
        result = str(obj)
        assert result.startswith("#X obj ")
        assert "100" in result
        assert "200" in result
        assert "osc~" in result
        assert result.endswith(";\n")

    def test_repr(self):
        obj = Obj(100, 200, "test")
        repr_str = repr(obj)
        assert "Obj" in repr_str
        assert "100" in repr_str
        assert "200" in repr_str

    def test_position(self):
        obj = Obj(50, 75, "test")
        assert obj.position == (50, 75)

    def test_size_minimum(self):
        obj = Obj(0, 0, "x")
        width, height = obj.dimensions
        assert width >= MIN_ELEMENT_WIDTH

    def test_size_scales_with_text(self):
        short_obj = Obj(0, 0, "x")
        long_obj = Obj(0, 0, "x" * 50)
        assert long_obj.dimensions[0] > short_obj.dimensions[0]

    def test_escapes_text(self):
        obj = Obj(0, 0, "test;with;semicolons")
        assert "\\;" in str(obj)


class TestMsg:
    """Tests for Msg class."""

    def test_str_format(self):
        msg = Msg(100, 200, "bang")
        result = str(msg)
        assert result.startswith("#X msg ")
        assert "100" in result
        assert "200" in result
        assert "bang" in result
        assert result.endswith(";\n")

    def test_repr(self):
        msg = Msg(100, 200, "test")
        assert "Msg" in repr(msg)

    def test_escapes_text(self):
        msg = Msg(0, 0, "value $1")
        assert "\\$1" in str(msg)


class TestFloat:
    """Tests for Float class."""

    def test_str_format(self):
        fa = Float(100, 200)
        result = str(fa)
        assert result.startswith("#X floatatom ")
        assert "100" in result
        assert "200" in result
        assert result.endswith(";\n")

    def test_default_parameters(self):
        fa = Float(0, 0)
        result = str(fa)
        # Check default values are present
        assert " 5 " in result  # default width
        assert " - " in result  # default label/receive/send

    def test_custom_parameters(self):
        fa = Float(0, 0, width=10, upper_limit=100, lower_limit=0)
        result = str(fa)
        assert " 10 " in result  # width
        assert " 100 " in result  # upper_limit

    def test_size(self):
        fa = Float(0, 0)
        assert fa.dimensions == (FLOATATOM_WIDTH, FLOATATOM_HEIGHT)

    def test_repr(self):
        fa = Float(50, 60, width=8)
        repr_str = repr(fa)
        assert "Float" in repr_str
        assert "50" in repr_str
        assert "60" in repr_str


class TestSubpatch:
    """Tests for Subpatch class."""

    def test_str_format(self):
        inner = Patcher()
        inner.add("inlet")
        sp = Subpatch(100, 200, "mysubpatch", inner)
        result = str(sp)
        assert "#N canvas" in result
        assert "#X restore" in result
        assert "pd mysubpatch" in result
        assert "100" in result
        assert "200" in result

    def test_contains_inner_patch(self):
        inner = Patcher()
        inner.add("inlet")
        inner.add("outlet")
        sp = Subpatch(0, 0, "test", inner)
        result = str(sp)
        assert "inlet" in result
        assert "outlet" in result

    def test_repr(self):
        inner = Patcher()
        sp = Subpatch(50, 60, "myname", inner)
        assert "Subpatch" in repr(sp)
        assert "myname" in repr(sp)

    def test_default_canvas_size(self):
        """Default canvas dimensions should be 300x180."""
        inner = Patcher()
        sp = Subpatch(0, 0, "test", inner)
        result = str(sp)
        assert "#N canvas 0 0 300 180" in result
        assert sp.canvas_width == SUBPATCH_CANVAS_WIDTH
        assert sp.canvas_height == SUBPATCH_CANVAS_HEIGHT

    def test_custom_canvas_size(self):
        """Custom canvas dimensions should be used."""
        inner = Patcher()
        sp = Subpatch(0, 0, "test", inner, canvas_width=500, canvas_height=400)
        result = str(sp)
        assert "#N canvas 0 0 500 400" in result
        assert sp.canvas_width == 500
        assert sp.canvas_height == 400

    def test_inner_patch_independent_coordinates(self):
        """Inner patch elements use their own coordinate system."""
        inner = Patcher()
        # Elements in inner patch start at their own (25, 25) not parent's
        inlet = inner.add("inlet")
        assert inlet.position == (DEFAULT_MARGIN, DEFAULT_MARGIN)

        # Parent subpatch position is independent
        parent = Patcher()
        sp = parent.add_subpatch("test", inner, x_pos=500, y_pos=500)
        assert sp.position == (500, 500)

        # Inner elements still at their original coordinates
        assert inlet.position == (DEFAULT_MARGIN, DEFAULT_MARGIN)

    def test_subpatch_constants_exported(self):
        """Subpatch constants should be exported."""
        from py2pd import SUBPATCH_CANVAS_HEIGHT, SUBPATCH_CANVAS_WIDTH

        assert SUBPATCH_CANVAS_WIDTH == 300
        assert SUBPATCH_CANVAS_HEIGHT == 180


class TestSubpatchLayoutInheritance:
    """Tests for subpatch layout inheritance."""

    def test_inherit_layout_false_by_default(self):
        """By default, inner patch has independent layout settings."""
        parent = Patcher(layout=LayoutManager(default_margin=100, row_height=50, column_width=80))
        inner = Patcher()  # Default settings

        parent.add_subpatch("test", inner)

        # Inner patch should have default settings, not parent's
        assert inner.layout.default_margin == DEFAULT_MARGIN
        assert inner.layout.row_height == ROW_HEIGHT
        assert inner.layout.column_width == COLUMN_WIDTH

    def test_inherit_layout_true_copies_settings(self):
        """With inherit_layout=True, parent settings are copied."""
        parent = Patcher(layout=LayoutManager(default_margin=100, row_height=50, column_width=80))
        inner = Patcher()

        parent.add_subpatch("test", inner, inherit_layout=True)

        # Inner patch should now have parent's settings
        assert inner.layout.default_margin == 100
        assert inner.layout.row_height == 50
        assert inner.layout.column_width == 80

    def test_inherit_layout_affects_element_positioning(self):
        """Inherited layout settings affect element positioning in inner patch."""
        parent = Patcher(layout=LayoutManager(default_margin=50))
        inner = Patcher()

        parent.add_subpatch("test", inner, inherit_layout=True)

        # Now create element in inner - should use inherited margin
        obj = inner.add("test")
        assert obj.position == (50, 50)

    def test_create_subpatch_with_canvas_and_inherit(self):
        """Both canvas size and inherit_layout can be specified."""
        parent = Patcher(layout=LayoutManager(default_margin=40))
        inner = Patcher()

        sp = parent.add_subpatch(
            "test", inner, canvas_width=600, canvas_height=400, inherit_layout=True
        )

        assert sp.canvas_width == 600
        assert sp.canvas_height == 400
        assert inner.layout.default_margin == 40


class TestArray:
    """Tests for Array class."""

    def test_str_format(self):
        arr = Array("myarray", 1024)
        result = str(arr)
        assert "#X array" in result
        assert "myarray" in result
        assert "1024" in result
        assert "float" in result  # default type

    def test_custom_type(self):
        arr = Array("myarray", 512, element_type="int")
        assert "int" in str(arr)

    def test_hidden(self):
        arr = Array("myarray", 100)
        assert arr.hidden is True
        assert arr.position == (-1, -1)

    def test_repr(self):
        arr = Array("testarray", 256)
        repr_str = repr(arr)
        assert "Array" in repr_str
        assert "testarray" in repr_str
        assert "256" in repr_str


class TestBang:
    """Tests for Bang class."""

    def test_str_format(self):
        bang = Bang(100, 200)
        result = str(bang)
        assert "#X obj 100 200 bng" in result
        assert "15" in result  # default size

    def test_custom_size(self):
        bang = Bang(0, 0, size=25)
        assert "25" in str(bang)

    def test_send_receive(self):
        bang = Bang(0, 0, send="mysend", receive="myreceive")
        result = str(bang)
        assert "mysend" in result
        assert "myreceive" in result

    def test_repr(self):
        bang = Bang(10, 20, size=30)
        repr_str = repr(bang)
        assert "Bang" in repr_str
        assert "size=30" in repr_str

    def test_size_property(self):
        bang = Bang(0, 0, size=20)
        assert bang.dimensions == (20, 20)

    def test_inlet_outlet_counts(self):
        bang = Bang(0, 0)
        assert bang.num_inlets == 1
        assert bang.num_outlets == 1


class TestToggle:
    """Tests for Toggle class."""

    def test_str_format(self):
        toggle = Toggle(100, 200)
        result = str(toggle)
        assert "#X obj 100 200 tgl" in result
        assert "15" in result  # default size

    def test_default_value(self):
        toggle = Toggle(0, 0, default_value=5)
        assert "5" in str(toggle)

    def test_repr(self):
        toggle = Toggle(10, 20, size=25)
        repr_str = repr(toggle)
        assert "Toggle" in repr_str
        assert "size=25" in repr_str

    def test_inlet_outlet_counts(self):
        toggle = Toggle(0, 0)
        assert toggle.num_inlets == 1
        assert toggle.num_outlets == 1


class TestSymbol:
    """Tests for Symbol class."""

    def test_str_format(self):
        sym = Symbol(100, 200)
        result = str(sym)
        assert "#X symbolatom 100 200" in result
        assert "10" in result  # default width

    def test_custom_width(self):
        sym = Symbol(0, 0, width=20)
        assert "20" in str(sym)

    def test_repr(self):
        sym = Symbol(10, 20, width=15)
        repr_str = repr(sym)
        assert "Symbol" in repr_str
        assert "width=15" in repr_str

    def test_inlet_outlet_counts(self):
        sym = Symbol(0, 0)
        assert sym.num_inlets == 1
        assert sym.num_outlets == 1


class TestNumberBox:
    """Tests for NumberBox class."""

    def test_str_format(self):
        nbx = NumberBox(100, 200)
        result = str(nbx)
        assert "#X obj 100 200 nbx" in result

    def test_min_max(self):
        nbx = NumberBox(0, 0, min_val=0, max_val=100)
        result = str(nbx)
        assert "0" in result
        assert "100" in result

    def test_repr(self):
        nbx = NumberBox(10, 20, width=8)
        repr_str = repr(nbx)
        assert "NumberBox" in repr_str
        assert "width=8" in repr_str

    def test_inlet_outlet_counts(self):
        nbx = NumberBox(0, 0)
        assert nbx.num_inlets == 1
        assert nbx.num_outlets == 1


class TestVSlider:
    """Tests for VSlider class."""

    def test_str_format(self):
        vsl = VSlider(100, 200)
        result = str(vsl)
        assert "#X obj 100 200 vsl" in result
        assert "15" in result  # default width
        assert "128" in result  # default height

    def test_min_max(self):
        vsl = VSlider(0, 0, min_val=0, max_val=1000)
        result = str(vsl)
        assert "0" in result
        assert "1000" in result

    def test_repr(self):
        vsl = VSlider(10, 20, width=20, height=150)
        repr_str = repr(vsl)
        assert "VSlider" in repr_str
        assert "20x150" in repr_str

    def test_size_property(self):
        vsl = VSlider(0, 0, width=20, height=100)
        assert vsl.dimensions == (20, 100)


class TestHSlider:
    """Tests for HSlider class."""

    def test_str_format(self):
        hsl = HSlider(100, 200)
        result = str(hsl)
        assert "#X obj 100 200 hsl" in result
        assert "128" in result  # default width
        assert "15" in result  # default height

    def test_repr(self):
        hsl = HSlider(10, 20, width=200, height=25)
        repr_str = repr(hsl)
        assert "HSlider" in repr_str
        assert "200x25" in repr_str

    def test_size_property(self):
        hsl = HSlider(0, 0, width=150, height=20)
        assert hsl.dimensions == (150, 20)


class TestVRadio:
    """Tests for VRadio class."""

    def test_str_format(self):
        vradio = VRadio(100, 200)
        result = str(vradio)
        assert "#X obj 100 200 vradio" in result
        assert "8" in result  # default number of buttons

    def test_custom_number(self):
        vradio = VRadio(0, 0, number=4)
        assert "4" in str(vradio)

    def test_repr(self):
        vradio = VRadio(10, 20, number=5)
        repr_str = repr(vradio)
        assert "VRadio" in repr_str
        assert "number=5" in repr_str

    def test_size_property(self):
        vradio = VRadio(0, 0, size=20, number=4)
        assert vradio.dimensions == (20, 80)  # width=size, height=size*number


class TestHRadio:
    """Tests for HRadio class."""

    def test_str_format(self):
        hradio = HRadio(100, 200)
        result = str(hradio)
        assert "#X obj 100 200 hradio" in result

    def test_custom_number(self):
        hradio = HRadio(0, 0, number=3)
        assert "3" in str(hradio)

    def test_repr(self):
        hradio = HRadio(10, 20, number=6)
        repr_str = repr(hradio)
        assert "HRadio" in repr_str
        assert "number=6" in repr_str

    def test_size_property(self):
        hradio = HRadio(0, 0, size=20, number=4)
        assert hradio.dimensions == (80, 20)  # width=size*number, height=size


class TestCanvas:
    """Tests for Canvas class."""

    def test_str_format(self):
        cnv = Canvas(100, 200)
        result = str(cnv)
        assert "#X obj 100 200 cnv" in result
        assert "100" in result  # default width
        assert "60" in result  # default height

    def test_custom_size(self):
        cnv = Canvas(0, 0, width=200, height=150)
        result = str(cnv)
        assert "200" in result
        assert "150" in result

    def test_label(self):
        cnv = Canvas(0, 0, label="My Label")
        assert "My" in str(cnv)  # PD escapes spaces

    def test_repr(self):
        cnv = Canvas(10, 20, width=300, height=200)
        repr_str = repr(cnv)
        assert "Canvas" in repr_str
        assert "300x200" in repr_str

    def test_size_property(self):
        cnv = Canvas(0, 0, width=150, height=80)
        assert cnv.dimensions == (150, 80)


class TestVU:
    """Tests for VU class."""

    def test_str_format(self):
        vu = VU(100, 200)
        result = str(vu)
        assert "#X obj 100 200 vu" in result
        assert "15" in result  # default width
        assert "120" in result  # default height

    def test_custom_size(self):
        vu = VU(0, 0, width=20, height=150)
        result = str(vu)
        assert "20" in result
        assert "150" in result

    def test_repr(self):
        vu = VU(10, 20, width=25, height=100)
        repr_str = repr(vu)
        assert "VU" in repr_str
        assert "25x100" in repr_str

    def test_inlet_outlet_counts(self):
        vu = VU(0, 0)
        assert vu.num_inlets == 2  # RMS and peak
        assert vu.num_outlets == 0


class TestIEMConstants:
    """Tests for IEM GUI constants."""

    def test_iem_colors(self):
        assert IEM_BG_COLOR == -262144
        assert IEM_FG_COLOR == -1
        assert IEM_LABEL_COLOR == -1

    def test_iem_default_size(self):
        assert IEM_DEFAULT_SIZE == 15


class TestConnection:
    """Tests for Connection class."""

    def test_str_format(self):
        conn = Connection(0, 0, 1, 0)
        result = str(conn)
        assert result == "#X connect 0 0 1 0;\n"

    def test_repr(self):
        conn = Connection(2, 1, 3, 0)
        repr_str = repr(conn)
        assert "Connection" in repr_str
        assert "2" in repr_str
        assert "1" in repr_str


class TestPatcher:
    """Tests for Patcher class."""

    def test_empty_patch(self):
        patch = Patcher()
        result = str(patch)
        assert result.startswith("#N canvas")
        assert "0 50 1000 600 10" in result

    def test_repr(self):
        patch = Patcher()
        patch.add("test")
        repr_str = repr(patch)
        assert "Patcher" in repr_str
        assert "nodes=1" in repr_str

    def test_add(self):
        patch = Patcher()
        obj = patch.add("osc~ 440")
        assert isinstance(obj, Obj)
        assert obj in patch.nodes

    def test_add_msg(self):
        patch = Patcher()
        msg = patch.add_msg("bang")
        assert isinstance(msg, Msg)
        assert msg in patch.nodes

    def test_add_float(self):
        patch = Patcher()
        fa = patch.add_float()
        assert isinstance(fa, Float)
        assert fa in patch.nodes

    def test_add_array(self):
        patch = Patcher()
        arr = patch.add_array("myarray", 1024)
        assert isinstance(arr, Array)
        assert arr in patch.nodes

    def test_add_subpatch(self):
        inner = Patcher()
        inner.add("inlet")
        patch = Patcher()
        sp = patch.add_subpatch("mysub", inner)
        assert isinstance(sp, Subpatch)
        assert sp in patch.nodes

    def test_add_bang(self):
        patch = Patcher()
        bang = patch.add_bang()
        assert isinstance(bang, Bang)
        assert bang in patch.nodes

    def test_add_toggle(self):
        patch = Patcher()
        toggle = patch.add_toggle()
        assert isinstance(toggle, Toggle)
        assert toggle in patch.nodes

    def test_add_symbol(self):
        patch = Patcher()
        sym = patch.add_symbol()
        assert isinstance(sym, Symbol)
        assert sym in patch.nodes

    def test_add_numberbox(self):
        patch = Patcher()
        nbx = patch.add_numberbox()
        assert isinstance(nbx, NumberBox)
        assert nbx in patch.nodes

    def test_add_vslider(self):
        patch = Patcher()
        vsl = patch.add_vslider()
        assert isinstance(vsl, VSlider)
        assert vsl in patch.nodes

    def test_add_hslider(self):
        patch = Patcher()
        hsl = patch.add_hslider()
        assert isinstance(hsl, HSlider)
        assert hsl in patch.nodes

    def test_add_vradio(self):
        patch = Patcher()
        vradio = patch.add_vradio()
        assert isinstance(vradio, VRadio)
        assert vradio in patch.nodes

    def test_add_hradio(self):
        patch = Patcher()
        hradio = patch.add_hradio()
        assert isinstance(hradio, HRadio)
        assert hradio in patch.nodes

    def test_add_canvas(self):
        patch = Patcher()
        cnv = patch.add_canvas()
        assert isinstance(cnv, Canvas)
        assert cnv in patch.nodes

    def test_add_vu(self):
        patch = Patcher()
        vu = patch.add_vu()
        assert isinstance(vu, VU)
        assert vu in patch.nodes

    def test_link_simple(self):
        patch = Patcher()
        obj1 = patch.add("osc~ 440")
        obj2 = patch.add("dac~")
        patch.link(obj1, obj2)
        assert len(patch.connections) == 1
        conn = patch.connections[0]
        assert conn.source == 0  # obj1 index
        assert conn.sink == 1  # obj2 index

    def test_link_multiple_inlets(self):
        patch = Patcher()
        obj1 = patch.add("sig~ 1")
        obj2 = patch.add("sig~ 2")
        obj3 = patch.add("*~")
        patch.link(obj1, obj3)
        patch.link(obj2, obj3, inlet=1)
        assert len(patch.connections) == 2

    def test_link_error_source_not_in_patch(self):
        patch1 = Patcher()
        patch2 = Patcher()
        obj1 = patch1.add("test")
        obj2 = patch2.add("test")
        with pytest.raises(NodeNotFoundError):
            patch2.link(obj1, obj2)

    def test_link_error_sink_not_in_patch(self):
        patch1 = Patcher()
        patch2 = Patcher()
        obj1 = patch1.add("source")
        obj2 = patch2.add("sink")
        with pytest.raises(NodeNotFoundError):
            patch1.link(obj1, obj2)

    def test_filename_in_constructor(self):
        patch = Patcher("test.pd")
        assert patch.filename == "test.pd"

    def test_filename_default_none(self):
        patch = Patcher()
        assert patch.filename is None


class TestPatchPositioning:
    """Tests for patch element positioning."""

    def test_first_element_position(self):
        patch = Patcher()
        obj = patch.add("test")
        assert obj.position == (DEFAULT_MARGIN, DEFAULT_MARGIN)

    def test_new_row_positioning(self):
        patch = Patcher()
        obj1 = patch.add("test1")
        obj2 = patch.add("test2", new_row=1)
        # Second object should be below first
        assert obj2.position[1] > obj1.position[1]

    def test_same_row_positioning(self):
        patch = Patcher()
        obj1 = patch.add("test1")
        obj2 = patch.add("test2", new_row=0)
        # Second object should be to the right of first
        assert obj2.position[0] > obj1.position[0]
        # Same y position
        assert obj2.position[1] == obj1.position[1]

    def test_absolute_positioning(self):
        patch = Patcher()
        obj = patch.add("test", x_pos=500, y_pos=300)
        assert obj.position == (500, 300)

    def test_new_col_offset(self):
        patch = Patcher()
        obj1 = patch.add("test1")
        obj2 = patch.add("test2", new_row=1, new_col=2)
        # Should have left margin
        expected_x = obj1.position[0] + 2 * COLUMN_WIDTH
        assert obj2.position[0] == expected_x


class TestPatchOutput:
    """Tests for patch output generation."""

    def test_patch_contains_all_nodes(self):
        patch = Patcher()
        patch.add("osc~ 440")
        patch.add_msg("bang")
        patch.add_float()
        result = str(patch)
        assert "osc~ 440" in result
        assert "#X msg" in result
        assert "#X floatatom" in result

    def test_patch_contains_connections(self):
        patch = Patcher()
        obj1 = patch.add("loadbang")
        obj2 = patch.add_msg("hello")
        patch.link(obj1, obj2)
        result = str(patch)
        assert "#X connect 0 0 1 0" in result

    def test_subpatch_str(self):
        patch = Patcher()
        patch.add("test")
        subpatch_output = patch._subpatch_str()
        # Should not contain canvas header
        assert not subpatch_output.startswith("#N canvas 0 50")
        assert "#X obj" in subpatch_output


class TestExceptionTypes:
    """Tests for custom exception types."""

    def test_connection_error_is_value_error(self):
        assert issubclass(PdConnectionError, ValueError)

    def test_node_not_found_error_is_value_error(self):
        assert issubclass(NodeNotFoundError, ValueError)

    def test_exceptions_exportable(self):
        from py2pd import PdConnectionError, NodeNotFoundError

        assert PdConnectionError is not None
        assert NodeNotFoundError is not None


class TestIntegration:
    """Integration tests for complete patches."""

    def test_simple_synth_patch(self):
        patch = Patcher()

        loadbang = patch.add("loadbang")
        freq_msg = patch.add_msg("440")
        osc = patch.add("osc~")
        mult = patch.add("*~ 0.5")
        dac = patch.add("dac~")

        patch.link(loadbang, freq_msg)
        patch.link(freq_msg, osc)
        patch.link(osc, mult)
        patch.link(mult, dac)
        patch.link(mult, dac, inlet=1)

        result = str(patch)

        # Verify all elements present
        assert "loadbang" in result
        assert "440" in result
        assert "osc~" in result
        assert "*~ 0.5" in result
        assert "dac~" in result

        # Verify connections
        assert "#X connect" in result
        assert result.count("#X connect") == 5

    def test_subpatch_integration(self):
        # Create inner patch
        inner = Patcher()
        inner.add("inlet")
        inner.add("* 2")
        inner.add("outlet")

        # Create outer patch with subpatch
        patch = Patcher()
        num = patch.add("sig~ 100")
        sub = patch.add_subpatch("double", inner)
        dac = patch.add("dac~")

        patch.link(num, sub)
        patch.link(sub, dac)

        result = str(patch)
        assert "pd double" in result
        assert "inlet" in result
        assert "outlet" in result


class TestLayoutManager:
    """Tests for LayoutManager class."""

    def test_default_initialization(self):
        layout = LayoutManager()
        assert layout.row_head is None
        assert layout.row_tail is None
        assert layout.default_margin == DEFAULT_MARGIN
        assert layout.row_height == ROW_HEIGHT
        assert layout.column_width == COLUMN_WIDTH

    def test_custom_initialization(self):
        layout = LayoutManager(default_margin=50, row_height=30, column_width=60)
        assert layout.default_margin == 50
        assert layout.row_height == 30
        assert layout.column_width == 60

    def test_reset(self):
        layout = LayoutManager()
        # Create a node and register it
        node = Obj(100, 100, "test")
        layout.register_node(node, new_row=1, new_col=0, was_absolute=False)
        assert layout.row_head is not None
        assert layout.row_tail is not None

        # Reset should clear anchors
        layout.reset()
        assert layout.row_head is None
        assert layout.row_tail is None

    def test_first_element_position(self):
        layout = LayoutManager()
        pos = layout.compute_position(new_row=1, new_col=0)
        assert pos == (DEFAULT_MARGIN, DEFAULT_MARGIN)

    def test_first_element_custom_margin(self):
        layout = LayoutManager(default_margin=100)
        pos = layout.compute_position(new_row=1, new_col=0)
        assert pos == (100, 100)

    def test_absolute_position_override(self):
        layout = LayoutManager()
        pos = layout.compute_position(new_row=1, new_col=0, x_pos=500, y_pos=300)
        assert pos == (500, 300)

    def test_new_row_positioning(self):
        layout = LayoutManager()
        # Place first node
        node1 = Obj(25, 25, "test1")
        layout.register_node(node1, new_row=1, new_col=0, was_absolute=False)

        # Compute position for next element on new row
        pos = layout.compute_position(new_row=1, new_col=0)
        # Should be below first node
        assert pos[1] > node1.position[1]
        # X should be at same starting position
        assert pos[0] == node1.position[0]

    def test_same_row_positioning(self):
        layout = LayoutManager()
        # Place first node
        node1 = Obj(25, 25, "test1")
        layout.register_node(node1, new_row=1, new_col=0, was_absolute=False)

        # Compute position for next element on same row
        pos = layout.compute_position(new_row=0, new_col=0)
        # Should be to the right of first node
        assert pos[0] > node1.position[0]
        # Y should be same
        assert pos[1] == node1.position[1]

    def test_column_offset(self):
        layout = LayoutManager()
        # Place first node
        node1 = Obj(25, 25, "test1")
        layout.register_node(node1, new_row=1, new_col=0, was_absolute=False)

        # Compute position with column offset
        pos = layout.compute_position(new_row=1, new_col=2)
        expected_x = node1.position[0] + 2 * COLUMN_WIDTH
        assert pos[0] == expected_x

    def test_row_margin_multiplier(self):
        layout = LayoutManager()
        # Place first node
        node1 = Obj(25, 25, "test1")
        layout.register_node(node1, new_row=1, new_col=0, was_absolute=False)

        # Get baseline new row position
        pos_normal = layout.compute_position(new_row=1, new_col=0)

        # Get position with extra row margin (new_row=2 adds one extra row_height)
        pos_extra = layout.compute_position(new_row=2, new_col=0)

        # Extra should be one row_height below normal
        assert pos_extra[1] == pos_normal[1] + ROW_HEIGHT

    def test_register_node_updates_tail(self):
        layout = LayoutManager()
        node1 = Obj(25, 25, "test1")
        node2 = Obj(75, 25, "test2")

        layout.register_node(node1, new_row=1, new_col=0, was_absolute=False)
        assert layout.row_tail is node1

        layout.register_node(node2, new_row=0, new_col=0, was_absolute=False)
        assert layout.row_tail is node2

    def test_register_node_updates_head_on_new_row(self):
        layout = LayoutManager()
        node1 = Obj(25, 25, "test1")
        node2 = Obj(25, 50, "test2")

        layout.register_node(node1, new_row=1, new_col=0, was_absolute=False)
        assert layout.row_head is node1

        # Same row should not update head
        layout.register_node(node2, new_row=0, new_col=0, was_absolute=False)
        assert layout.row_head is node1

        # New row should update head
        node3 = Obj(25, 75, "test3")
        layout.register_node(node3, new_row=1, new_col=0, was_absolute=False)
        assert layout.row_head is node3

    def test_register_node_updates_head_on_new_col(self):
        layout = LayoutManager()
        node1 = Obj(25, 25, "test1")
        layout.register_node(node1, new_row=1, new_col=0, was_absolute=False)

        # new_col > 0 should update head
        node2 = Obj(75, 25, "test2")
        layout.register_node(node2, new_row=0, new_col=1, was_absolute=False)
        assert layout.row_head is node2

    def test_register_node_updates_head_on_absolute(self):
        layout = LayoutManager()
        node1 = Obj(25, 25, "test1")
        layout.register_node(node1, new_row=1, new_col=0, was_absolute=False)

        # Absolute positioning should update head
        node2 = Obj(500, 300, "test2")
        layout.register_node(node2, new_row=0, new_col=0, was_absolute=True)
        assert layout.row_head is node2

    def test_place_node_convenience_method(self):
        layout = LayoutManager()
        node = Obj(0, 0, "test")  # Position will be computed

        pos = layout.place_node(node, new_row=1, new_col=0)

        assert pos == (DEFAULT_MARGIN, DEFAULT_MARGIN)
        assert layout.row_head is node
        assert layout.row_tail is node

    def test_layout_manager_exportable(self):
        from py2pd import LayoutManager

        assert LayoutManager is not None


class TestLayoutManagerWithPatch:
    """Tests for LayoutManager integration with Patch."""

    def test_patch_uses_layout_manager(self):
        patch = Patcher()
        assert hasattr(patch, "layout")
        assert isinstance(patch.layout, LayoutManager)

    def test_patch_with_custom_layout(self):
        custom_layout = LayoutManager(default_margin=100)
        patch = Patcher(layout=custom_layout)
        assert patch.layout is custom_layout

        obj = patch.add("test")
        assert obj.position == (100, 100)

    def test_patch_row_head_property(self):
        patch = Patcher()
        obj = patch.add("test")
        assert patch.row_head is obj
        assert patch.layout.row_head is obj

    def test_patch_row_tail_property(self):
        patch = Patcher()
        obj = patch.add("test")
        assert patch.row_tail is obj
        assert patch.layout.row_tail is obj

    def test_patch_row_head_setter(self):
        patch = Patcher()
        patch.add("test")
        patch.row_head = None
        assert patch.layout.row_head is None

    def test_patch_row_tail_setter(self):
        patch = Patcher()
        patch.add("test")
        patch.row_tail = None
        assert patch.layout.row_tail is None


class TestCustomLayoutManager:
    """Tests for custom LayoutManager subclasses."""

    def test_custom_layout_algorithm(self):
        class GridLayout(LayoutManager):
            """A simple grid layout that ignores relative positioning."""

            def __init__(self, cell_width=100, cell_height=50):
                super().__init__()
                self.cell_width = cell_width
                self.cell_height = cell_height
                self.node_count = 0
                self.columns = 3

            def _compute_relative_position(self, anchor, new_row, new_col):
                # Simple grid: 3 columns, then wrap
                col = self.node_count % self.columns
                row = self.node_count // self.columns
                return (
                    self.default_margin + col * self.cell_width,
                    self.default_margin + row * self.cell_height,
                )

            def register_node(self, node, new_row, new_col, was_absolute):
                super().register_node(node, new_row, new_col, was_absolute)
                self.node_count += 1

        grid = GridLayout(cell_width=100, cell_height=50)
        patch = Patcher(layout=grid)

        # Create 5 nodes - should be in 3x2 grid
        nodes = [patch.add(f"test{i}") for i in range(5)]

        # Check grid positions
        assert nodes[0].position == (25, 25)  # (0, 0)
        assert nodes[1].position == (125, 25)  # (1, 0)
        assert nodes[2].position == (225, 25)  # (2, 0)
        assert nodes[3].position == (25, 75)  # (0, 1)
        assert nodes[4].position == (125, 75)  # (1, 1)


class TestNodeInletOutletCounts:
    """Tests for inlet/outlet count tracking on nodes."""

    def test_obj_default_counts_none(self):
        obj = Obj(0, 0, "test")
        assert obj.num_inlets is None
        assert obj.num_outlets is None

    def test_obj_with_counts(self):
        obj = Obj(0, 0, "osc~", num_inlets=2, num_outlets=1)
        assert obj.num_inlets == 2
        assert obj.num_outlets == 1

    def test_msg_default_counts(self):
        msg = Msg(0, 0, "bang")
        assert msg.num_inlets == 1
        assert msg.num_outlets == 1

    def test_floatatom_default_counts(self):
        fa = Float(0, 0)
        assert fa.num_inlets == 1
        assert fa.num_outlets == 1

    def test_array_counts(self):
        arr = Array("test", 100)
        assert arr.num_inlets == 0
        assert arr.num_outlets == 0

    def test_subpatch_default_counts_none(self):
        inner = Patcher()
        sp = Subpatch(0, 0, "test", inner)
        assert sp.num_inlets is None
        assert sp.num_outlets is None

    def test_subpatch_with_counts(self):
        inner = Patcher()
        sp = Subpatch(0, 0, "test", inner, num_inlets=2, num_outlets=3)
        assert sp.num_inlets == 2
        assert sp.num_outlets == 3


class TestPatchCreateWithCounts:
    """Tests for creating nodes with inlet/outlet counts via Patch."""

    def test_create_obj_with_counts(self):
        patch = Patcher()
        obj = patch.add("osc~ 440", num_inlets=2, num_outlets=1)
        assert obj.num_inlets == 2
        assert obj.num_outlets == 1

    def test_create_subpatch_with_counts(self):
        inner = Patcher()
        patch = Patcher()
        sp = patch.add_subpatch("mysub", inner, num_inlets=1, num_outlets=2)
        assert sp.num_inlets == 1
        assert sp.num_outlets == 2


class TestValidateConnections:
    """Tests for connection validation."""

    def test_valid_connections_no_error(self):
        patch = Patcher()
        osc = patch.add("osc~ 440", num_inlets=2, num_outlets=1)
        dac = patch.add("dac~", num_inlets=2, num_outlets=0)
        patch.link(osc, dac)
        # Should not raise
        errors = patch.validate_connections(check_cycles=False)
        assert errors == []

    def test_invalid_outlet_index(self):
        patch = Patcher()
        patch.add("osc~ 440", num_inlets=2, num_outlets=1)
        # Manually add a bad connection (outlet index 5 on a node with 1 outlet)
        patch.nodes.append(Obj(0, 0, "test"))
        patch.connections.append(Connection(0, 5, 1, 0))  # outlet 5 doesn't exist

        with pytest.raises(InvalidConnectionError) as exc_info:
            patch.validate_connections(check_cycles=False)
        assert "Invalid outlet index 5" in str(exc_info.value)
        assert "has 1 outlets" in str(exc_info.value)

    def test_invalid_inlet_index(self):
        patch = Patcher()
        patch.add("osc~ 440", num_inlets=2, num_outlets=1)
        patch.add("dac~", num_inlets=2, num_outlets=0)
        # Manually add a bad connection (inlet index 5 on a node with 2 inlets)
        patch.connections.append(Connection(0, 0, 1, 5))

        with pytest.raises(InvalidConnectionError) as exc_info:
            patch.validate_connections(check_cycles=False)
        assert "Invalid inlet index 5" in str(exc_info.value)
        assert "has 2 inlets" in str(exc_info.value)

    def test_multiple_errors_reported(self):
        patch = Patcher()
        patch.add("a", num_inlets=1, num_outlets=1)
        patch.add("b", num_inlets=1, num_outlets=1)
        # Add two bad connections
        patch.connections.append(Connection(0, 5, 1, 0))  # bad outlet
        patch.connections.append(Connection(0, 0, 1, 5))  # bad inlet

        with pytest.raises(InvalidConnectionError) as exc_info:
            patch.validate_connections(check_cycles=False)
        assert "Found 2 invalid connection(s)" in str(exc_info.value)

    def test_no_validation_without_counts(self):
        patch = Patcher()
        # Create nodes without specifying counts
        patch.add("a")  # num_inlets/num_outlets = None
        patch.add("b")
        # Add connection with large indices - should pass since no counts specified
        patch.connections.append(Connection(0, 100, 1, 100))
        # Should not raise
        errors = patch.validate_connections(check_cycles=False)
        assert errors == []

    def test_validation_with_msg_default_counts(self):
        patch = Patcher()
        patch.add_msg("hello")  # default: 1 inlet, 1 outlet
        patch.add_msg("world")
        # Add bad connection - msg only has outlet 0
        patch.connections.append(Connection(0, 2, 1, 0))

        with pytest.raises(InvalidConnectionError):
            patch.validate_connections(check_cycles=False)


class TestCycleDetection:
    """Tests for cycle detection in connection graphs."""

    def test_no_cycles(self):
        patch = Patcher()
        a = patch.add("a")
        b = patch.add("b")
        c = patch.add("c")
        patch.link(a, b)
        patch.link(b, c)
        cycles = patch.detect_cycles()
        assert cycles == []

    def test_simple_cycle(self):
        patch = Patcher()
        a = patch.add("a")
        b = patch.add("b")
        patch.link(a, b)
        # Manually create cycle: b -> a (in addition to a -> b)
        patch.connections.append(Connection(1, 0, 0, 0))

        cycles = patch.detect_cycles()
        assert len(cycles) >= 1
        # Cycle should contain both nodes
        cycle_nodes = set()
        for cycle in cycles:
            cycle_nodes.update(cycle)
        assert 0 in cycle_nodes  # node a
        assert 1 in cycle_nodes  # node b

    def test_self_loop(self):
        patch = Patcher()
        patch.add("delwrite~ loop")
        # Self-connection
        patch.connections.append(Connection(0, 0, 0, 0))

        cycles = patch.detect_cycles()
        assert len(cycles) >= 1

    def test_validate_with_cycle_warning(self):
        patch = Patcher()
        a = patch.add("a")
        b = patch.add("b")
        patch.link(a, b)
        # Create cycle
        patch.connections.append(Connection(1, 0, 0, 0))

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            patch.validate_connections(check_cycles=True)
            # Should have issued a CycleWarning
            assert len(w) >= 1
            assert issubclass(w[0].category, CycleWarning)
            assert "Cycle detected" in str(w[0].message)

    def test_validate_no_cycle_warning_when_disabled(self):
        patch = Patcher()
        a = patch.add("a")
        b = patch.add("b")
        patch.link(a, b)
        patch.connections.append(Connection(1, 0, 0, 0))

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            patch.validate_connections(check_cycles=False)
            # Should NOT have any CycleWarning
            cycle_warnings = [x for x in w if issubclass(x.category, CycleWarning)]
            assert len(cycle_warnings) == 0


class TestConnectionStats:
    """Tests for get_connection_stats method."""

    def test_empty_patch(self):
        patch = Patcher()
        stats = patch.get_connection_stats()
        assert stats["total_connections"] == 0
        assert stats["nodes_with_connections"] == 0

    def test_simple_patch(self):
        patch = Patcher()
        a = patch.add("a", num_inlets=1, num_outlets=1)
        b = patch.add("b", num_inlets=1, num_outlets=1)
        c = patch.add("c")  # no counts specified
        patch.link(a, b)
        patch.link(b, c)

        stats = patch.get_connection_stats()
        assert stats["total_connections"] == 2
        assert stats["nodes_with_connections"] == 3
        assert stats["max_outlets_used"] == 0  # outlet 0
        assert stats["max_inlets_used"] == 0  # inlet 0
        # 2 out of 3 nodes have counts specified
        assert stats["validation_coverage"] == pytest.approx(66.7, rel=0.1)

    def test_multiple_inlets_outlets(self):
        patch = Patcher()
        patch.add("a")
        patch.add("b")
        # Connect a[0] -> b[0] and a[1] -> b[2]
        patch.connections.append(Connection(0, 0, 1, 0))
        patch.connections.append(Connection(0, 1, 1, 2))

        stats = patch.get_connection_stats()
        assert stats["max_outlets_used"] == 1
        assert stats["max_inlets_used"] == 2


class TestExceptionTypesNew:
    """Tests for new exception types."""

    def test_invalid_connection_error_is_value_error(self):
        assert issubclass(InvalidConnectionError, ValueError)

    def test_cycle_warning_is_user_warning(self):
        assert issubclass(CycleWarning, UserWarning)

    def test_new_exceptions_exportable(self):
        from py2pd import CycleWarning, InvalidConnectionError

        assert InvalidConnectionError is not None
        assert CycleWarning is not None


class TestValidationIntegration:
    """Integration tests for validation with realistic patches."""

    def test_synth_patch_valid(self):
        patch = Patcher()
        osc = patch.add("osc~ 440", num_inlets=2, num_outlets=1)
        mult = patch.add("*~ 0.5", num_inlets=2, num_outlets=1)
        dac = patch.add("dac~", num_inlets=2, num_outlets=0)
        patch.link(osc, mult)
        patch.link(mult, dac)
        patch.link(mult, dac, inlet=1)

        # Should pass validation
        errors = patch.validate_connections(check_cycles=False)
        assert errors == []

    def test_synth_patch_with_bad_connection(self):
        patch = Patcher()
        patch.add("osc~ 440", num_inlets=2, num_outlets=1)
        patch.add("dac~", num_inlets=2, num_outlets=0)
        # Manually add connection from non-existent outlet
        patch.connections.append(Connection(0, 3, 1, 0))  # osc has only 1 outlet

        with pytest.raises(InvalidConnectionError):
            patch.validate_connections()

    def test_feedback_patch_with_cycle(self):
        patch = Patcher()
        # Create a patch where we'll add a cycle
        # Don't specify num_outlets on the last node so we can test cycle detection
        a = patch.add("a", num_inlets=1, num_outlets=1)
        b = patch.add("b", num_inlets=1, num_outlets=1)
        c = patch.add("c")  # No counts - allows any connection
        patch.link(a, b)
        patch.link(b, c)

        # This is valid (no cycle yet)
        errors = patch.validate_connections(check_cycles=True)
        assert errors == []

        # Now create an actual graph cycle: c -> a
        patch.connections.append(Connection(2, 0, 0, 0))

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Validation should still pass (cycles are allowed) but warn
            patch.validate_connections(check_cycles=True)
            cycle_warnings = [x for x in w if issubclass(x.category, CycleWarning)]
            assert len(cycle_warnings) >= 1


class TestSVGExport:
    """Tests for SVG visualization export."""

    def test_to_svg_empty_patch(self):
        patch = Patcher()
        svg = patch.to_svg()
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_to_svg_single_node(self):
        patch = Patcher()
        patch.add("osc~ 440")
        svg = patch.to_svg()
        assert "<svg" in svg
        assert "<rect" in svg
        assert "osc~ 440" in svg

    def test_to_svg_with_connections(self):
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc, dac)
        svg = patch.to_svg()
        assert '<path class="connection"' in svg
        assert "osc~ 440" in svg
        assert "dac~" in svg

    def test_to_svg_different_node_types(self):
        patch = Patcher()
        patch.add("osc~ 440")
        patch.add_msg("bang")
        patch.add_bang()
        inner = Patcher()
        patch.add_subpatch("sub", inner)
        svg = patch.to_svg()
        # Check that different node types have different classes
        assert "node-msg" in svg
        assert "node-gui" in svg
        assert "node-subpatch" in svg

    def test_to_svg_escapes_special_chars(self):
        patch = Patcher()
        patch.add_msg("1 < 2 & 3 > 0")
        svg = patch.to_svg()
        # XML entities should be escaped
        assert "&lt;" in svg
        assert "&gt;" in svg
        assert "&amp;" in svg

    def test_to_svg_show_labels_false(self):
        patch = Patcher()
        patch.add("osc~ 440")
        svg = patch.to_svg(show_labels=False)
        assert "<rect" in svg
        assert "<text" not in svg

    def test_to_svg_custom_dimensions(self):
        patch = Patcher()
        patch.add("test")
        svg = patch.to_svg(padding=50, node_height=30)
        assert "<svg" in svg
        # Should still produce valid SVG
        assert "</svg>" in svg

    def test_save_svg(self):
        import os
        import tempfile

        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc, dac)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            temp_path = f.name

        try:
            patch.save_svg(temp_path)
            with open(temp_path, "r") as f:
                content = f.read()
            assert "<svg" in content
            assert "osc~ 440" in content
        finally:
            os.unlink(temp_path)

    def test_to_svg_with_hidden_nodes(self):
        patch = Patcher()
        patch.add("osc~ 440")
        patch.add_array("hidden_array", 1024)  # Arrays are hidden
        svg = patch.to_svg()
        assert "osc~ 440" in svg
        # Array should not appear visually (it's hidden)

    def test_add_link_alias(self):
        """Test that add_link works as alias for link."""
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.add_link(osc, dac)  # Using alias
        assert len(patch.connections) == 1


class TestSave:
    """Tests for Patcher.save() method."""

    def test_save_no_filename_raises(self):
        patch = Patcher()
        patch.add("osc~ 440")
        with pytest.raises(ValueError, match="No filename"):
            patch.save()

    def test_save_with_argument(self, tmp_path):
        patch = Patcher()
        patch.add("osc~ 440")
        filepath = tmp_path / "test.pd"
        patch.save(str(filepath))
        content = filepath.read_text()
        assert "#N canvas" in content
        assert "osc~ 440" in content

    def test_save_with_constructor_filename(self, tmp_path):
        filepath = tmp_path / "ctor.pd"
        patch = Patcher(str(filepath))
        patch.add("dac~")
        patch.save()
        content = filepath.read_text()
        assert "#N canvas" in content
        assert "dac~" in content

    def test_save_argument_overrides_constructor(self, tmp_path):
        ctor_path = tmp_path / "ctor.pd"
        arg_path = tmp_path / "arg.pd"
        patch = Patcher(str(ctor_path))
        patch.add("osc~ 440")
        patch.save(str(arg_path))
        assert arg_path.exists()
        assert not ctor_path.exists()
        content = arg_path.read_text()
        assert "osc~ 440" in content


class TestGridLayoutManager:
    """Tests for GridLayoutManager."""

    def test_grid_basic(self):
        from py2pd import GridLayoutManager

        grid = GridLayoutManager(columns=3, cell_width=100, cell_height=50)
        patch = Patcher(layout=grid)

        nodes = [patch.add(f"obj{i}") for i in range(6)]

        # First row: 0, 1, 2
        assert nodes[0].position == (25, 25)
        assert nodes[1].position == (125, 25)
        assert nodes[2].position == (225, 25)
        # Second row: 3, 4, 5
        assert nodes[3].position == (25, 75)
        assert nodes[4].position == (125, 75)
        assert nodes[5].position == (225, 75)

    def test_grid_custom_margin(self):
        from py2pd import GridLayoutManager

        grid = GridLayoutManager(columns=2, margin=50)
        patch = Patcher(layout=grid)

        node = patch.add("test")
        assert node.position == (50, 50)

    def test_grid_absolute_override(self):
        from py2pd import GridLayoutManager

        grid = GridLayoutManager(columns=2)
        patch = Patcher(layout=grid)

        patch.add("obj1")
        node2 = patch.add("obj2", x_pos=500, y_pos=500)  # absolute
        node3 = patch.add("obj3")  # should continue grid

        assert node2.position == (500, 500)
        # node3 should be at position 2 in grid (not 3)
        assert node3.position[0] == grid.default_margin + grid.cell_width

    def test_grid_reset(self):
        from py2pd import GridLayoutManager

        grid = GridLayoutManager(columns=2)

        # Simulate some placements
        grid.node_count = 5
        grid.reset()
        assert grid.node_count == 0

    def test_grid_exportable(self):
        from py2pd import GridLayoutManager

        assert GridLayoutManager is not None


class TestAutoLayout:
    """Tests for auto_layout method."""

    def test_auto_layout_linear_chain(self):
        patch = Patcher()
        # Create nodes in arbitrary order
        dac = patch.add("dac~")
        osc = patch.add("osc~ 440")
        gain = patch.add("*~ 0.5")

        # Connect: osc -> gain -> dac
        patch.link(osc, gain)
        patch.link(gain, dac)

        patch.auto_layout()

        # osc should be at top (depth 0)
        # gain should be in middle (depth 1)
        # dac should be at bottom (depth 2)
        assert osc.position[1] < gain.position[1]
        assert gain.position[1] < dac.position[1]

    def test_auto_layout_parallel_branches(self):
        patch = Patcher()
        source = patch.add("osc~ 440")
        branch1 = patch.add("*~ 0.5")
        branch2 = patch.add("*~ 0.3")
        mixer = patch.add("+~")

        patch.link(source, branch1)
        patch.link(source, branch2)
        patch.link(branch1, mixer)
        patch.link(branch2, mixer)

        patch.auto_layout()

        # source at top
        # branch1 and branch2 at same level
        # mixer at bottom
        assert source.position[1] < branch1.position[1]
        assert branch1.position[1] == branch2.position[1]
        assert branch1.position[1] < mixer.position[1]

    def test_auto_layout_empty_patch(self):
        patch = Patcher()
        patch.auto_layout()  # Should not raise

    def test_auto_layout_no_connections(self):
        patch = Patcher()
        a = patch.add("a")
        b = patch.add("b")
        c = patch.add("c")

        patch.auto_layout()

        # All nodes should be at depth 0 (same row)
        assert a.position[1] == b.position[1] == c.position[1]

    def test_auto_layout_custom_spacing(self):
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc, dac)

        patch.auto_layout(margin=100, row_spacing=80, col_spacing=200)

        assert osc.position == (100, 100)
        assert dac.position == (100, 180)  # margin + row_spacing

    def test_auto_layout_with_hidden_nodes(self):
        patch = Patcher()
        osc = patch.add("osc~ 440")
        patch.add_array("hidden", 1024)  # Hidden node
        dac = patch.add("dac~")
        patch.link(osc, dac)

        patch.auto_layout()  # Should not crash on hidden nodes
        assert osc.position[1] < dac.position[1]

    def test_auto_layout_with_cycle(self):
        """auto_layout must terminate when the graph contains a cycle."""
        patch = Patcher()
        a = patch.add("a")
        b = patch.add("b")
        c = patch.add("c")
        patch.link(a, b)
        patch.link(b, c)
        patch.link(c, a)  # back-edge creating cycle
        patch.auto_layout()  # must not loop forever
        # All nodes should be placed at valid positions
        for node in patch.nodes:
            assert node.position[0] >= 0
            assert node.position[1] >= 0

    def test_auto_layout_self_loop(self):
        """auto_layout must terminate when a node connects to itself."""
        patch = Patcher()
        a = patch.add("delwrite~ loop 1000")
        b = patch.add("delread~ loop 500")
        patch.link(a, b)
        patch.link(b, a)  # feedback loop
        patch.auto_layout()
        assert a.position[0] >= 0
        assert b.position[0] >= 0

    def test_auto_layout_multiple_cycles(self):
        """auto_layout terminates with multiple independent cycles."""
        patch = Patcher()
        a = patch.add("a")
        b = patch.add("b")
        c = patch.add("c")
        d = patch.add("d")
        patch.link(a, b)
        patch.link(b, a)  # cycle 1
        patch.link(c, d)
        patch.link(d, c)  # cycle 2
        patch.auto_layout()
        for node in patch.nodes:
            assert node.position[0] >= 0
            assert node.position[1] >= 0


class TestUnescapeDollar:
    """Tests for the unescape dollar sign fix."""

    def test_unescape_escaped_dollar_mid_string(self):
        """Escaped dollar signs in the middle of a string should be unescaped."""
        result = unescape("hello \\$1 world")
        assert "$1" in result
        assert "\\$" not in result

    def test_unescape_roundtrip_dollar(self):
        """escape() then unescape() should round-trip dollar signs."""
        original = "set $1 value"
        escaped = escape(original)
        unescaped = unescape(escaped)
        assert "$1" in unescaped


class TestComment:
    """Tests for the Comment class."""

    def test_comment_str(self):
        c = Comment(50, 60, "hello world")
        assert str(c) == "#X text 50 60 hello world;\n"

    def test_comment_repr(self):
        c = Comment(50, 60, "hello world")
        assert repr(c) == "Comment(50, 60, 'hello world')"

    def test_comment_no_inlets_outlets(self):
        c = Comment(0, 0, "test")
        assert c.num_inlets == 0
        assert c.num_outlets == 0

    def test_comment_empty_content(self):
        c = Comment(10, 20)
        assert c.parameters["content"] == ""
        assert str(c) == "#X text 10 20 ;\n"


class TestLinkWithOutlet:
    """Tests for link() accepting Node.Outlet objects."""

    def test_link_with_outlet_index_zero(self):
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc[0], dac)
        assert len(patch.connections) == 1
        conn = patch.connections[0]
        assert conn.source == 0
        assert conn.outlet_index == 0
        assert conn.sink == 1
        assert conn.inlet_index == 0

    def test_link_with_outlet_non_zero(self):
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc[1], dac)
        conn = patch.connections[0]
        assert conn.outlet_index == 1

    def test_link_outlet_with_inlet(self):
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc[0], dac, inlet=1)
        conn = patch.connections[0]
        assert conn.outlet_index == 0
        assert conn.inlet_index == 1

    def test_link_outlet_overrides_outlet_kwarg(self):
        """When an Outlet is passed, its index is used (outlet kwarg ignored)."""
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc[2], dac, outlet=99)
        conn = patch.connections[0]
        assert conn.outlet_index == 2

    def test_link_with_node_still_works(self):
        """Passing a plain Node should still work as before."""
        patch = Patcher()
        osc = patch.add("osc~ 440")
        dac = patch.add("dac~")
        patch.link(osc, dac, outlet=0, inlet=1)
        conn = patch.connections[0]
        assert conn.outlet_index == 0
        assert conn.inlet_index == 1


class TestSubpatchAutoInference:
    """Tests for auto-inferring subpatch num_inlets/num_outlets."""

    def test_infer_from_inlet_outlet_objects(self):
        inner = Patcher()
        inner.add("inlet")
        inner.add("outlet")
        patch = Patcher()
        sp = patch.add_subpatch("test", inner)
        assert sp.num_inlets == 1
        assert sp.num_outlets == 1

    def test_infer_multiple_inlets_outlets(self):
        inner = Patcher()
        inner.add("inlet")
        inner.add("inlet~")
        inner.add("outlet")
        inner.add("outlet~")
        inner.add("outlet")
        patch = Patcher()
        sp = patch.add_subpatch("test", inner)
        assert sp.num_inlets == 2
        assert sp.num_outlets == 3

    def test_explicit_override(self):
        inner = Patcher()
        inner.add("inlet")
        inner.add("outlet")
        patch = Patcher()
        sp = patch.add_subpatch("test", inner, num_inlets=5, num_outlets=3)
        assert sp.num_inlets == 5
        assert sp.num_outlets == 3

    def test_no_inlet_outlet_objects(self):
        inner = Patcher()
        inner.add("osc~ 440")
        patch = Patcher()
        sp = patch.add_subpatch("test", inner)
        assert sp.num_inlets == 0
        assert sp.num_outlets == 0

    def test_signal_inlets_outlets(self):
        inner = Patcher()
        inner.add("inlet~")
        inner.add("outlet~")
        patch = Patcher()
        sp = patch.add_subpatch("test", inner)
        assert sp.num_inlets == 1
        assert sp.num_outlets == 1


class TestPdObjectRegistry:
    """Tests for PD_OBJECT_REGISTRY and auto-fill in add()."""

    def test_registry_lookup_osc(self):
        patch = Patcher()
        osc = patch.add("osc~ 440")
        assert osc.num_inlets == 2
        assert osc.num_outlets == 1

    def test_registry_lookup_dac(self):
        patch = Patcher()
        dac = patch.add("dac~")
        assert dac.num_inlets == 2
        assert dac.num_outlets == 0

    def test_registry_unknown_object(self):
        patch = Patcher()
        obj = patch.add("my_custom_external~")
        assert obj.num_inlets is None
        assert obj.num_outlets is None

    def test_registry_explicit_override(self):
        patch = Patcher()
        osc = patch.add("osc~ 440", num_inlets=5, num_outlets=3)
        assert osc.num_inlets == 5
        assert osc.num_outlets == 3

    def test_registry_partial_override(self):
        """Explicit num_inlets overrides registry, num_outlets from registry."""
        patch = Patcher()
        osc = patch.add("osc~ 440", num_inlets=10)
        assert osc.num_inlets == 10
        assert osc.num_outlets == 1  # from registry

    def test_registry_variable_outlets(self):
        """Objects with None (variable) outlets keep None."""
        patch = Patcher()
        t = patch.add("trigger b f")
        assert t.num_inlets == 1
        assert t.num_outlets is None  # variable

    def test_registry_control_math(self):
        patch = Patcher()
        plus = patch.add("+ 5")
        assert plus.num_inlets == 2
        assert plus.num_outlets == 1

    def test_registry_has_expected_entries(self):
        assert "osc~" in PD_OBJECT_REGISTRY
        assert "dac~" in PD_OBJECT_REGISTRY
        assert "loadbang" in PD_OBJECT_REGISTRY
        assert "send" in PD_OBJECT_REGISTRY
        assert "receive" in PD_OBJECT_REGISTRY
