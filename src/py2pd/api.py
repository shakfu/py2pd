from collections import deque
import re
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple, Union
import warnings

# Layout constants (pixels)
ROW_HEIGHT = 25
COLUMN_WIDTH = 50
DEFAULT_MARGIN = 25

# Text display constants
TEXT_WRAP_WIDTH = 60
CHAR_WIDTH = 6
MIN_ELEMENT_WIDTH = 50
ELEMENT_PADDING = 20
LINE_HEIGHT = 15
ELEMENT_BASE_HEIGHT = 10

# Default floatatom dimensions
FLOATATOM_WIDTH = 50
FLOATATOM_HEIGHT = 25

# Default main-canvas geometry written on the "#N canvas" line
CANVAS_X = 0
CANVAS_Y = 50
CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 600
CANVAS_FONT_SIZE = 10


class PdConnectionError(ValueError):
    """Raised when connection arguments are invalid."""

    pass


class NodeNotFoundError(ValueError):
    """Raised when a node is not found in the patch."""

    pass


class InvalidConnectionError(ValueError):
    """Raised when a connection references an invalid inlet or outlet index."""

    pass


class CycleWarning(UserWarning):
    """Warning raised when a connection cycle is detected."""

    pass


class PdConnectionWarning(UserWarning):
    """Warning raised for an out-of-range connection when validation is advisory.

    Issued by ``link()`` when the patch was created with ``validate_links=False``
    -- the connection is still recorded, since the object registry's counts are
    incomplete and PureData may well accept it.
    """

    pass


def _fmt_coord(value: float) -> str:
    """Format a coordinate the way PureData writes it -- integral values as integers."""
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def escape(text: str) -> str:
    """Escape special characters for PureData format."""
    save = re.sub(r"\\", r"\\\\", text)
    save = re.sub(r";", r" \; ", save)
    save = re.sub(r",", r" \, ", save)
    save = re.sub(r"\$(?=[0-9])", r"\$", save)
    return save


def unescape(text: str) -> str:
    """Convert PureData-escaped text into the text PureData displays.

    Escaped semicolons become newlines, escaped commas become commas and
    escaped dollar signs become plain dollar signs -- matching how PureData
    lays a message or comment out on screen.

    This is a display transform, **not** the inverse of :func:`escape`. Two
    differences matter if you were hoping to round-trip through it:

    - ``escape`` turns a semicolon into an escaped one; ``unescape`` turns that
      into a newline, because that is where PureData breaks the line.
    - ``escape`` doubles a backslash; ``unescape`` leaves it doubled.

    Use it to render text for a human. To recover the exact source text, keep
    the escaped form (see the ``escaped`` argument on :class:`Obj`,
    :class:`Msg` and :class:`Comment`).

    Parameters
    ----------
    text : str
        PureData-escaped text

    Returns
    -------
    str
        Text as PureData would display it

    Examples
    --------
    >>> unescape(escape('a, b'))
    'a, b'
    >>> unescape(escape('one; two'))
    'one\ntwo'
    """
    disp = re.sub(r" (?<!\\)\\; ", "\n", text)
    disp = re.sub(r" (?<!\\)\\, ", ",", disp)
    disp = re.sub(r"(?<!\\)\\\$", "$", disp)
    lines = [line.strip() for line in disp.split("\n")]
    return "\n".join(lines)


def get_display_lines(text: str) -> List[str]:
    """Split text into display lines, wrapping at TEXT_WRAP_WIDTH characters."""
    display_text = unescape(text)
    lines: List[str] = []
    # Regex matches up to TEXT_WRAP_WIDTH chars ending at whitespace or end,
    # or exactly TEXT_WRAP_WIDTH chars if no break point found
    wrap_pattern = rf"[ ]*(?:.{{1,{TEXT_WRAP_WIDTH}}}(?:\s|$)|.{{{TEXT_WRAP_WIDTH}}})"
    for line in display_text.splitlines():
        wrapped = re.findall(wrap_pattern, line)
        lines.extend(filter(lambda x: len(x) > 0, map(str.strip, wrapped)))
    return lines


class Node:
    """Represents one element in a PureData patch.

    Supports outlet indexing via node[outlet_index] syntax to create
    connections between elements.

    Attributes
    ----------
    num_inlets : int or None
        Number of inlets this node has. None means unknown/unlimited.
        Used for connection validation.
    num_outlets : int or None
        Number of outlets this node has. None means unknown/unlimited.
        Used for connection validation.
    """

    parameters: Dict[str, Any]
    hidden: bool = False
    num_inlets: Optional[int] = None
    num_outlets: Optional[int] = None

    class Outlet:
        """Reference to a specific outlet of a Node, used for creating connections."""

        owner: "Node"
        index: int

        def __init__(self, owner: "Node", index: int) -> None:
            self.owner = owner
            self.index = index

        def __repr__(self) -> str:
            return f"Outlet({self.owner!r}, {self.index})"

    def __getitem__(self, key: int) -> "Node.Outlet":
        """Get an outlet reference for creating connections.

        Parameters
        ----------
        key : int
            The outlet index (0-based)

        Returns
        -------
        Node.Outlet
            A reference to the specified outlet
        """
        if not isinstance(key, int):
            raise TypeError(f"Outlet index must be int, not {type(key).__name__}")
        if key < 0:
            raise ValueError(f"Outlet index must be non-negative, got {key}")
        if self.num_outlets is not None and key >= self.num_outlets:
            raise ValueError(
                f"Outlet index {key} out of range for {self!r} "
                f"(has {self.num_outlets} outlet{'s' if self.num_outlets != 1 else ''})"
            )
        return Node.Outlet(self, key)

    @property
    def pd_class_name(self) -> Optional[str]:
        """The PureData class name this node is validated as, or None.

        Returns the name a validator should check against a registry of known
        objects -- ``'osc~'``, ``'bng'``, ``'floatatom'``. Returns None for
        nodes that are not object boxes (messages, comments, arrays) and for
        abstractions, whose name refers to a user file rather than a built-in
        class and so cannot be looked up in any registry.
        """
        return None

    @property
    def position(self) -> Tuple[int, int]:
        if self.hidden:
            return (-1, -1)
        return (self.parameters["x_pos"], self.parameters["y_pos"])

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (0, 0)

    def get_next_position(self, new_row: float, new_col: float) -> Tuple[int, int]:
        x_pos, y_pos = self.position
        dx, dy = self.dimensions
        if new_row < 1:
            x_pos += dx
            new_col -= 1
        else:
            y_pos += dy + int(ROW_HEIGHT * (new_row - 1))
        x_pos += max(0, int(COLUMN_WIDTH * new_col))
        return (x_pos, y_pos)


class Obj(Node):
    """A generic PureData object box (``#X obj``).

    Represents any object created with ``#X obj`` in PureData, such as
    ``osc~ 440``, ``+~``, ``dac~``, etc. The object's class and arguments
    are stored as a single text string.

    Parameters
    ----------
    x_pos : int
        X position in patch coordinates
    y_pos : int
        Y position in patch coordinates
    text : str
        Object text (e.g., ``'osc~ 440'``). Will be escaped for the
        PureData file format.
    num_inlets : int, optional
        Number of inlets for connection validation
    num_outlets : int, optional
        Number of outlets for connection validation
    escaped : bool, optional
        Set True when *text* is already in PureData's escaped form -- for
        example text read back out of a parsed patch. The text is then stored
        verbatim instead of being escaped a second time.
    """

    parameters: Dict[str, Any]

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        text: str,
        num_inlets: Optional[int] = None,
        num_outlets: Optional[int] = None,
        *,
        escaped: bool = False,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "text": text if escaped else escape(text),
        }
        self.num_inlets = num_inlets
        self.num_outlets = num_outlets

    def __str__(self) -> str:
        p = self.parameters
        return f"#X obj {p['x_pos']} {p['y_pos']} {p['text']};\n"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Obj({p['x_pos']}, {p['y_pos']}, {p['text']!r})"

    @property
    def pd_class_name(self) -> Optional[str]:
        parts = self.parameters["text"].split()
        return parts[0] if parts else None

    @property
    def dimensions(self) -> Tuple[int, int]:
        display_lines = get_display_lines(self.parameters["text"])
        max_chars = max((len(line) for line in display_lines), default=0)
        x_size = max(MIN_ELEMENT_WIDTH, ELEMENT_PADDING + max_chars * CHAR_WIDTH)
        y_size = ELEMENT_BASE_HEIGHT + LINE_HEIGHT * len(display_lines)
        return (x_size, y_size)


class Msg(Node):
    """A message box (``#X msg``).

    Message boxes in PureData send their contents when clicked or when
    they receive a bang. They can contain literal values, comma-separated
    sequences, and ``$`` argument substitutions.

    Parameters
    ----------
    x_pos : int
        X position in patch coordinates
    y_pos : int
        Y position in patch coordinates
    text : str
        Message content. Will be escaped for the PureData file format.
    num_inlets : int, optional
        Number of inlets (default: 2 -- hot inlet + cold inlet for setting contents)
    num_outlets : int, optional
        Number of outlets (default: 1)
    escaped : bool, optional
        Set True when *text* is already in PureData's escaped form (see
        :class:`Obj`).
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        text: str,
        num_inlets: Optional[int] = 2,
        num_outlets: Optional[int] = 1,
        *,
        escaped: bool = False,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "text": text if escaped else escape(text),
        }
        self.num_inlets = num_inlets
        self.num_outlets = num_outlets

    def __str__(self) -> str:
        p = self.parameters
        return f"#X msg {p['x_pos']} {p['y_pos']} {p['text']};\n"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Msg({p['x_pos']}, {p['y_pos']}, {p['text']!r})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        display_lines = get_display_lines(self.parameters["text"])
        max_chars = max((len(line) for line in display_lines), default=0)
        x_size = max(MIN_ELEMENT_WIDTH, ELEMENT_PADDING + max_chars * CHAR_WIDTH)
        y_size = ELEMENT_BASE_HEIGHT + LINE_HEIGHT * len(display_lines)
        return (x_size, y_size)


class Float(Node):
    """A number box (``#X floatatom``).

    Displays and edits a single floating-point value. Simpler than
    the IEM ``NumberBox`` (nbx) -- does not support logarithmic scaling
    or advanced styling.

    Parameters
    ----------
    x_pos : int
        X position in patch coordinates
    y_pos : int
        Y position in patch coordinates
    width : int
        Display width in characters (default: 5)
    upper_limit : float
        Maximum value; 0 means no limit (default: 0)
    lower_limit : float
        Minimum value; 0 means no limit (default: 0)
    label : str
        Label text (default: ``'-'`` for none)
    receive : str
        Receive symbol for wireless input (default: ``'-'`` for none)
    send : str
        Send symbol for wireless output (default: ``'-'`` for none)
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        width: int = 5,
        upper_limit: float = 0,
        lower_limit: float = 0,
        label: str = "-",
        receive: str = "-",
        send: str = "-",
        num_inlets: Optional[int] = 1,
        num_outlets: Optional[int] = 1,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "width": width,
            "upper_limit": upper_limit,
            "lower_limit": lower_limit,
            "label": label,
            "receive": receive,
            "send": send,
        }
        self.num_inlets = num_inlets
        self.num_outlets = num_outlets

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X floatatom {p['x_pos']} {p['y_pos']} {p['width']} "
            f"{p['upper_limit']} {p['lower_limit']} {p['label']} "
            f"{p['receive']} {p['send']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "floatatom"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Float({p['x_pos']}, {p['y_pos']}, width={p['width']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (FLOATATOM_WIDTH, FLOATATOM_HEIGHT)


class Comment(Node):
    """A comment (``#X text``) -- non-functional text displayed in the patch.

    Parameters
    ----------
    x_pos, y_pos : int
        Position in patch coordinates.
    content : str
        Comment text. Escaped for the PureData file format, so a semicolon or
        comma in the text does not terminate the statement.
    escaped : bool, optional
        Set True when *content* is already in PureData's escaped form, e.g.
        text taken from a parsed patch.
    """

    def __init__(self, x_pos: int, y_pos: int, content: str = "", *, escaped: bool = False) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "content": content if escaped else escape(content),
        }
        self.num_inlets = 0
        self.num_outlets = 0

    def __str__(self) -> str:
        p = self.parameters
        return f"#X text {p['x_pos']} {p['y_pos']} {p['content']};\n"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Comment({p['x_pos']}, {p['y_pos']}, {p['content']!r})"


# Default subpatch canvas dimensions (pixels)
SUBPATCH_CANVAS_WIDTH = 300
SUBPATCH_CANVAS_HEIGHT = 180


class Subpatch(Node):
    """A subpatch (nested patch) within a PureData patch.

    Subpatches have a dual nature:
    1. As a Node in the parent patch with a position (x_pos, y_pos)
    2. As a container holding an inner Patch with its own coordinate system

    Coordinate System Relationship
    ------------------------------
    The subpatch's position (x_pos, y_pos) is in the PARENT patch's coordinate
    system and determines where the subpatch box appears.

    The inner patch (src) has its own INDEPENDENT coordinate system:
    - Starts at (0, 0) in the top-left corner of the subpatch canvas
    - Has its own LayoutManager for positioning elements
    - Uses canvas_width and canvas_height to define its bounds

    When the subpatch is opened in PureData, elements inside are positioned
    relative to the inner canvas, not the parent patch.

    Layout Inheritance
    ------------------
    By default, the inner patch has its own independent LayoutManager.
    Use ``inherit_layout=True`` in ``add_subpatch()`` to copy the parent's
    layout settings (margins, row/column spacing) to the inner patch.

    Examples
    --------
    >>> # Create parent and inner patches
    >>> parent = Patcher()
    >>> inner = Patcher()
    >>> inlet = inner.add('inlet')
    >>> outlet = inner.add('outlet')
    >>> inner.link(inlet, outlet)
    >>>
    >>> # Insert subpatch - position (100, 50) is in parent's coordinates
    >>> # Elements inside use inner's coordinate system
    >>> sp = parent.add_subpatch('mysubpatch', inner, x_pos=100, y_pos=50)

    Attributes
    ----------
    src : Patch
        The inner patch containing the subpatch's elements
    canvas_width : int
        Width of the subpatch canvas in pixels
    canvas_height : int
        Height of the subpatch canvas in pixels
    """

    src: "Patcher"
    canvas_width: int
    canvas_height: int

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        name: str,
        src: "Patcher",
        num_inlets: Optional[int] = None,
        num_outlets: Optional[int] = None,
        canvas_width: int = SUBPATCH_CANVAS_WIDTH,
        canvas_height: int = SUBPATCH_CANVAS_HEIGHT,
        graph_on_parent: bool = False,
        hide_name: bool = False,
        gop_width: int = 85,
        gop_height: int = 60,
        is_graph: bool = False,
        gop_rect: Tuple[float, float, float, float] = (0, 1, 1, 0),
        gop_margins: Optional[Tuple[int, int]] = (0, 0),
    ) -> None:
        """Create a subpatch node.

        Parameters
        ----------
        x_pos : int
            X position in the PARENT patch's coordinate system
        y_pos : int
            Y position in the PARENT patch's coordinate system
        name : str
            Name displayed on the subpatch box (used as 'pd <name>')
        src : Patch
            The inner patch containing subpatch elements. Elements inside
            use their own coordinate system starting at (0, 0).
        num_inlets : int, optional
            Number of inlets (determined by 'inlet' objects inside)
        num_outlets : int, optional
            Number of outlets (determined by 'outlet' objects inside)
        canvas_width : int
            Width of the subpatch canvas (default: 300)
        canvas_height : int
            Height of the subpatch canvas (default: 180)
        graph_on_parent : bool
            If True, GUI elements inside the subpatch are visible in the
            parent patch (default: False)
        hide_name : bool
            If True, hide the subpatch name when graph_on_parent is enabled
            (default: False)
        gop_width : int
            Width of the graph-on-parent viewport in pixels (default: 85)
        gop_height : int
            Height of the graph-on-parent viewport in pixels (default: 60)
        is_graph : bool
            If True, this canvas is closed with ``#X restore <x> <y> graph;``
            rather than ``pd <name>``. That is the form PureData uses for a
            canvas holding an array (default: False)
        gop_rect : tuple of float
            The ``(x_from, y_from, x_to, y_to)`` coordinate range written on the
            ``#X coords`` line (default: ``(0, 1, 1, 0)``)
        gop_margins : tuple of int, optional
            Viewport ``(x, y)`` margins. ``None`` writes the seven-value form of
            ``#X coords``, which PureData also accepts (default: ``(0, 0)``)
        """
        self.src = src
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "name": name,
            "graph_on_parent": graph_on_parent,
            "hide_name": hide_name,
            "gop_width": gop_width,
            "gop_height": gop_height,
            "is_graph": is_graph,
            "gop_rect": gop_rect,
            "gop_margins": gop_margins,
        }
        self.num_inlets = num_inlets
        self.num_outlets = num_outlets

    def __str__(self) -> str:
        p = self.parameters
        coords_line = ""
        if p["graph_on_parent"]:
            # PureData encodes "hide object name and arguments" in the
            # graph-on-parent flag itself: 1 = shown, 2 = hidden. There is no
            # separate field, and the two values after the flag are the
            # viewport margins.
            gop_flag = 2 if p["hide_name"] else 1
            rect = " ".join(_fmt_coord(v) for v in p.get("gop_rect", (0, 1, 1, 0)))
            margins = p.get("gop_margins", (0, 0))
            tail = "" if margins is None else f" {margins[0]} {margins[1]}"
            coords_line = f"#X coords {rect} {p['gop_width']} {p['gop_height']} {gop_flag}{tail};\n"
        restore = (
            f"#X restore {p['x_pos']} {p['y_pos']} graph;\n"
            if p.get("is_graph")
            else f"#X restore {p['x_pos']} {p['y_pos']} pd {p['name']};\n"
        )
        return (
            f"#N canvas 0 0 {self.canvas_width} {self.canvas_height} (subpatch) 0;\n"
            f"{self.src._subpatch_str()}"
            f"{coords_line}"
            f"{restore}"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "pd"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Subpatch({p['x_pos']}, {p['y_pos']}, {p['name']!r})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        p = self.parameters
        if p["graph_on_parent"]:
            return (p["gop_width"], p["gop_height"])
        label_text = "pd " + p["name"]
        x_size = max(MIN_ELEMENT_WIDTH, ELEMENT_PADDING + len(label_text) * CHAR_WIDTH)
        return (x_size, ROW_HEIGHT)


class Abstraction(Obj):
    """Reference to an external .pd file (abstraction).

    In PureData, an abstraction is an object that loads from a .pd file.
    It appears as a regular object box, e.g. [my-synth 440 0.5].

    Parameters
    ----------
    x_pos : int
        X position in patch coordinates
    y_pos : int
        Y position in patch coordinates
    text : str
        Object text (e.g., ``'my-synth 440 0.5'``)
    num_inlets : int, optional
        Number of inlets for connection validation
    num_outlets : int, optional
        Number of outlets for connection validation
    source_path : str, optional
        Path to the .pd file on disk
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        text: str,
        num_inlets: Optional[int] = None,
        num_outlets: Optional[int] = None,
        source_path: Optional[str] = None,
        *,
        escaped: bool = False,
    ) -> None:
        super().__init__(x_pos, y_pos, text, num_inlets, num_outlets, escaped=escaped)
        self._source_path = source_path

    @property
    def name(self) -> str:
        """The abstraction name (first token of text)."""
        text = self.parameters["text"]
        return text.split()[0] if text else ""

    @property
    def source_path(self) -> Optional[str]:
        """Path to the .pd file, if known."""
        return self._source_path

    @property
    def pd_class_name(self) -> Optional[str]:
        """None -- an abstraction names a user file, not a built-in class."""
        return None

    def __repr__(self) -> str:
        p = self.parameters
        return f"Abstraction({p['x_pos']}, {p['y_pos']}, {p['text']!r})"


def _infer_abstraction_io(path: str) -> Tuple[int, int]:
    """Infer inlet/outlet counts from an abstraction's .pd file.

    Parses the file as a PdPatch and counts top-level inlet/inlet~ and
    outlet/outlet~ objects.  Only top-level elements are considered --
    inlets inside subpatches belong to those subpatches.

    Parameters
    ----------
    path : str
        Path to the .pd file

    Returns
    -------
    tuple of (int, int)
        (num_inlets, num_outlets)
    """
    from .ast import PdObj, parse

    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    patch = parse(content)
    num_inlets = 0
    num_outlets = 0
    for elem in patch.elements:
        if isinstance(elem, PdObj):
            if elem.class_name in {"inlet", "inlet~"}:
                num_inlets += 1
            elif elem.class_name in {"outlet", "outlet~"}:
                num_outlets += 1
    return (num_inlets, num_outlets)


class Array(Node):
    """A data array (``#X array``).

    Arrays store sequences of numeric data, typically used for wavetables,
    sample buffers, or lookup tables. They are hidden nodes (not displayed
    in the patch canvas) and have no inlets or outlets.

    Parameters
    ----------
    name : str
        Array name (used to reference the array from other objects)
    length : int
        Number of elements
    element_type : str
        Data type (default: ``'float'``)
    save_flag : int
        If 1, save array contents with the patch (default: 0)
    """

    def __init__(
        self, name: str, length: int, element_type: str = "float", save_flag: int = 0
    ) -> None:
        self.hidden = True
        self.parameters = {
            "name": name,
            "length": length,
            "element_type": element_type,
            "save_flag": save_flag,
        }
        self.num_inlets = 0
        self.num_outlets = 0

    def __str__(self) -> str:
        p = self.parameters
        return f"#X array {p['name']} {p['length']} {p['element_type']} {p['save_flag']};\n"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Array({p['name']!r}, {p['length']})"


# An IEM GUI colour is either a legacy packed negative integer (PureData < 0.47)
# or a hex string such as ``#fcfcfc`` (PureData >= 0.47). Both are accepted and
# written out unchanged.
IemColor = Union[int, str]

# IEM GUI default colors (PureData standard)
IEM_BG_COLOR = -262144  # Gray background
IEM_FG_COLOR = -1  # White foreground
IEM_LABEL_COLOR = -1  # White label
IEM_DEFAULT_SIZE = 15  # Default size for bang/toggle


class Bang(Node):
    """A bang button (bng) - sends a bang message when clicked.

    Bang buttons are the most basic trigger in PureData. They flash briefly
    when activated and send a 'bang' message to connected objects.

    Attributes
    ----------
    size : int
        Width and height in pixels (default: 15)
    hold : int
        Flash hold time in milliseconds (default: 250)
    interrupt : int
        Flash interrupt time in milliseconds (default: 50)
    init : int
        If 1, send bang on load (default: 0)
    send : str
        Send symbol for wireless connection (default: 'empty')
    receive : str
        Receive symbol for wireless connection (default: 'empty')
    label : str
        Label text (default: 'empty')
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        size: int = IEM_DEFAULT_SIZE,
        hold: int = 250,
        interrupt: int = 50,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 17,
        label_y: int = 7,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "size": size,
            "hold": hold,
            "interrupt": interrupt,
            "init": init,
            "send": send,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "fg_color": fg_color,
            "label_color": label_color,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} bng {p['size']} {p['hold']} "
            f"{p['interrupt']} {p['init']} {p['send']} {p['receive']} "
            f"{p['label']} {p['label_x']} {p['label_y']} {p['font']} "
            f"{p['font_size']} {p['bg_color']} {p['fg_color']} {p['label_color']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "bng"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Bang({p['x_pos']}, {p['y_pos']}, size={p['size']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        s = self.parameters["size"]
        return (s, s)


class Toggle(Node):
    """A toggle button (tgl) - stores and outputs 0 or non-zero value.

    Toggle buttons maintain an on/off state. When clicked, they alternate
    between 0 and their default value (typically 1).

    Attributes
    ----------
    size : int
        Width and height in pixels (default: 15)
    init : int
        If 1, output init_value on load (default: 0)
    init_value : int
        Value to output on load if init=1 (default: 0)
    default_value : int
        Value when toggled on (default: 1)
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        size: int = IEM_DEFAULT_SIZE,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 17,
        label_y: int = 7,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: int = 0,
        default_value: int = 1,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "size": size,
            "init": init,
            "send": send,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "fg_color": fg_color,
            "label_color": label_color,
            "init_value": init_value,
            "default_value": default_value,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} tgl {p['size']} {p['init']} "
            f"{p['send']} {p['receive']} {p['label']} "
            f"{p['label_x']} {p['label_y']} {p['font']} {p['font_size']} "
            f"{p['bg_color']} {p['fg_color']} {p['label_color']} "
            f"{p['init_value']} {p['default_value']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "tgl"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Toggle({p['x_pos']}, {p['y_pos']}, size={p['size']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        s = self.parameters["size"]
        return (s, s)


class Symbol(Node):
    """A symbol input box (symbolatom) - displays and edits symbol values.

    Similar to floatatom but for symbol (string) data instead of numbers.
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        width: int = 10,
        lower_limit: float = 0,
        upper_limit: float = 0,
        label_pos: int = 0,
        label: str = "-",
        receive: str = "-",
        send: str = "-",
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "width": width,
            "lower_limit": lower_limit,
            "upper_limit": upper_limit,
            "label_pos": label_pos,
            "label": label,
            "receive": receive,
            "send": send,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X symbolatom {p['x_pos']} {p['y_pos']} {p['width']} "
            f"{p['lower_limit']} {p['upper_limit']} {p['label_pos']} "
            f"{p['label']} {p['receive']} {p['send']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "symbolatom"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Symbol({p['x_pos']}, {p['y_pos']}, width={p['width']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (self.parameters["width"] * CHAR_WIDTH, ROW_HEIGHT)


class NumberBox(Node):
    """IEM GUI number box (nbx) - numeric input with more features than floatatom.

    Unlike floatatom, nbx supports:
    - Logarithmic scaling
    - Different display modes
    - More control over appearance
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        width: int = 5,
        height: int = 14,
        min_val: float = -1e37,
        max_val: float = 1e37,
        log_flag: int = 0,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 0,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: float = 0,
        log_height: int = 256,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "width": width,
            "height": height,
            "min_val": min_val,
            "max_val": max_val,
            "log_flag": log_flag,
            "init": init,
            "send": send,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "fg_color": fg_color,
            "label_color": label_color,
            "init_value": init_value,
            "log_height": log_height,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} nbx {p['width']} {p['height']} "
            f"{p['min_val']} {p['max_val']} {p['log_flag']} {p['init']} "
            f"{p['send']} {p['receive']} {p['label']} "
            f"{p['label_x']} {p['label_y']} {p['font']} {p['font_size']} "
            f"{p['bg_color']} {p['fg_color']} {p['label_color']} "
            f"{p['init_value']} {p['log_height']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "nbx"

    def __repr__(self) -> str:
        p = self.parameters
        return f"NumberBox({p['x_pos']}, {p['y_pos']}, width={p['width']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (self.parameters["width"] * CHAR_WIDTH, self.parameters["height"])


class VSlider(Node):
    """Vertical slider (vsl) - outputs values based on slider position.

    The slider outputs values between min and max as the user drags it.
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        width: int = 15,
        height: int = 128,
        min_val: float = 0,
        max_val: float = 127,
        log_flag: int = 0,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 0,
        label_y: int = -9,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: float = 0,
        steady: int = 1,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "width": width,
            "height": height,
            "min_val": min_val,
            "max_val": max_val,
            "log_flag": log_flag,
            "init": init,
            "send": send,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "fg_color": fg_color,
            "label_color": label_color,
            "init_value": init_value,
            "steady": steady,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} vsl {p['width']} {p['height']} "
            f"{p['min_val']} {p['max_val']} {p['log_flag']} {p['init']} "
            f"{p['send']} {p['receive']} {p['label']} "
            f"{p['label_x']} {p['label_y']} {p['font']} {p['font_size']} "
            f"{p['bg_color']} {p['fg_color']} {p['label_color']} "
            f"{p['init_value']} {p['steady']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "vsl"

    def __repr__(self) -> str:
        p = self.parameters
        return f"VSlider({p['x_pos']}, {p['y_pos']}, {p['width']}x{p['height']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (self.parameters["width"], self.parameters["height"])


class HSlider(Node):
    """Horizontal slider (hsl) - outputs values based on slider position."""

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        width: int = 128,
        height: int = 15,
        min_val: float = 0,
        max_val: float = 127,
        log_flag: int = 0,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = -2,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: float = 0,
        steady: int = 1,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "width": width,
            "height": height,
            "min_val": min_val,
            "max_val": max_val,
            "log_flag": log_flag,
            "init": init,
            "send": send,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "fg_color": fg_color,
            "label_color": label_color,
            "init_value": init_value,
            "steady": steady,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} hsl {p['width']} {p['height']} "
            f"{p['min_val']} {p['max_val']} {p['log_flag']} {p['init']} "
            f"{p['send']} {p['receive']} {p['label']} "
            f"{p['label_x']} {p['label_y']} {p['font']} {p['font_size']} "
            f"{p['bg_color']} {p['fg_color']} {p['label_color']} "
            f"{p['init_value']} {p['steady']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "hsl"

    def __repr__(self) -> str:
        p = self.parameters
        return f"HSlider({p['x_pos']}, {p['y_pos']}, {p['width']}x{p['height']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (self.parameters["width"], self.parameters["height"])


class VRadio(Node):
    """Vertical radio buttons (vradio) - selects one of N options.

    Outputs the index (0 to number-1) of the selected button.
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        size: int = 15,
        new_old: int = 0,
        init: int = 0,
        number: int = 8,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 0,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: int = 0,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "size": size,
            "new_old": new_old,
            "init": init,
            "number": number,
            "send": send,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "fg_color": fg_color,
            "label_color": label_color,
            "init_value": init_value,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} vradio {p['size']} {p['new_old']} "
            f"{p['init']} {p['number']} {p['send']} {p['receive']} {p['label']} "
            f"{p['label_x']} {p['label_y']} {p['font']} {p['font_size']} "
            f"{p['bg_color']} {p['fg_color']} {p['label_color']} {p['init_value']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "vradio"

    def __repr__(self) -> str:
        p = self.parameters
        return f"VRadio({p['x_pos']}, {p['y_pos']}, number={p['number']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        s = self.parameters["size"]
        n = self.parameters["number"]
        return (s, s * n)


class HRadio(Node):
    """Horizontal radio buttons (hradio) - selects one of N options."""

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        size: int = 15,
        new_old: int = 0,
        init: int = 0,
        number: int = 8,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 0,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: int = 0,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "size": size,
            "new_old": new_old,
            "init": init,
            "number": number,
            "send": send,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "fg_color": fg_color,
            "label_color": label_color,
            "init_value": init_value,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} hradio {p['size']} {p['new_old']} "
            f"{p['init']} {p['number']} {p['send']} {p['receive']} {p['label']} "
            f"{p['label_x']} {p['label_y']} {p['font']} {p['font_size']} "
            f"{p['bg_color']} {p['fg_color']} {p['label_color']} {p['init_value']};\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "hradio"

    def __repr__(self) -> str:
        p = self.parameters
        return f"HRadio({p['x_pos']}, {p['y_pos']}, number={p['number']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        s = self.parameters["size"]
        n = self.parameters["number"]
        return (s * n, s)


class Canvas(Node):
    """Canvas/background (cnv) - decorative rectangle for grouping objects.

    Canvas objects are purely visual - they have no audio function.
    Useful for organizing patches visually with colored backgrounds.
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        size: int = 15,
        width: int = 100,
        height: int = 60,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 20,
        label_y: int = 12,
        font: int = 0,
        font_size: int = 14,
        bg_color: IemColor = -233017,
        label_color: IemColor = IEM_LABEL_COLOR,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "size": size,
            "width": width,
            "height": height,
            "send": send,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "label_color": label_color,
        }
        self.num_inlets = 1
        self.num_outlets = 1

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} cnv {p['size']} {p['width']} "
            f"{p['height']} {p['send']} {p['receive']} {p['label']} "
            f"{p['label_x']} {p['label_y']} {p['font']} {p['font_size']} "
            f"{p['bg_color']} {p['label_color']} 0;\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "cnv"

    def __repr__(self) -> str:
        p = self.parameters
        return f"Canvas({p['x_pos']}, {p['y_pos']}, {p['width']}x{p['height']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (self.parameters["width"], self.parameters["height"])


class VU(Node):
    """VU meter (vu) - displays audio level.

    Receives RMS level on inlet 0 and peak level on inlet 1.
    No outlets - purely for display.
    """

    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        width: int = 15,
        height: int = 120,
        receive: str = "empty",
        label: str = "empty",
        label_x: int = -1,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        scale: int = 1,
    ) -> None:
        self.parameters = {
            "x_pos": x_pos,
            "y_pos": y_pos,
            "width": width,
            "height": height,
            "receive": receive,
            "label": label,
            "label_x": label_x,
            "label_y": label_y,
            "font": font,
            "font_size": font_size,
            "bg_color": bg_color,
            "label_color": label_color,
            "scale": scale,
        }
        self.num_inlets = 2  # RMS and peak
        self.num_outlets = 0

    def __str__(self) -> str:
        p = self.parameters
        return (
            f"#X obj {p['x_pos']} {p['y_pos']} vu {p['width']} {p['height']} "
            f"{p['receive']} {p['label']} "
            f"{p['label_x']} {p['label_y']} {p['font']} {p['font_size']} "
            f"{p['bg_color']} {p['label_color']} {p['scale']} 0;\n"
        )

    @property
    def pd_class_name(self) -> Optional[str]:
        return "vu"

    def __repr__(self) -> str:
        p = self.parameters
        return f"VU({p['x_pos']}, {p['y_pos']}, {p['width']}x{p['height']})"

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (self.parameters["width"], self.parameters["height"])


# Pd object registry: maps class names to (num_inlets, num_outlets).
# None means unknown -- connection validation is skipped for that end.
#
# The counts below were measured against Pd 0.55 by generating probe patches
# and reading back which "connection failed" errors Pd reported, rather than
# transcribed from memory.  Classes whose arity depends on creation arguments
# (dac~, trigger, pack, route, ...) are not expressible as a fixed pair; those
# live in PD_OBJECT_IO_RULES below and are resolved by lookup_object_io().
PD_OBJECT_REGISTRY: Dict[str, Tuple[Optional[int], Optional[int]]] = {
    # Audio oscillators/sources
    "osc~": (2, 1),
    "phasor~": (2, 1),
    "noise~": (1, 1),
    "tabosc4~": (2, 1),
    # Audio math
    "+~": (2, 1),
    "-~": (2, 1),
    "*~": (2, 1),
    "/~": (2, 1),
    "clip~": (3, 1),
    "wrap~": (1, 1),
    "abs~": (1, 1),
    "sqrt~": (1, 1),
    # Audio filters
    "lop~": (2, 1),
    "hip~": (2, 1),
    "bp~": (3, 1),
    "vcf~": (3, 2),
    # Audio I/O
    "line~": (2, 1),
    "vline~": (3, 1),
    "env~": (1, 1),
    "threshold~": (2, 2),
    # Audio delay
    "delwrite~": (1, 0),
    "delread~": (1, 1),
    "delread4~": (1, 1),
    "vd~": (1, 1),
    # Audio tables
    "tabread~": (1, 1),
    "tabread4~": (2, 1),
    "tabwrite~": (1, 0),
    "tabsend~": (1, 0),
    "tabreceive~": (1, 1),
    # Control math
    "+": (2, 1),
    "-": (2, 1),
    "*": (2, 1),
    "/": (2, 1),
    "mod": (2, 1),
    "div": (2, 1),
    "pow": (2, 1),
    "abs": (1, 1),
    "sqrt": (1, 1),
    "min": (2, 1),
    "max": (2, 1),
    "random": (2, 1),
    # Control comparison
    "==": (2, 1),
    "!=": (2, 1),
    ">": (2, 1),
    "<": (2, 1),
    ">=": (2, 1),
    "<=": (2, 1),
    "&&": (2, 1),
    "||": (2, 1),
    # Control routing
    "spigot": (2, 1),
    "swap": (2, 2),
    "moses": (2, 2),
    # Control time
    "delay": (2, 1),
    "metro": (2, 1),
    "timer": (2, 1),
    "pipe": (None, None),
    "line": (3, 1),
    # Control data
    "float": (2, 1),
    "f": (2, 1),
    "int": (2, 1),
    "i": (2, 1),
    "symbol": (2, 1),
    "value": (1, 1),
    "v": (1, 1),
    # Control I/O
    "send": (1, 0),
    "s": (1, 0),
    "receive": (0, 1),
    "r": (0, 1),
    "throw~": (1, 0),
    "catch~": (1, 1),
    "send~": (1, 0),
    "s~": (1, 0),
    "receive~": (1, 1),
    "r~": (1, 1),
    # Misc control
    "bang": (1, 1),
    "loadbang": (0, 1),
    "print": (1, 0),
    "inlet": (0, 1),
    "outlet": (1, 0),
    "inlet~": (0, 2),
    "outlet~": (1, 0),
    "change": (1, 1),
    "stripnote": (2, 2),
    "makenote": (3, 2),
    "tabread": (1, 1),
    "tabwrite": (2, 0),
    # MIDI
    "notein": (0, 3),
    "noteout": (3, 0),
    "ctlin": (0, 3),
    "ctlout": (3, 0),
    "bendin": (0, 2),
    "bendout": (2, 0),
    "midiin": (0, 2),
    "midiout": (2, 0),
}


IoRule = Callable[[Tuple[str, ...]], Tuple[Optional[int], Optional[int]]]


def _io_dac(args: Tuple[str, ...]) -> Tuple[Optional[int], Optional[int]]:
    """[dac~] takes one inlet per named channel, or two when unnamed."""
    return (len(args) or 2, 0)


def _io_adc(args: Tuple[str, ...]) -> Tuple[Optional[int], Optional[int]]:
    """[adc~] takes one outlet per named channel, or two when unnamed."""
    return (1, len(args) or 2)


def _io_trigger(args: Tuple[str, ...]) -> Tuple[Optional[int], Optional[int]]:
    """[trigger]/[t] has one outlet per type argument (two when bare)."""
    return (1, len(args) or 2)


def _io_pack(args: Tuple[str, ...]) -> Tuple[Optional[int], Optional[int]]:
    """[pack] has one inlet per element (two when bare)."""
    return (len(args) or 2, 1)


def _io_unpack(args: Tuple[str, ...]) -> Tuple[Optional[int], Optional[int]]:
    """[unpack] has one outlet per element (two when bare)."""
    return (1, len(args) or 2)


def _io_select(args: Tuple[str, ...]) -> Tuple[Optional[int], Optional[int]]:
    """[select]/[route] -- a single test value keeps the right inlet."""
    if len(args) <= 1:
        return (2, 2)
    return (1, len(args) + 1)


_LIST_METHOD_IO: Dict[str, Tuple[Optional[int], Optional[int]]] = {
    "append": (2, 1),
    "prepend": (2, 1),
    "split": (2, 3),
    "trim": (1, 1),
    "length": (1, 1),
    "store": (2, 2),
    "fromsymbol": (1, 1),
    "tosymbol": (1, 1),
}


def _io_list(args: Tuple[str, ...]) -> Tuple[Optional[int], Optional[int]]:
    """[list <method>] -- arity depends on the method selector."""
    method = args[0] if args else "append"
    return _LIST_METHOD_IO.get(method, (None, None))


# Classes whose inlet/outlet counts depend on their creation arguments.
PD_OBJECT_IO_RULES: Dict[str, IoRule] = {
    "dac~": _io_dac,
    "adc~": _io_adc,
    "trigger": _io_trigger,
    "t": _io_trigger,
    "pack": _io_pack,
    "unpack": _io_unpack,
    "select": _io_select,
    "sel": _io_select,
    "route": _io_select,
    "list": _io_list,
}


def lookup_object_io(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Resolve the inlet/outlet counts for an object from its full text.

    Parameters
    ----------
    text : str
        Object text including creation arguments, e.g. ``'dac~ 1 2 3 4'``.

    Returns
    -------
    tuple of (int or None, int or None)
        ``(num_inlets, num_outlets)``. ``None`` for either element means the
        count is unknown and connection validation should be skipped for that
        end -- which is the case for every object not in the registry, including
        all externals and abstractions.
    """
    parts = text.split()
    if not parts:
        return (None, None)
    class_name = parts[0]
    rule = PD_OBJECT_IO_RULES.get(class_name)
    if rule is not None:
        return rule(tuple(parts[1:]))
    return PD_OBJECT_REGISTRY.get(class_name, (None, None))


# Types that are never removed by optimize() -- they either have side effects
# (send/receive, loadbang), carry user-visible information (Comment, Msg, GUI),
# or encapsulate sub-graphs that may use wireless connections internally.
_PROTECTED_TYPES = (
    Comment,
    Subpatch,
    Abstraction,
    Array,
    Msg,
    Bang,
    Toggle,
    Symbol,
    NumberBox,
    VSlider,
    HSlider,
    VRadio,
    HRadio,
    Canvas,
    VU,
    Float,
)

# Default/inactive values for send/receive parameters across Pd object types.
_SEND_RECEIVE_INACTIVE = frozenset({"empty", "-", ""})

# Object classes that do their job without any patch cords attached, so
# "disconnected" says nothing about whether they are used. Removing one of
# these changes what the patch does:
#
#   inlet/outlet   define the enclosing subpatch's own inlets and outlets
#   table/array    declare storage other objects address by name
#   text/struct    declare data structures addressed by name
#   block~/switch~ configure the canvas's block size and DSP switching
#   declare/import set the patch's search path and libraries
#   namecanvas     names the canvas for messages sent to it
#   pd~            runs a subprocess
_STRUCTURAL_OBJECTS = frozenset(
    {
        "inlet",
        "inlet~",
        "outlet",
        "outlet~",
        "table",
        "array",
        "text",
        "struct",
        "block~",
        "switch~",
        "declare",
        "import",
        "namecanvas",
        "pd~",
    }
)


def _resolve_bypasses(
    bypass: Dict[int, Tuple["Connection", "Connection"]],
) -> List["Connection"]:
    """Turn per-node bypass pairs into direct predecessor-to-successor connections.

    *bypass* maps the index of each node being collapsed to its single incoming
    and single outgoing connection. A chain of adjacent collapsed nodes
    (``a -> p1 -> p2 -> b``) must yield one connection ``a -> b``, so each end is
    walked through any further collapsed nodes until it reaches a surviving one.

    Parameters
    ----------
    bypass : dict
        Node index -> (incoming connection, outgoing connection).

    Returns
    -------
    list of Connection
        One connection per collapsed chain. Chains that form a closed cycle of
        collapsed nodes yield nothing, since no surviving endpoint exists.
    """
    results: List[Connection] = []
    for idx, (inc, out) in bypass.items():
        # Only start from the head of a chain: if this node's predecessor is
        # itself being collapsed, the head will emit the connection instead.
        if inc.source in bypass:
            continue

        # Walk forward through collapsed nodes to the first survivor.
        sink, inlet_index = out.sink, out.inlet_index
        seen: Set[int] = {idx}
        while sink in bypass and sink not in seen:
            seen.add(sink)
            next_out = bypass[sink][1]
            sink, inlet_index = next_out.sink, next_out.inlet_index
        if sink in bypass:
            continue  # cycle of collapsed nodes -- nothing survives to connect

        results.append(Connection(inc.source, inc.outlet_index, sink, inlet_index))
    return results


def _has_active_send_receive(node: Node) -> bool:
    """Return True if *node* has a send or receive parameter set to a non-default value."""
    params = node.parameters
    for key in ("send", "receive"):
        val = params.get(key)
        if val is not None and val not in _SEND_RECEIVE_INACTIVE:
            return True
    return False


class Connection:
    """A connection (patch cord) between two nodes.

    Connections are stored as index-based references into the parent
    patch's node list. They map directly to ``#X connect`` lines in
    the PureData file format.

    Parameters
    ----------
    source : int
        Index of the source node in the patch's node list
    outlet_index : int
        Outlet index on the source node (0-based)
    sink : int
        Index of the sink node in the patch's node list
    inlet_index : int
        Inlet index on the sink node (0-based)
    """

    source: int
    outlet_index: int
    sink: int
    inlet_index: int

    def __init__(self, source: int, outlet_index: int, sink: int, inlet_index: int) -> None:
        self.source = source
        self.outlet_index = outlet_index
        self.sink = sink
        self.inlet_index = inlet_index

    def __str__(self) -> str:
        return f"#X connect {self.source} {self.outlet_index} {self.sink} {self.inlet_index};\n"

    def __repr__(self) -> str:
        return f"Connection({self.source}, {self.outlet_index}, {self.sink}, {self.inlet_index})"


OutletList = Union[Node.Outlet, Sequence[Node.Outlet]]


class LayoutManager:
    """Manages automatic positioning of elements in a patch.

    The layout manager tracks the current row state and computes positions
    for new elements based on relative positioning parameters (new_row, new_col)
    or allows absolute positioning to override.

    This class can be subclassed to implement different layout algorithms.

    Attributes
    ----------
    row_head : Node or None
        The first node of the current row (used as anchor for new rows)
    row_tail : Node or None
        The last node of the current row (used as anchor for same-row placement)
    default_margin : int
        Default margin from canvas edge for first element
    row_height : int
        Base height added between rows
    column_width : int
        Base width used for column offset calculations
    """

    row_head: Optional[Node]
    row_tail: Optional[Node]

    def __init__(
        self,
        default_margin: int = DEFAULT_MARGIN,
        row_height: int = ROW_HEIGHT,
        column_width: int = COLUMN_WIDTH,
    ) -> None:
        """Initialize the layout manager.

        Parameters
        ----------
        default_margin : int
            Margin from canvas edge for first element (default: 25)
        row_height : int
            Base height between rows (default: 25)
        column_width : int
            Base width for column offsets (default: 50)
        """
        self.row_head = None
        self.row_tail = None
        self.default_margin = default_margin
        self.row_height = row_height
        self.column_width = column_width

    def reset(self) -> None:
        """Reset layout state, clearing row anchors."""
        self.row_head = None
        self.row_tail = None

    def compute_position(
        self, new_row: float, new_col: float, x_pos: int = -1, y_pos: int = -1
    ) -> Tuple[int, int]:
        """Compute the position for a new element.

        Parameters
        ----------
        new_row : float
            0 to continue current row, 1 to start new row.
            Values > 1 add additional top margin.
        new_col : float
            0 to keep current baseline, values > 0 add left margin.
        x_pos : int
            Absolute x position (-1 to use relative positioning)
        y_pos : int
            Absolute y position (-1 to use relative positioning)

        Returns
        -------
        tuple of (int, int)
            The computed (x, y) position
        """
        # Absolute positioning overrides relative
        if x_pos >= 0 and y_pos >= 0:
            return (x_pos, y_pos)

        # Determine anchor node based on whether starting new row
        if new_row < 1:
            anchor = self.row_tail
        else:
            anchor = self.row_head

        # First element or no anchor - use default margin
        if anchor is None:
            return (self.default_margin, self.default_margin)

        # Calculate position relative to anchor
        return self._compute_relative_position(anchor, new_row, new_col)

    def _compute_relative_position(
        self, anchor: Node, new_row: float, new_col: float
    ) -> Tuple[int, int]:
        """Compute position relative to an anchor node.

        This method can be overridden in subclasses to implement
        different layout algorithms.

        Parameters
        ----------
        anchor : Node
            The node to position relative to
        new_row : float
            Row offset parameter
        new_col : float
            Column offset parameter

        Returns
        -------
        tuple of (int, int)
            The computed (x, y) position
        """
        x_pos, y_pos = anchor.position
        dx, dy = anchor.dimensions

        if new_row < 1:
            # Continue on same row - position to the right
            x_pos += dx
            new_col -= 1
        else:
            # New row - position below with optional extra margin
            y_pos += dy + int(self.row_height * (new_row - 1))

        # Apply column offset
        x_pos += max(0, int(self.column_width * new_col))

        return (x_pos, y_pos)

    def register_node(self, node: Node, new_row: float, new_col: float, was_absolute: bool) -> None:
        """Register a node after placement, updating layout state.

        Parameters
        ----------
        node : Node
            The node that was just placed
        new_row : float
            The new_row parameter used for placement
        new_col : float
            The new_col parameter used for placement
        was_absolute : bool
            Whether absolute positioning was used
        """
        self.row_tail = node

        # Update row_head if:
        # - Using absolute positioning
        # - First node (row_head is None)
        # - Starting a new column (new_col > 0)
        # - Starting a new row (new_row >= 1)
        if was_absolute or self.row_head is None or new_col > 0 or new_row >= 1:
            self.row_head = node

    def place_node(
        self,
        node: Node,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
    ) -> Tuple[int, int]:
        """Compute position for a node and register it.

        This is a convenience method that combines compute_position
        and register_node. Note: this does NOT update the node's position,
        it only computes where it should go and updates layout state.

        Parameters
        ----------
        node : Node
            The node to place (used for registering after placement)
        new_row : float
            Row positioning parameter
        new_col : float
            Column positioning parameter
        x_pos : int
            Absolute x position (-1 for relative)
        y_pos : int
            Absolute y position (-1 for relative)

        Returns
        -------
        tuple of (int, int)
            The computed position
        """
        was_absolute = x_pos >= 0 and y_pos >= 0
        position = self.compute_position(new_row, new_col, x_pos, y_pos)
        self.register_node(node, new_row, new_col, was_absolute)
        return position


class GridLayoutManager(LayoutManager):
    """A layout manager that places nodes in a grid pattern.

    Nodes are placed left-to-right, wrapping to a new row after
    reaching the specified number of columns.

    Example
    -------
    >>> grid = GridLayoutManager(columns=4, cell_width=100, cell_height=40)
    >>> p = Patcher(layout=grid)
    >>> for i in range(8):
    ...     p.add(f'obj{i}')  # Creates 2 rows of 4 objects

    Parameters
    ----------
    columns : int
        Number of columns before wrapping to next row (default: 4)
    cell_width : int
        Width of each grid cell (default: 100)
    cell_height : int
        Height of each grid cell (default: 40)
    margin : int
        Margin from canvas edge (default: 25)
    """

    def __init__(
        self,
        columns: int = 4,
        cell_width: int = 100,
        cell_height: int = 40,
        margin: int = DEFAULT_MARGIN,
    ) -> None:
        super().__init__(default_margin=margin)
        self.columns = columns
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.node_count = 0

    def reset(self) -> None:
        """Reset layout state."""
        super().reset()
        self.node_count = 0

    def compute_position(
        self, new_row: float, new_col: float, x_pos: int = -1, y_pos: int = -1
    ) -> Tuple[int, int]:
        """Compute grid position, ignoring new_row/new_col parameters."""
        # Absolute positioning still works
        if x_pos >= 0 and y_pos >= 0:
            return (x_pos, y_pos)

        col = self.node_count % self.columns
        row = self.node_count // self.columns
        return (
            self.default_margin + col * self.cell_width,
            self.default_margin + row * self.cell_height,
        )

    def register_node(self, node: Node, new_row: float, new_col: float, was_absolute: bool) -> None:
        """Register node and increment counter."""
        super().register_node(node, new_row, new_col, was_absolute)
        if not was_absolute:
            self.node_count += 1


class Patcher:
    """Represents a PureData patch, stores its nodes and connections.

    Example
    -------
    >>> p = Patcher('my-patch.pd')
    >>> osc = p.add('osc~ 440')
    >>> gain = p.add('*~ 0.5')
    >>> dac = p.add('dac~')
    >>> p.link(osc, gain)
    >>> p.link(gain, dac)
    >>> p.link(gain, dac, inlet=1)  # stereo
    >>> p.save()

    Attributes
    ----------
    filename : str or None
        Default filename for save()
    nodes : list of Node
        All nodes in the patch
    connections : list of Connection
        All connections between nodes
    layout : LayoutManager
        Manages automatic element positioning
    """

    filename: Optional[str]
    nodes: List[Node]
    connections: List[Connection]
    layout: LayoutManager
    validate_links: bool

    def __init__(
        self,
        filename: Optional[str] = None,
        layout: Optional[LayoutManager] = None,
        *,
        validate_links: bool = True,
        canvas_x: int = CANVAS_X,
        canvas_y: int = CANVAS_Y,
        canvas_width: int = CANVAS_WIDTH,
        canvas_height: int = CANVAS_HEIGHT,
        font_size: int = CANVAS_FONT_SIZE,
    ) -> None:
        """Initialize a new patch.

        Parameters
        ----------
        filename : str, optional
            Default filename for save(). Can be overridden in save().
        layout : LayoutManager, optional
            Custom layout manager. If None, creates a default LayoutManager.
        validate_links : bool, optional
            When True (default), ``link()`` raises ``PdConnectionError`` for an
            outlet or inlet index outside the node's known range. Set False to
            warn instead. Reading an existing patch uses False, because the
            object registry cannot know the arity of externals, abstractions,
            or objects it has no entry for, and a patch that PureData accepts
            must still be representable.
        canvas_x, canvas_y : int, optional
            Window position written on the ``#N canvas`` line.
        canvas_width, canvas_height : int, optional
            Window size written on the ``#N canvas`` line.
        font_size : int, optional
            Patch font size written on the ``#N canvas`` line (default: 10).
        """
        self.filename = filename
        self.nodes = []
        self.connections = []
        self.layout = layout if layout is not None else LayoutManager()
        self.validate_links = validate_links
        self.canvas_x = canvas_x
        self.canvas_y = canvas_y
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.font_size = font_size
        self._node_positions: Dict[int, int] = {}

    @property
    def row_head(self) -> Optional[Node]:
        """First node of current row."""
        return self.layout.row_head

    @row_head.setter
    def row_head(self, value: Optional[Node]) -> None:
        self.layout.row_head = value

    @property
    def row_tail(self) -> Optional[Node]:
        """Last node of current row."""
        return self.layout.row_tail

    @row_tail.setter
    def row_tail(self, value: Optional[Node]) -> None:
        self.layout.row_tail = value

    def _register(self, node: Node, pos_update: Optional[Callable[[Node], None]] = None) -> None:
        """Add *node* to the patch and update layout state.

        Every ``add_*`` method funnels through here, which gives subclasses a
        single place to inspect or reject nodes. ``HeavyPatcher`` uses it to
        enforce the hvcc object subset across all of them rather than only
        ``add()``.

        Parameters
        ----------
        node : Node
            The node to add.
        pos_update : callable, optional
            Layout callback returned by ``_resolve_position()``. Omitted for
            hidden nodes that take no part in layout.
        """
        self._node_positions[id(node)] = len(self.nodes)
        self.nodes.append(node)
        if pos_update is not None:
            pos_update(node)

    def _resolve_position(
        self, x_pos: int, y_pos: int, new_row: float, new_col: float
    ) -> Tuple[int, int, Callable[[Node], None]]:
        """Resolve position for a new element."""
        was_absolute = x_pos >= 0 and y_pos >= 0
        computed_x, computed_y = self.layout.compute_position(new_row, new_col, x_pos, y_pos)

        def position_update(node: Node) -> None:
            self.layout.register_node(node, new_row, new_col, was_absolute)

        return (computed_x, computed_y, position_update)

    def add(
        self,
        text: str,
        *,
        source_path: Optional[str] = None,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        num_inlets: Optional[int] = None,
        num_outlets: Optional[int] = None,
        escaped: bool = False,
    ) -> Obj:
        """Add an object to the patch.

        Parameters
        ----------
        text : str
            The object text (e.g., 'osc~ 440', 'dac~', '+')

        source_path : str, optional
            Path to an abstraction's .pd file. When provided, creates
            an ``Abstraction`` instead of a plain ``Obj`` and infers
            inlet/outlet counts from the file (unless overridden).

        new_row : float, optional
            0 to continue current row, 1 to start new row (default).
            Values > 1 add extra top margin.

        new_col : float, optional
            0 to continue from last object, values > 0 add left margin.

        x_pos : int, optional
            Absolute x position. Overrides new_row/new_col if >= 0.

        y_pos : int, optional
            Absolute y position. Overrides new_row/new_col if >= 0.

        num_inlets : int, optional
            Number of inlets for connection validation.

        num_outlets : int, optional
            Number of outlets for connection validation.

        escaped : bool, optional
            Set True when *text* is already in PureData's escaped form, e.g.
            text taken from a parsed patch. Prevents double-escaping.

        Returns
        -------
        Obj
            The created object (or ``Abstraction`` if *source_path* given)

        Example
        -------
        >>> p = Patcher()
        >>> osc = p.add('osc~ 440')
        >>> dac = p.add('dac~')
        >>> p.link(osc, dac)
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)

        if source_path is not None:
            # Abstraction: infer I/O from the .pd file when not given
            if num_inlets is None or num_outlets is None:
                inferred_in, inferred_out = _infer_abstraction_io(source_path)
                if num_inlets is None:
                    num_inlets = inferred_in
                if num_outlets is None:
                    num_outlets = inferred_out
            node: Obj = Abstraction(
                x_pos, y_pos, text, num_inlets, num_outlets, source_path, escaped=escaped
            )
        else:
            node = Obj(x_pos, y_pos, text, num_inlets, num_outlets, escaped=escaped)
            # Auto-fill inlet/outlet counts from registry if not explicitly given
            if num_inlets is None or num_outlets is None:
                reg_in, reg_out = lookup_object_io(text)
                if num_inlets is None:
                    node.num_inlets = reg_in
                if num_outlets is None:
                    node.num_outlets = reg_out

        self._register(node, pos_update)
        return node

    def add_msg(
        self,
        text: str,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        escaped: bool = False,
    ) -> Msg:
        """Add a message box to the patch.

        Parameters
        ----------
        text : str
            The message content
        escaped : bool, optional
            Set True when *text* is already in PureData's escaped form, e.g.
            text taken from a parsed patch. Prevents double-escaping.

        Returns
        -------
        Msg
            The created message box
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Msg(x_pos, y_pos, text, escaped=escaped)
        self._register(node, pos_update)
        return node

    def add_comment(
        self,
        text: str,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        escaped: bool = False,
    ) -> Comment:
        """Add a comment to the patch.

        Parameters
        ----------
        text : str
            The comment text. Semicolons and commas are escaped, so they
            display as written rather than ending the statement.
        escaped : bool, optional
            Set True when *text* is already in PureData's escaped form.

        Returns
        -------
        Comment
            The created comment

        Example
        -------
        >>> p = Patcher()
        >>> p.add_comment('gain stage; adjust to taste')
        Comment(25, 25, 'gain stage \\\\;  adjust to taste')
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Comment(x_pos, y_pos, text, escaped=escaped)
        self._register(node, pos_update)
        return node

    def add_float(
        self,
        *,
        width: int = 5,
        upper_limit: float = 0,
        lower_limit: float = 0,
        label: str = "-",
        receive: str = "-",
        send: str = "-",
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
    ) -> Float:
        """Add a number box (floatatom) to the patch.

        Parameters
        ----------
        width : int
            Display width in characters (default: 5)
        upper_limit : int
            Maximum value (0 = no limit)
        lower_limit : int
            Minimum value (0 = no limit)
        label : str
            Label text (default: '-' for none)
        receive : str
            Receive symbol for wireless input
        send : str
            Send symbol for wireless output

        Returns
        -------
        Float
            The created number box
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Float(x_pos, y_pos, width, upper_limit, lower_limit, label, receive, send)
        self._register(node, pos_update)
        return node

    def add_subpatch(
        self,
        name: str,
        src: "Patcher",
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        num_inlets: Optional[int] = None,
        num_outlets: Optional[int] = None,
        canvas_width: int = SUBPATCH_CANVAS_WIDTH,
        canvas_height: int = SUBPATCH_CANVAS_HEIGHT,
        inherit_layout: bool = False,
        graph_on_parent: bool = False,
        hide_name: bool = False,
        gop_width: int = 85,
        gop_height: int = 60,
        is_graph: bool = False,
        gop_rect: Tuple[float, float, float, float] = (0, 1, 1, 0),
        gop_margins: Optional[Tuple[int, int]] = (0, 0),
    ) -> Subpatch:
        """Add a subpatch to the patch.

        Parameters
        ----------
        name : str
            The subpatch name (displayed as 'pd <name>')

        src : Patcher
            The inner patch with its own coordinate system.

        num_inlets : int, optional
            Number of inlets (should match 'inlet' objects in src)

        num_outlets : int, optional
            Number of outlets (should match 'outlet' objects in src)

        canvas_width : int, optional
            Width of the subpatch's inner canvas (default: 300)

        canvas_height : int, optional
            Height of the subpatch's inner canvas (default: 180)

        inherit_layout : bool, optional
            If True, copy this patch's layout settings to inner patch.

        graph_on_parent : bool, optional
            If True, GUI elements inside the subpatch are visible in the
            parent patch (default: False)

        hide_name : bool, optional
            If True, hide the subpatch name when graph_on_parent is enabled
            (default: False)

        gop_width : int, optional
            Width of the graph-on-parent viewport (default: 85)

        gop_height : int, optional
            Height of the graph-on-parent viewport (default: 60)

        is_graph : bool, optional
            If True, close the canvas with ``#X restore <x> <y> graph;`` --
            the form PureData uses for an array canvas (default: False)

        Returns
        -------
        Subpatch
            The created subpatch

        Example
        -------
        >>> inner = Patcher()
        >>> inlet = inner.add('inlet')
        >>> gain = inner.add('*~ 0.5')
        >>> inner.link(inlet, gain)
        >>> outlet = inner.add('outlet~')
        >>> inner.link(gain, outlet)
        >>>
        >>> parent = Patcher()
        >>> osc = parent.add('osc~ 440')
        >>> sp = parent.add_subpatch('gain', inner, num_inlets=1, num_outlets=1)
        >>> parent.link(osc, sp)
        """
        if inherit_layout:
            src.layout.default_margin = self.layout.default_margin
            src.layout.row_height = self.layout.row_height
            src.layout.column_width = self.layout.column_width

        # Auto-infer inlet/outlet counts from inner patch objects
        if num_inlets is None:
            num_inlets = sum(
                1
                for n in src.nodes
                if isinstance(n, Obj)
                and n.parameters["text"].split()[:1] in (["inlet"], ["inlet~"])
            )
        if num_outlets is None:
            num_outlets = sum(
                1
                for n in src.nodes
                if isinstance(n, Obj)
                and n.parameters["text"].split()[:1] in (["outlet"], ["outlet~"])
            )

        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Subpatch(
            x_pos,
            y_pos,
            name,
            src,
            num_inlets,
            num_outlets,
            canvas_width,
            canvas_height,
            graph_on_parent=graph_on_parent,
            hide_name=hide_name,
            gop_width=gop_width,
            gop_height=gop_height,
            is_graph=is_graph,
            gop_rect=gop_rect,
            gop_margins=gop_margins,
        )
        self._register(node, pos_update)
        return node

    def add_abstraction(
        self,
        text: str,
        *,
        source_path: Optional[str] = None,
        num_inlets: Optional[int] = None,
        num_outlets: Optional[int] = None,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
    ) -> Abstraction:
        """Add an abstraction reference (external .pd file) to the patch.

        Parameters
        ----------
        text : str
            The abstraction text (e.g., ``'my-synth 440 0.5'``)

        source_path : str, optional
            Path to the .pd file. If provided and num_inlets/num_outlets
            are not specified, inlet/outlet counts will be inferred from
            the file contents.

        num_inlets : int, optional
            Number of inlets. If None and source_path is given, inferred from
            the file. Otherwise left unknown, so connection validation is
            skipped for this node -- py2pd cannot see inside an abstraction it
            has not been shown.

        num_outlets : int, optional
            Number of outlets. Same rules as *num_inlets*.

        Returns
        -------
        Abstraction
            The created abstraction reference
        """
        if source_path is not None and (num_inlets is None or num_outlets is None):
            inferred_in, inferred_out = _infer_abstraction_io(source_path)
            if num_inlets is None:
                num_inlets = inferred_in
            if num_outlets is None:
                num_outlets = inferred_out

        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Abstraction(
            x_pos,
            y_pos,
            text,
            num_inlets=num_inlets,
            num_outlets=num_outlets,
            source_path=source_path,
        )
        self._register(node, pos_update)
        return node

    def add_array(self, name: str, length: int) -> Array:
        """Declare an array in the subpatch.

        Parameters
        ----------
        name : str
            the subpatch name

        length : int
            the array length

        Returns
        -------
        node : Array
            The created array

        Notes
        -----
        The array will not have a graph. Its contents are not stored.
        """
        node = Array(name, length)
        self._register(node)
        return node

    def add_bang(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        size: int = IEM_DEFAULT_SIZE,
        hold: int = 250,
        interrupt: int = 50,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 17,
        label_y: int = 7,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
    ) -> Bang:
        """Create a bang button and add it to the patch.

        Parameters
        ----------
        size : int
            Width and height in pixels (default: 15)

        init : int
            If 1, send bang on load (default: 0)

        send : str
            Send symbol for wireless connection

        receive : str
            Receive symbol for wireless connection

        label : str
            Label text displayed next to the button

        Returns
        -------
        node : Bang
            The created bang button
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Bang(
            x_pos,
            y_pos,
            size=size,
            hold=hold,
            interrupt=interrupt,
            init=init,
            send=send,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            fg_color=fg_color,
            label_color=label_color,
        )
        self._register(node, pos_update)
        return node

    def add_toggle(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        size: int = IEM_DEFAULT_SIZE,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 17,
        label_y: int = 7,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: int = 0,
        default_value: int = 1,
    ) -> Toggle:
        """Create a toggle button and add it to the patch.

        Parameters
        ----------
        size : int
            Width and height in pixels (default: 15)

        init : int
            If 1, output init_value on load (default: 0)

        default_value : int
            Value when toggled on (default: 1)

        Returns
        -------
        node : Toggle
            The created toggle button
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Toggle(
            x_pos,
            y_pos,
            size=size,
            init=init,
            send=send,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            fg_color=fg_color,
            label_color=label_color,
            init_value=init_value,
            default_value=default_value,
        )
        self._register(node, pos_update)
        return node

    def add_symbol(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        width: int = 10,
        lower_limit: float = 0,
        upper_limit: float = 0,
        label_pos: int = 0,
        label: str = "-",
        send: str = "-",
        receive: str = "-",
    ) -> Symbol:
        """Create a symbol input box and add it to the patch.

        Parameters
        ----------
        width : int
            Width in characters (default: 10)

        Returns
        -------
        node : Symbol
            The created symbol box
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Symbol(
            x_pos,
            y_pos,
            width=width,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            label_pos=label_pos,
            label=label,
            send=send,
            receive=receive,
        )
        self._register(node, pos_update)
        return node

    def add_numberbox(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        width: int = 5,
        height: int = 14,
        min_val: float = -1e37,
        max_val: float = 1e37,
        log_flag: int = 0,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 0,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: float = 0,
        log_height: int = 256,
    ) -> NumberBox:
        """Create an IEM number box and add it to the patch.

        Unlike floatatom, nbx supports logarithmic scaling and more appearance options.

        Parameters
        ----------
        width : int
            Width in characters (default: 5)

        height : int
            Height in pixels (default: 14)

        min_val : float
            Minimum value

        max_val : float
            Maximum value

        Returns
        -------
        node : NumberBox
            The created number box
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = NumberBox(
            x_pos,
            y_pos,
            width=width,
            height=height,
            min_val=min_val,
            max_val=max_val,
            log_flag=log_flag,
            init=init,
            send=send,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            fg_color=fg_color,
            label_color=label_color,
            init_value=init_value,
            log_height=log_height,
        )
        self._register(node, pos_update)
        return node

    def add_vslider(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        width: int = 15,
        height: int = 128,
        min_val: float = 0,
        max_val: float = 127,
        log_flag: int = 0,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 0,
        label_y: int = -9,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: float = 0,
        steady: int = 1,
    ) -> VSlider:
        """Create a vertical slider and add it to the patch.

        Parameters
        ----------
        width : int
            Width in pixels (default: 15)

        height : int
            Height in pixels (default: 128)

        min_val : float
            Minimum output value (default: 0)

        max_val : float
            Maximum output value (default: 127)

        Returns
        -------
        node : VSlider
            The created vertical slider
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = VSlider(
            x_pos,
            y_pos,
            width=width,
            height=height,
            min_val=min_val,
            max_val=max_val,
            log_flag=log_flag,
            init=init,
            send=send,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            fg_color=fg_color,
            label_color=label_color,
            init_value=init_value,
            steady=steady,
        )
        self._register(node, pos_update)
        return node

    def add_hslider(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        width: int = 128,
        height: int = 15,
        min_val: float = 0,
        max_val: float = 127,
        log_flag: int = 0,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = -2,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: float = 0,
        steady: int = 1,
    ) -> HSlider:
        """Create a horizontal slider and add it to the patch.

        Parameters
        ----------
        width : int
            Width in pixels (default: 128)

        height : int
            Height in pixels (default: 15)

        min_val : float
            Minimum output value (default: 0)

        max_val : float
            Maximum output value (default: 127)

        Returns
        -------
        node : HSlider
            The created horizontal slider
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = HSlider(
            x_pos,
            y_pos,
            width=width,
            height=height,
            min_val=min_val,
            max_val=max_val,
            log_flag=log_flag,
            init=init,
            send=send,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            fg_color=fg_color,
            label_color=label_color,
            init_value=init_value,
            steady=steady,
        )
        self._register(node, pos_update)
        return node

    def add_vradio(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        size: int = 15,
        new_old: int = 0,
        number: int = 8,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 0,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: int = 0,
    ) -> VRadio:
        """Create vertical radio buttons and add to the patch.

        Parameters
        ----------
        size : int
            Size of each button in pixels (default: 15)

        number : int
            Number of buttons (default: 8)

        Returns
        -------
        node : VRadio
            The created vertical radio buttons
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = VRadio(
            x_pos,
            y_pos,
            size=size,
            new_old=new_old,
            number=number,
            init=init,
            send=send,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            fg_color=fg_color,
            label_color=label_color,
            init_value=init_value,
        )
        self._register(node, pos_update)
        return node

    def add_hradio(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        size: int = 15,
        new_old: int = 0,
        number: int = 8,
        init: int = 0,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 0,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        fg_color: IemColor = IEM_FG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        init_value: int = 0,
    ) -> HRadio:
        """Create horizontal radio buttons and add to the patch.

        Parameters
        ----------
        size : int
            Size of each button in pixels (default: 15)

        number : int
            Number of buttons (default: 8)

        Returns
        -------
        node : HRadio
            The created horizontal radio buttons
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = HRadio(
            x_pos,
            y_pos,
            size=size,
            new_old=new_old,
            number=number,
            init=init,
            send=send,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            fg_color=fg_color,
            label_color=label_color,
            init_value=init_value,
        )
        self._register(node, pos_update)
        return node

    def add_canvas(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        size: int = 15,
        width: int = 100,
        height: int = 60,
        send: str = "empty",
        receive: str = "empty",
        label: str = "empty",
        label_x: int = 20,
        label_y: int = 12,
        font: int = 0,
        font_size: int = 14,
        bg_color: IemColor = -233017,
        label_color: IemColor = IEM_LABEL_COLOR,
    ) -> Canvas:
        """Create a canvas/background rectangle and add to the patch.

        Canvas objects are purely visual - useful for organizing patches
        with colored backgrounds and labels.

        Parameters
        ----------
        width : int
            Width in pixels (default: 100)

        height : int
            Height in pixels (default: 60)

        label : str
            Text displayed on the canvas

        bg_color : int
            Background color as PureData color value

        Returns
        -------
        node : Canvas
            The created canvas
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = Canvas(
            x_pos,
            y_pos,
            size=size,
            width=width,
            height=height,
            send=send,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            label_color=label_color,
        )
        self._register(node, pos_update)
        return node

    def add_vu(
        self,
        *,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        width: int = 15,
        height: int = 120,
        receive: str = "empty",
        label: str = "empty",
        label_x: int = -1,
        label_y: int = -8,
        font: int = 0,
        font_size: int = 10,
        bg_color: IemColor = IEM_BG_COLOR,
        label_color: IemColor = IEM_LABEL_COLOR,
        scale: int = 1,
    ) -> VU:
        """Create a VU meter and add to the patch.

        VU meters display audio levels. They have 2 inlets:
        - Inlet 0: RMS level
        - Inlet 1: Peak level

        Parameters
        ----------
        width : int
            Width in pixels (default: 15)

        height : int
            Height in pixels (default: 120)

        Returns
        -------
        node : VU
            The created VU meter
        """
        x_pos, y_pos, pos_update = self._resolve_position(x_pos, y_pos, new_row, new_col)
        node = VU(
            x_pos,
            y_pos,
            width=width,
            height=height,
            receive=receive,
            label=label,
            label_x=label_x,
            label_y=label_y,
            font=font,
            font_size=font_size,
            bg_color=bg_color,
            label_color=label_color,
            scale=scale,
        )
        self._register(node, pos_update)
        return node

    def link(
        self,
        source: Union[Node, "Node.Outlet"],
        sink: Node,
        outlet: int = 0,
        inlet: int = 0,
    ) -> None:
        """Connect source's outlet to sink's inlet.

        Parameters
        ----------
        source : Node or Node.Outlet
            The source node (signal flows from here). If a Node.Outlet is
            passed, its index is used as the outlet and the owner as source.
        sink : Node
            The sink node (signal flows to here)
        outlet : int, optional
            Index of the source's outlet (default: 0). Ignored if source
            is a Node.Outlet.
        inlet : int, optional
            Index of the sink's inlet (default: 0)

        Raises
        ------
        NodeNotFoundError
            If source or sink is not in this patch
        PdConnectionError
            If an index is negative, or exceeds the node's known I/O count
            while ``validate_links`` is True. PureData rejects a negative index
            outright ("connection failed"), so it is always an error regardless
            of ``validate_links``.

        Example
        -------
        >>> p = Patcher()
        >>> osc = p.add('osc~ 440')
        >>> dac = p.add('dac~')
        >>> p.link(osc, dac)           # connect osc outlet 0 -> dac inlet 0
        >>> p.link(osc[0], dac)        # same as above using Outlet syntax
        >>> p.link(osc, dac, inlet=1)  # connect osc outlet 0 -> dac inlet 1 (stereo)
        """
        if isinstance(source, Node.Outlet):
            outlet = source.index
            source = source.owner

        source_index = self._index_of(source, "Source")
        sink_index = self._index_of(sink, "Sink")

        if outlet < 0:
            raise PdConnectionError(f"Outlet index must be non-negative, got {outlet}")
        if inlet < 0:
            raise PdConnectionError(f"Inlet index must be non-negative, got {inlet}")

        if source.num_outlets is not None and outlet >= source.num_outlets:
            self._reject_link(
                f"Outlet index {outlet} out of range for {source!r} "
                f"(has {source.num_outlets} outlet{'s' if source.num_outlets != 1 else ''})"
            )
        if sink.num_inlets is not None and inlet >= sink.num_inlets:
            self._reject_link(
                f"Inlet index {inlet} out of range for {sink!r} "
                f"(has {sink.num_inlets} inlet{'s' if sink.num_inlets != 1 else ''})"
            )

        self.connections.append(Connection(source_index, outlet, sink_index, inlet))

    def _index_of(self, node: Node, role: str) -> int:
        """Return *node*'s position in ``self.nodes``.

        Backed by an ``id()`` cache so that building a large patch is linear
        rather than quadratic -- a plain ``list.index()`` per ``link()`` call
        made construction O(n^2). The cached position is verified against the
        live list before use and rebuilt on a miss, so the cache stays correct
        even when ``self.nodes`` is manipulated directly.

        Raises
        ------
        NodeNotFoundError
            If *node* is not in this patch.
        """
        key = id(node)
        cached = self._node_positions.get(key)
        if cached is not None and cached < len(self.nodes) and self.nodes[cached] is node:
            return cached

        self._node_positions = {id(n): i for i, n in enumerate(self.nodes)}
        index = self._node_positions.get(key)
        if index is None:
            raise NodeNotFoundError(f"{role} node {node!r} not found in patch")
        return index

    def _reject_link(self, message: str) -> None:
        """Raise or warn about an out-of-range connection, per ``validate_links``."""
        if self.validate_links:
            raise PdConnectionError(message)
        warnings.warn(message, PdConnectionWarning, stacklevel=3)

    # Alias for symmetry with add_* methods
    add_link = link

    def __str__(self) -> str:
        canvas = (
            f"#N canvas {self.canvas_x} {self.canvas_y} "
            f"{self.canvas_width} {self.canvas_height} {self.font_size};\n"
        )
        return f"{canvas}{self._subpatch_str().rstrip()}"

    def __repr__(self) -> str:
        return f"Patcher(nodes={len(self.nodes)}, connections={len(self.connections)})"

    def _subpatch_str(self) -> str:
        """Internal: generate string for patch contents."""
        nodes_str = "".join(str(n) for n in self.nodes)
        connections_str = "".join(str(c) for c in self.connections)
        return f"{nodes_str}{connections_str}"

    def save(self, filename: Optional[str] = None) -> None:
        """Save the patch to a file.

        Parameters
        ----------
        filename : str, optional
            Path to the output .pd file. If not provided, uses the filename
            from the constructor.

        Raises
        ------
        ValueError
            If no filename is provided and none was set in constructor.
        """
        fn = filename or self.filename
        if fn is None:
            raise ValueError("No filename specified. Provide filename or set in constructor.")
        with open(fn, "w", encoding="utf-8", newline="\n") as f:
            f.write(str(self) + "\n")

    def validate_connections(
        self, check_cycles: bool = True, *, raise_on_error: bool = True
    ) -> List[str]:
        """Validate all connections in the patch.

        Checks that:
        - Outlet indices are within bounds (if num_outlets is specified on source node)
        - Inlet indices are within bounds (if num_inlets is specified on sink node)
        - Optionally detects cycles in the connection graph

        Parameters
        ----------
        check_cycles : bool
            If True, also check for cycles and issue warnings (default: True)
        raise_on_error : bool
            If True (default), raise ``InvalidConnectionError`` when any
            connection is invalid. If False, return the errors instead, which
            is the only way to receive a non-empty list.

        Returns
        -------
        list of str
            Validation error messages. Always empty when *raise_on_error* is
            True, since a non-empty result raises instead.

        Raises
        ------
        InvalidConnectionError
            If any connection references an invalid inlet or outlet index and
            *raise_on_error* is True. Connections to nodes whose
            num_inlets/num_outlets are unknown are not checked.

        Examples
        --------
        >>> patch = Patcher()
        >>> osc = patch.add('osc~ 440')
        >>> dac = patch.add('dac~')
        >>> patch.link(osc, dac)
        >>> patch.validate_connections()
        []

        Collect problems instead of raising:

        >>> errors = patch.validate_connections(raise_on_error=False)
        >>> if errors:
        ...     print("Validation errors:", errors)
        """
        errors = []

        for conn in self.connections:
            source_node = self.nodes[conn.source]
            sink_node = self.nodes[conn.sink]

            # Validate outlet index
            if source_node.num_outlets is not None:
                if conn.outlet_index >= source_node.num_outlets:
                    errors.append(
                        f"Invalid outlet index {conn.outlet_index} on {source_node!r} "
                        f"(has {source_node.num_outlets} outlets)"
                    )
                elif conn.outlet_index < 0:
                    errors.append(f"Negative outlet index {conn.outlet_index} on {source_node!r}")

            # Validate inlet index
            if sink_node.num_inlets is not None:
                if conn.inlet_index >= sink_node.num_inlets:
                    errors.append(
                        f"Invalid inlet index {conn.inlet_index} on {sink_node!r} "
                        f"(has {sink_node.num_inlets} inlets)"
                    )
                elif conn.inlet_index < 0:
                    errors.append(f"Negative inlet index {conn.inlet_index} on {sink_node!r}")

        # Check for cycles if requested
        if check_cycles:
            cycles = self.detect_cycles()
            if cycles:
                for cycle in cycles:
                    cycle_nodes = [repr(self.nodes[i]) for i in cycle]
                    warnings.warn(f"Cycle detected: {' -> '.join(cycle_nodes)}", CycleWarning)

        if errors and raise_on_error:
            raise InvalidConnectionError(
                f"Found {len(errors)} invalid connection(s):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        return errors

    def detect_cycles(self) -> List[List[int]]:
        """Detect cycles in the connection graph.

        Uses depth-first search to find all cycles in the patch's
        connection graph. Note that PureData allows cycles (for feedback),
        so this is informational rather than an error.

        Returns
        -------
        list of list of int
            Each inner list contains node indices forming a cycle.
            Empty list if no cycles found.

        Examples
        --------
        >>> patch = Patcher()
        >>> a = patch.add('delread~ delay')
        >>> b = patch.add('+~')
        >>> c = patch.add('delwrite~ delay')
        >>> patch.link(a, b)
        >>> patch.link(b, c)
        >>> cycles = patch.detect_cycles()

        Notes
        -----
        The traversal is iterative. A recursive one overflows the interpreter
        stack on a patch a few thousand nodes deep, and ``validate_connections()``
        calls this by default.
        """
        # Build adjacency list
        adjacency: Dict[int, List[int]] = {i: [] for i in range(len(self.nodes))}
        for conn in self.connections:
            if conn.sink not in adjacency[conn.source]:
                adjacency[conn.source].append(conn.sink)

        cycles: List[List[int]] = []
        visited: Set[int] = set()
        on_path: Set[int] = set()
        path: List[int] = []

        for start in range(len(self.nodes)):
            if start in visited:
                continue
            # Each stack frame is (node, index of the next neighbour to visit).
            stack: List[Tuple[int, int]] = [(start, 0)]
            visited.add(start)
            on_path.add(start)
            path.append(start)

            while stack:
                node, next_index = stack[-1]
                neighbors = adjacency[node]
                if next_index < len(neighbors):
                    stack[-1] = (node, next_index + 1)
                    neighbor = neighbors[next_index]
                    if neighbor in on_path:
                        # Back edge: the cycle is the path from that node on.
                        cycle_start = path.index(neighbor)
                        cycles.append(path[cycle_start:] + [neighbor])
                    elif neighbor not in visited:
                        visited.add(neighbor)
                        on_path.add(neighbor)
                        path.append(neighbor)
                        stack.append((neighbor, 0))
                else:
                    stack.pop()
                    on_path.discard(node)
                    path.pop()

        return cycles

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about connections in the patch.

        Returns
        -------
        dict
            Statistics including:
            - total_connections: Total number of connections
            - nodes_with_connections: Number of nodes that have connections
            - max_inlets_used: Maximum inlet index used
            - max_outlets_used: Maximum outlet index used
            - validation_coverage: Percentage of nodes with inlet/outlet counts specified
        """
        if not self.connections:
            return {
                "total_connections": 0,
                "nodes_with_connections": 0,
                "max_inlets_used": 0,
                "max_outlets_used": 0,
                "validation_coverage": 0.0,
            }

        connected_nodes = set()
        max_inlet = 0
        max_outlet = 0

        for conn in self.connections:
            connected_nodes.add(conn.source)
            connected_nodes.add(conn.sink)
            max_inlet = max(max_inlet, conn.inlet_index)
            max_outlet = max(max_outlet, conn.outlet_index)

        nodes_with_counts = sum(
            1 for n in self.nodes if n.num_inlets is not None or n.num_outlets is not None
        )
        coverage = nodes_with_counts / len(self.nodes) * 100 if self.nodes else 0

        return {
            "total_connections": len(self.connections),
            "nodes_with_connections": len(connected_nodes),
            "max_inlets_used": max_inlet,
            "max_outlets_used": max_outlet,
            "validation_coverage": round(coverage, 1),
        }

    def to_svg(
        self,
        padding: int = 20,
        node_height: int = 20,
        min_node_width: int = 60,
        char_width: int = 7,
        font_size: int = 11,
        show_labels: bool = True,
    ) -> str:
        """Export the patch as an SVG diagram.

        Generates an SVG visualization of the patch showing all nodes
        as boxes and connections as lines between them.

        Parameters
        ----------
        padding : int
            Padding around the diagram (default: 20)
        node_height : int
            Height of each node box (default: 20)
        min_node_width : int
            Minimum width of a node box (default: 60)
        char_width : int
            Estimated width per character for sizing (default: 7)
        font_size : int
            Font size for node labels (default: 11)
        show_labels : bool
            Whether to show text labels in nodes (default: True)

        Returns
        -------
        str
            SVG markup as a string

        Example
        -------
        >>> p = Patcher()
        >>> osc = p.add('osc~ 440')
        >>> dac = p.add('dac~')
        >>> p.link(osc, dac)
        >>> svg = p.to_svg()
        >>> with open('patch.svg', 'w') as f:
        ...     f.write(svg)
        """
        if not self.nodes:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>'

        def get_node_text(node: Node) -> str:
            """Extract display text from a node.

            Ordered most specific first: a bare ``"text" in params`` check would
            also catch Msg, and ``"name" in params`` would also catch Array,
            leaving their own labels unreachable.
            """
            params = node.parameters
            if isinstance(node, Msg):
                return f"msg: {params.get('text', '')}"
            if isinstance(node, Array):
                return f"array: {params.get('name', '')}"
            if isinstance(node, Float):
                return "floatatom"
            if isinstance(node, Comment):
                return str(params.get("content", ""))
            if "text" in params:
                return str(params["text"])
            if "name" in params:
                return f"[{params['name']}]"
            return str(type(node).__name__)

        def get_node_width(text: str) -> int:
            """Calculate node width based on text length."""
            return max(min_node_width, len(text) * char_width + 16)

        # Calculate node dimensions and bounds
        node_info: List[Optional[Dict[str, Any]]] = []
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = 0.0, 0.0

        for node in self.nodes:
            if node.hidden:
                node_info.append(None)
                continue

            x, y = node.position
            text = get_node_text(node)
            width = get_node_width(text)

            node_info.append(
                {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": node_height,
                    "text": text,
                    "type": type(node).__name__,
                }
            )

            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + width)
            max_y = max(max_y, y + node_height)

        # Handle empty/all-hidden case
        if min_x == float("inf"):
            return '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>'

        # SVG dimensions
        svg_width = int(max_x - min_x + 2 * padding)
        svg_height = int(max_y - min_y + 2 * padding)

        # Offset to normalize coordinates
        offset_x = int(-min_x + padding)
        offset_y = int(-min_y + padding)

        # Build SVG
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}">',
            "  <defs>",
            "    <style>",
            "      .node { fill: #f5f5f5; stroke: #333; stroke-width: 1; }",
            "      .node-msg { fill: #fff8e1; }",
            "      .node-subpatch { fill: #e3f2fd; }",
            "      .node-gui { fill: #f3e5f5; }",
            "      .node-text { font-family: monospace; font-size: "
            + str(font_size)
            + "px; fill: #333; }",
            "      .connection { stroke: #666; stroke-width: 1.5; fill: none; }",
            "    </style>",
            "  </defs>",
            "",
        ]

        # Draw connections first (behind nodes)
        lines.append("  <!-- Connections -->")
        for conn in self.connections:
            source_info = node_info[conn.source] if conn.source < len(node_info) else None
            sink_info = node_info[conn.sink] if conn.sink < len(node_info) else None

            if source_info is None or sink_info is None:
                continue

            # Calculate connection points
            # Outlets are at the bottom of source, inlets at the top of sink
            src_x = int(source_info["x"]) + offset_x + int(source_info["width"]) // 2
            src_y = int(source_info["y"]) + offset_y + int(source_info["height"])

            sink_x = int(sink_info["x"]) + offset_x + int(sink_info["width"]) // 2
            sink_y = int(sink_info["y"]) + offset_y

            # Use a curved path for better visualization
            mid_y = (src_y + sink_y) // 2
            lines.append(
                f'  <path class="connection" d="M {src_x} {src_y} '
                f'C {src_x} {mid_y}, {sink_x} {mid_y}, {sink_x} {sink_y}"/>'
            )

        # Draw nodes
        lines.append("")
        lines.append("  <!-- Nodes -->")
        for i, info in enumerate(node_info):
            if info is None:
                continue

            x = int(info["x"]) + offset_x
            y = int(info["y"]) + offset_y
            w = int(info["width"])
            h = int(info["height"])

            # Determine node class based on type
            node_class = "node"
            if info["type"] == "Msg":
                node_class = "node node-msg"
            elif info["type"] == "Subpatch":
                node_class = "node node-subpatch"
            elif info["type"] in (
                "Bang",
                "Toggle",
                "VSlider",
                "HSlider",
                "VRadio",
                "HRadio",
                "NumberBox",
                "Canvas",
                "VU",
            ):
                node_class = "node node-gui"

            lines.append(
                f'  <rect class="{node_class}" x="{x}" y="{y}" width="{w}" height="{h}" rx="2"/>'
            )

            if show_labels:
                # Truncate text if too long
                text = str(info["text"])
                max_chars = max(0, (w - 8) // char_width)
                if len(text) > max_chars:
                    text = text[: max(0, max_chars - 2)] + ".."

                text_x = x + 4
                text_y = y + h - 5
                # Escape XML entities
                text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                lines.append(f'  <text class="node-text" x="{text_x}" y="{text_y}">{text}</text>')

        lines.append("</svg>")
        return "\n".join(lines)

    def save_svg(self, filename: str, **kwargs: Any) -> None:
        """Save the patch visualization as an SVG file.

        Parameters
        ----------
        filename : str
            Path to the output .svg file
        **kwargs
            Additional arguments passed to to_svg()

        Example
        -------
        >>> p = Patcher()
        >>> osc = p.add('osc~ 440')
        >>> dac = p.add('dac~')
        >>> p.link(osc, dac)
        >>> p.save_svg('patch.svg')
        """
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.to_svg(**kwargs))

    def _remap_after_removal(self, indices_to_remove: Set[int]) -> None:
        """Rebuild node and connection lists after removing nodes at *indices_to_remove*.

        Connections that reference any removed node are dropped. Surviving
        connections have their source/sink indices remapped to match the
        compacted node list. The layout state is reset because row_head/row_tail
        may reference removed nodes.
        """
        if not indices_to_remove:
            return

        # Build old -> new index mapping
        old_to_new: Dict[int, int] = {}
        new_idx = 0
        for old_idx in range(len(self.nodes)):
            if old_idx not in indices_to_remove:
                old_to_new[old_idx] = new_idx
                new_idx += 1

        # Rebuild nodes
        self.nodes = [n for i, n in enumerate(self.nodes) if i not in indices_to_remove]

        # Filter and remap connections
        new_connections: List[Connection] = []
        for conn in self.connections:
            if conn.source in indices_to_remove or conn.sink in indices_to_remove:
                continue
            new_connections.append(
                Connection(
                    old_to_new[conn.source],
                    conn.outlet_index,
                    old_to_new[conn.sink],
                    conn.inlet_index,
                )
            )
        self.connections = new_connections

        # Layout anchors may reference removed nodes
        self.layout.reset()

    def optimize(
        self,
        *,
        recursive: bool = False,
        collapsible_objects: FrozenSet[str] = frozenset(),
    ) -> Dict[str, int]:
        """Remove unused elements and simplify connections.

        Runs three passes in order:

        1. **Deduplicate connections** -- drop exact-duplicate patch cords.
        2. **Pass-through collapse** -- for each ``Obj`` node whose class name
           is in *collapsible_objects*, that has exactly 1 inlet, 1 outlet,
           no creation arguments, and exactly 1 incoming + 1 outgoing
           connection: replace the two connections with a single direct one and
           remove the intermediate node. The caller must ensure that collapsing
           the intermediate node does not change message semantics.
        3. **Unused element removal** -- remove ``Obj`` nodes that have no
           connections and are not protected types (GUI, Comment, Subpatch,
           Abstraction, Array, Msg, Float), are not structural objects that do
           their job without patch cords (``inlet``, ``outlet``, ``table``,
           ``declare``, ``block~``, ... -- see ``_STRUCTURAL_OBJECTS``), and do
           not have active send/receive parameters.

        Parameters
        ----------
        recursive : bool
            If True, call ``optimize()`` on the inner patch of every
            ``Subpatch`` node first (default: False).
        collapsible_objects : frozenset of str
            Set of Pd class names eligible for pass-through collapse
            (default: empty -- no collapse unless opt-in).

        Returns
        -------
        dict with str keys and int values
            ``nodes_removed``, ``connections_removed``, ``duplicates_removed``,
            ``pass_throughs_collapsed``, ``subpatches_optimized``.
        """
        stats: Dict[str, int] = {
            "nodes_removed": 0,
            "connections_removed": 0,
            "duplicates_removed": 0,
            "pass_throughs_collapsed": 0,
            "subpatches_optimized": 0,
        }

        # --- Recursive pass ---
        if recursive:
            for node in self.nodes:
                if isinstance(node, Subpatch):
                    node.src.optimize(
                        recursive=True,
                        collapsible_objects=collapsible_objects,
                    )
                    stats["subpatches_optimized"] += 1

        initial_connection_count = len(self.connections)

        # --- Pass 1: Deduplicate connections ---
        seen: Set[Tuple[int, int, int, int]] = set()
        deduped: List[Connection] = []
        for conn in self.connections:
            key = (conn.source, conn.outlet_index, conn.sink, conn.inlet_index)
            if key not in seen:
                seen.add(key)
                deduped.append(conn)
        stats["duplicates_removed"] = len(self.connections) - len(deduped)
        self.connections = deduped

        # --- Pass 2: Pass-through collapse ---
        removal_set: Set[int] = set()
        if collapsible_objects:
            # Build inverse indices for O(1) lookup
            conn_by_sink: Dict[int, List[Connection]] = {}
            conn_by_source: Dict[int, List[Connection]] = {}
            for c in self.connections:
                conn_by_sink.setdefault(c.sink, []).append(c)
                conn_by_source.setdefault(c.source, []).append(c)

            conns_to_remove: Set[int] = set()  # id() of connections to remove
            # Bypass edges keyed by the node they replace, resolved transitively
            # afterwards.  Emitting them directly would break when two
            # collapsible nodes are adjacent: the bypass for the first would
            # point at the second, which is itself about to be removed, and the
            # whole chain would be dropped instead of joined.
            bypass: Dict[int, Tuple[Connection, Connection]] = {}

            for idx, node in enumerate(self.nodes):
                if not isinstance(node, Obj):
                    continue
                text_parts = node.parameters["text"].split()
                class_name = text_parts[0] if text_parts else ""
                if class_name not in collapsible_objects:
                    continue
                # Must have no creation args
                if len(text_parts) > 1:
                    continue
                # Must have exactly 1 inlet and 1 outlet
                if node.num_inlets != 1 or node.num_outlets != 1:
                    continue
                # Find incoming and outgoing connections
                incoming = conn_by_sink.get(idx, [])
                outgoing = conn_by_source.get(idx, [])
                if len(incoming) != 1 or len(outgoing) != 1:
                    continue
                inc = incoming[0]
                out = outgoing[0]
                bypass[idx] = (inc, out)
                conns_to_remove.add(id(inc))
                conns_to_remove.add(id(out))
                removal_set.add(idx)
                stats["pass_throughs_collapsed"] += 1

            conns_to_add = _resolve_bypasses(bypass)

            self.connections = [
                c for c in self.connections if id(c) not in conns_to_remove
            ] + conns_to_add

        # --- Pass 3: Unused element removal ---
        connected_nodes: Set[int] = set()
        for conn in self.connections:
            connected_nodes.add(conn.source)
            connected_nodes.add(conn.sink)

        for idx, node in enumerate(self.nodes):
            if idx in connected_nodes:
                continue
            if idx in removal_set:
                continue
            if isinstance(node, _PROTECTED_TYPES):
                continue
            if node.pd_class_name in _STRUCTURAL_OBJECTS:
                continue
            if _has_active_send_receive(node):
                continue
            removal_set.add(idx)

        stats["nodes_removed"] = len(removal_set)

        self._remap_after_removal(removal_set)

        stats["connections_removed"] = initial_connection_count - len(self.connections)

        return stats

    def auto_layout(
        self,
        margin: int = 50,
        row_spacing: int = 40,
        col_spacing: int = 120,
        align_columns: bool = True,
    ) -> None:
        """Automatically layout nodes based on signal flow.

        Performs a topological sort of the connection graph and positions
        nodes in rows based on their depth in the graph. Source nodes
        (no inputs) are placed at the top, sink nodes (no outputs) at
        the bottom.

        Parameters
        ----------
        margin : int
            Margin from canvas edge (default: 50)
        row_spacing : int
            Vertical spacing between rows (default: 40)
        col_spacing : int
            Horizontal spacing between nodes in same row (default: 120)
        align_columns : bool
            If True, try to align connected nodes vertically (default: True)

        Example
        -------
        >>> p = Patcher()
        >>> osc = p.add('osc~ 440')
        >>> gain = p.add('*~ 0.5')
        >>> dac = p.add('dac~')
        >>> p.link(osc, gain)
        >>> p.link(gain, dac)
        >>> p.auto_layout()  # Arranges: osc -> gain -> dac vertically
        """
        if not self.nodes:
            return

        # Build adjacency lists
        n = len(self.nodes)
        outgoing: Dict[int, Set[int]] = {i: set() for i in range(n)}
        incoming: Dict[int, Set[int]] = {i: set() for i in range(n)}

        for conn in self.connections:
            outgoing[conn.source].add(conn.sink)
            incoming[conn.sink].add(conn.source)

        # Detect back-edges via iterative DFS to break cycles
        back_edges: Set[Tuple[int, int]] = set()
        visited: Set[int] = set()
        on_stack: Set[int] = set()
        for start in range(n):
            if start in visited or self.nodes[start].hidden:
                continue
            stack: List[Tuple[int, int]] = [(start, 0)]
            on_stack.add(start)
            while stack:
                node_id, idx = stack[-1]
                neighbors = sorted(outgoing[node_id])
                if idx < len(neighbors):
                    stack[-1] = (node_id, idx + 1)
                    neighbor = neighbors[idx]
                    if neighbor in on_stack:
                        back_edges.add((node_id, neighbor))
                    elif neighbor not in visited and not self.nodes[neighbor].hidden:
                        on_stack.add(neighbor)
                        stack.append((neighbor, 0))
                else:
                    on_stack.discard(node_id)
                    visited.add(node_id)
                    stack.pop()

        # Build DAG by excluding back-edges
        dag_outgoing: Dict[int, Set[int]] = {i: set() for i in range(n)}
        dag_incoming: Dict[int, Set[int]] = {i: set() for i in range(n)}
        for i in range(n):
            for j in outgoing[i]:
                if (i, j) not in back_edges:
                    dag_outgoing[i].add(j)
                    dag_incoming[j].add(i)

        # Calculate depth for each node using BFS from sources on the DAG
        # Depth = longest path from any source to this node
        depth: Dict[int, int] = {}

        # Find source nodes (no incoming connections in DAG)
        sources = [i for i in range(n) if not dag_incoming[i] and not self.nodes[i].hidden]

        # If no clear sources, use all non-hidden nodes as potential starts
        if not sources:
            sources = [i for i in range(n) if not self.nodes[i].hidden]

        # BFS to assign depths (on DAG, guaranteed to terminate)
        queue: deque[int] = deque()

        for src in sources:
            if src not in depth:
                depth[src] = 0
                queue.append(src)

        while queue:
            current = queue.popleft()
            for neighbor in dag_outgoing[current]:
                new_depth = depth[current] + 1
                if neighbor not in depth or depth[neighbor] < new_depth:
                    depth[neighbor] = new_depth
                    queue.append(neighbor)

        # Assign depth 0 to any remaining unvisited nodes
        for i in range(n):
            if i not in depth and not self.nodes[i].hidden:
                depth[i] = 0

        # Group nodes by depth
        rows: Dict[int, List[int]] = {}
        for node_idx, d in depth.items():
            if d not in rows:
                rows[d] = []
            rows[d].append(node_idx)

        # Sort rows by depth and nodes within rows for consistency
        sorted_depths = sorted(rows.keys())

        # If align_columns is True, try to position nodes below their parents
        if align_columns and len(sorted_depths) > 1:
            # For each row after the first, order nodes based on parent positions
            for depth_idx in range(1, len(sorted_depths)):
                d = sorted_depths[depth_idx]
                prev_d = sorted_depths[depth_idx - 1]

                # Get x positions of nodes in previous row
                prev_positions = {}
                for i, node_idx in enumerate(rows[prev_d]):
                    prev_positions[node_idx] = i

                # Sort current row nodes by average parent position
                def parent_position(node_idx: int) -> float:
                    parents = [p for p in incoming[node_idx] if p in prev_positions]
                    if parents:
                        return sum(prev_positions[p] for p in parents) / len(parents)
                    return float("inf")

                rows[d].sort(key=parent_position)

        # Assign positions
        for d in sorted_depths:
            row_nodes = rows[d]
            y = margin + d * row_spacing

            start_x = margin

            for i, node_idx in enumerate(row_nodes):
                node = self.nodes[node_idx]
                x = start_x + i * col_spacing

                # Update node position
                node.parameters["x_pos"] = x
                node.parameters["y_pos"] = y
