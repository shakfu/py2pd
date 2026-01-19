"""
Abstract Syntax Tree representation for PureData patches.

This module provides:
- Immutable AST node classes representing PureData elements
- A parser to read .pd files into AST
- A serializer to write AST back to .pd format
- Round-trip conversion support

Example usage:
    >>> from py2pd.ast import parse_file, serialize
    >>> ast = parse_file('patch.pd')
    >>> print(ast)
    >>> with open('output.pd', 'w') as f:
    ...     f.write(serialize(ast))
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Union, Tuple

if TYPE_CHECKING:
    from . import api


# AST Node Types


@dataclass(frozen=True)
class Position:
    """2D position in the patch canvas."""

    x: int
    y: int

    def __str__(self) -> str:
        return f"{self.x} {self.y}"


@dataclass(frozen=True)
class CanvasProperties:
    """Properties of a PureData canvas (main patch or subpatch)."""

    x: int = 0
    y: int = 50
    width: int = 1000
    height: int = 600
    font_size: int = 10
    name: Optional[str] = None  # For subpatches
    open_on_load: int = 0  # 0 = closed, 1 = open

    def __str__(self) -> str:
        if self.name:
            return f"{self.x} {self.y} {self.width} {self.height} {self.name} {self.open_on_load}"
        return f"{self.x} {self.y} {self.width} {self.height} {self.font_size}"


@dataclass(frozen=True)
class PdObj:
    """A PureData object (#X obj)."""

    position: Position
    class_name: str
    args: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        if self.args:
            return f"{self.class_name} {' '.join(self.args)}"
        return self.class_name

    def __str__(self) -> str:
        return f"#X obj {self.position} {self.text};"


@dataclass(frozen=True)
class PdMsg:
    """A PureData message box (#X msg)."""

    position: Position
    content: str

    def __str__(self) -> str:
        return f"#X msg {self.position} {self.content};"


@dataclass(frozen=True)
class PdFloatatom:
    """A PureData number box (#X floatatom)."""

    position: Position
    width: int = 5
    lower_limit: float = 0
    upper_limit: float = 0
    label_pos: int = 0  # 0=left, 1=right, 2=top, 3=bottom
    label: str = "-"
    receive: str = "-"
    send: str = "-"

    def __str__(self) -> str:
        return (
            f"#X floatatom {self.position} {self.width} "
            f"{self.lower_limit} {self.upper_limit} {self.label_pos} "
            f"{self.label} {self.receive} {self.send};"
        )


@dataclass(frozen=True)
class PdSymbolatom:
    """A PureData symbol box (#X symbolatom)."""

    position: Position
    width: int = 10
    lower_limit: float = 0
    upper_limit: float = 0
    label_pos: int = 0
    label: str = "-"
    receive: str = "-"
    send: str = "-"

    def __str__(self) -> str:
        return (
            f"#X symbolatom {self.position} {self.width} "
            f"{self.lower_limit} {self.upper_limit} {self.label_pos} "
            f"{self.label} {self.receive} {self.send};"
        )


@dataclass(frozen=True)
class PdText:
    """A PureData comment (#X text)."""

    position: Position
    content: str

    def __str__(self) -> str:
        return f"#X text {self.position} {self.content};"


@dataclass(frozen=True)
class PdArray:
    """A PureData array declaration (#X array)."""

    name: str
    size: int
    dtype: str = "float"
    save_flag: int = 0

    def __str__(self) -> str:
        return f"#X array {self.name} {self.size} {self.dtype} {self.save_flag};"


@dataclass(frozen=True)
class PdConnect:
    """A connection between two objects (#X connect)."""

    source_id: int
    outlet_id: int
    sink_id: int
    inlet_id: int

    def __str__(self) -> str:
        return f"#X connect {self.source_id} {self.outlet_id} {self.sink_id} {self.inlet_id};"


@dataclass(frozen=True)
class PdCoords:
    """Graph-on-parent coordinates (#X coords)."""

    x_from: float
    y_from: float
    x_to: float
    y_to: float
    width: int
    height: int
    graph_on_parent: int = 1
    hide_name: int = 0
    x_margin: int = 0
    y_margin: int = 0

    def __str__(self) -> str:
        return (
            f"#X coords {self.x_from} {self.y_from} {self.x_to} {self.y_to} "
            f"{self.width} {self.height} {self.graph_on_parent} "
            f"{self.hide_name} {self.x_margin} {self.y_margin};"
        )


@dataclass(frozen=True)
class PdRestore:
    """Subpatch restore command (#X restore)."""

    position: Position
    name: str

    def __str__(self) -> str:
        return f"#X restore {self.position} pd {self.name};"


# GUI objects
@dataclass(frozen=True)
class PdBng:
    """Bang button (#X obj ... bng)."""

    position: Position
    size: int = 15
    hold: int = 250
    interrupt: int = 50
    init: int = 0
    send: str = "empty"
    receive: str = "empty"
    label: str = "empty"
    label_x: int = 17
    label_y: int = 7
    font: int = 0
    font_size: int = 10
    bg_color: int = -262144
    fg_color: int = -1
    label_color: int = -1

    def __str__(self) -> str:
        return (
            f"#X obj {self.position} bng {self.size} {self.hold} {self.interrupt} "
            f"{self.init} {self.send} {self.receive} {self.label} "
            f"{self.label_x} {self.label_y} {self.font} {self.font_size} "
            f"{self.bg_color} {self.fg_color} {self.label_color};"
        )


@dataclass(frozen=True)
class PdTgl:
    """Toggle button (#X obj ... tgl)."""

    position: Position
    size: int = 15
    init: int = 0
    send: str = "empty"
    receive: str = "empty"
    label: str = "empty"
    label_x: int = 17
    label_y: int = 7
    font: int = 0
    font_size: int = 10
    bg_color: int = -262144
    fg_color: int = -1
    label_color: int = -1
    init_value: int = 0
    default_value: int = 0

    def __str__(self) -> str:
        return (
            f"#X obj {self.position} tgl {self.size} {self.init} "
            f"{self.send} {self.receive} {self.label} "
            f"{self.label_x} {self.label_y} {self.font} {self.font_size} "
            f"{self.bg_color} {self.fg_color} {self.label_color} "
            f"{self.init_value} {self.default_value};"
        )


# Union type for all elements that can appear in a patch
PdElement = Union[
    PdObj,
    PdMsg,
    PdFloatatom,
    PdSymbolatom,
    PdText,
    PdArray,
    PdConnect,
    PdCoords,
    PdBng,
    PdTgl,
    "PdSubpatch",
]


@dataclass
class PdSubpatch:
    """A subpatch containing its own canvas and elements."""

    canvas: CanvasProperties
    elements: List[PdElement] = field(default_factory=list)
    restore: Optional[PdRestore] = None

    def __str__(self) -> str:
        lines = [f"#N canvas {self.canvas};"]
        for elem in self.elements:
            if isinstance(elem, PdSubpatch):
                lines.append(str(elem))
            else:
                lines.append(str(elem))
        if self.restore:
            lines.append(str(self.restore))
        return "\n".join(lines)


@dataclass
class PdPatch:
    """Root AST node representing a complete PureData patch."""

    canvas: CanvasProperties
    elements: List[PdElement] = field(default_factory=list)

    def __str__(self) -> str:
        return serialize(self)

    def get_objects(
        self,
    ) -> List[Union[PdObj, PdMsg, PdFloatatom, PdSymbolatom, PdBng, PdTgl, PdSubpatch]]:
        """Get all connectable objects (not connections, arrays, or coords)."""
        return [
            e
            for e in self.elements
            if isinstance(
                e, (PdObj, PdMsg, PdFloatatom, PdSymbolatom, PdBng, PdTgl, PdSubpatch)
            )
        ]

    def get_connections(self) -> List[PdConnect]:
        """Get all connections in the patch."""
        return [e for e in self.elements if isinstance(e, PdConnect)]


# Parser


class ParseError(Exception):
    """Raised when parsing a PureData file fails."""

    pass


def _tokenize(text: str) -> List[str]:
    """Tokenize a PureData line, respecting escaped characters and commas."""
    tokens = []
    current = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            # Escaped character - keep the backslash and next char
            current.append(char)
            current.append(text[i + 1])
            i += 2
        elif char in " \t":
            if current:
                tokens.append("".join(current))
                current = []
            i += 1
        elif char == ";":
            if current:
                tokens.append("".join(current))
                current = []
            # Don't include trailing semicolon in tokens
            i += 1
        else:
            current.append(char)
            i += 1
    if current:
        tokens.append("".join(current))
    return tokens


def _parse_int(s: str, default: int = 0) -> int:
    """Parse an integer, returning default on failure."""
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def _parse_float(s: str, default: float = 0.0) -> float:
    """Parse a float, returning default on failure."""
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _parse_canvas(tokens: List[str]) -> CanvasProperties:
    """Parse #N canvas line."""
    # #N canvas x y width height [name open_on_load | font_size]
    if len(tokens) < 6:
        raise ParseError(f"Invalid canvas line: {tokens}")

    x = _parse_int(tokens[2])
    y = _parse_int(tokens[3])
    width = _parse_int(tokens[4])
    height = _parse_int(tokens[5])

    # Check if this is a subpatch (has name) or main patch (has font_size)
    if len(tokens) >= 8 and not tokens[6].isdigit():
        # Subpatch: name and open_on_load
        name = tokens[6]
        open_on_load = _parse_int(tokens[7]) if len(tokens) > 7 else 0
        return CanvasProperties(x, y, width, height, 10, name, open_on_load)
    else:
        # Main patch: font_size
        font_size = _parse_int(tokens[6]) if len(tokens) > 6 else 10
        return CanvasProperties(x, y, width, height, font_size)


def _parse_obj(tokens: List[str]) -> PdElement:
    """Parse #X obj line."""
    # #X obj x y class_name [args...]
    if len(tokens) < 5:
        raise ParseError(f"Invalid obj line: {tokens}")

    pos = Position(_parse_int(tokens[2]), _parse_int(tokens[3]))
    class_name = tokens[4]
    args = tuple(tokens[5:]) if len(tokens) > 5 else ()

    # Check for special GUI objects
    if class_name == "bng" and len(args) >= 14:
        return PdBng(
            position=pos,
            size=_parse_int(args[0], 15),
            hold=_parse_int(args[1], 250),
            interrupt=_parse_int(args[2], 50),
            init=_parse_int(args[3], 0),
            send=args[4] if len(args) > 4 else "empty",
            receive=args[5] if len(args) > 5 else "empty",
            label=args[6] if len(args) > 6 else "empty",
            label_x=_parse_int(args[7], 17) if len(args) > 7 else 17,
            label_y=_parse_int(args[8], 7) if len(args) > 8 else 7,
            font=_parse_int(args[9], 0) if len(args) > 9 else 0,
            font_size=_parse_int(args[10], 10) if len(args) > 10 else 10,
            bg_color=_parse_int(args[11], -262144) if len(args) > 11 else -262144,
            fg_color=_parse_int(args[12], -1) if len(args) > 12 else -1,
            label_color=_parse_int(args[13], -1) if len(args) > 13 else -1,
        )
    elif class_name == "tgl" and len(args) >= 15:
        return PdTgl(
            position=pos,
            size=_parse_int(args[0], 15),
            init=_parse_int(args[1], 0),
            send=args[2] if len(args) > 2 else "empty",
            receive=args[3] if len(args) > 3 else "empty",
            label=args[4] if len(args) > 4 else "empty",
            label_x=_parse_int(args[5], 17) if len(args) > 5 else 17,
            label_y=_parse_int(args[6], 7) if len(args) > 6 else 7,
            font=_parse_int(args[7], 0) if len(args) > 7 else 0,
            font_size=_parse_int(args[8], 10) if len(args) > 8 else 10,
            bg_color=_parse_int(args[9], -262144) if len(args) > 9 else -262144,
            fg_color=_parse_int(args[10], -1) if len(args) > 10 else -1,
            label_color=_parse_int(args[11], -1) if len(args) > 11 else -1,
            init_value=_parse_int(args[12], 0) if len(args) > 12 else 0,
            default_value=_parse_int(args[13], 0) if len(args) > 13 else 0,
        )

    return PdObj(pos, class_name, args)


def _parse_msg(tokens: List[str]) -> PdMsg:
    """Parse #X msg line."""
    # #X msg x y content...
    if len(tokens) < 4:
        raise ParseError(f"Invalid msg line: {tokens}")

    pos = Position(_parse_int(tokens[2]), _parse_int(tokens[3]))
    content = " ".join(tokens[4:]) if len(tokens) > 4 else ""
    return PdMsg(pos, content)


def _parse_floatatom(tokens: List[str]) -> PdFloatatom:
    """Parse #X floatatom line."""
    # #X floatatom x y width lower upper label_pos label receive send
    if len(tokens) < 4:
        raise ParseError(f"Invalid floatatom line: {tokens}")

    pos = Position(_parse_int(tokens[2]), _parse_int(tokens[3]))
    width = _parse_int(tokens[4], 5) if len(tokens) > 4 else 5
    lower = _parse_float(tokens[5], 0) if len(tokens) > 5 else 0
    upper = _parse_float(tokens[6], 0) if len(tokens) > 6 else 0
    label_pos = _parse_int(tokens[7], 0) if len(tokens) > 7 else 0
    label = tokens[8] if len(tokens) > 8 else "-"
    receive = tokens[9] if len(tokens) > 9 else "-"
    send = tokens[10] if len(tokens) > 10 else "-"

    return PdFloatatom(pos, width, lower, upper, label_pos, label, receive, send)


def _parse_symbolatom(tokens: List[str]) -> PdSymbolatom:
    """Parse #X symbolatom line."""
    if len(tokens) < 4:
        raise ParseError(f"Invalid symbolatom line: {tokens}")

    pos = Position(_parse_int(tokens[2]), _parse_int(tokens[3]))
    width = _parse_int(tokens[4], 10) if len(tokens) > 4 else 10
    lower = _parse_float(tokens[5], 0) if len(tokens) > 5 else 0
    upper = _parse_float(tokens[6], 0) if len(tokens) > 6 else 0
    label_pos = _parse_int(tokens[7], 0) if len(tokens) > 7 else 0
    label = tokens[8] if len(tokens) > 8 else "-"
    receive = tokens[9] if len(tokens) > 9 else "-"
    send = tokens[10] if len(tokens) > 10 else "-"

    return PdSymbolatom(pos, width, lower, upper, label_pos, label, receive, send)


def _parse_text(tokens: List[str]) -> PdText:
    """Parse #X text line."""
    if len(tokens) < 4:
        raise ParseError(f"Invalid text line: {tokens}")

    pos = Position(_parse_int(tokens[2]), _parse_int(tokens[3]))
    content = " ".join(tokens[4:]) if len(tokens) > 4 else ""
    return PdText(pos, content)


def _parse_array(tokens: List[str]) -> PdArray:
    """Parse #X array line."""
    # #X array name size dtype save_flag
    if len(tokens) < 5:
        raise ParseError(f"Invalid array line: {tokens}")

    name = tokens[2]
    size = _parse_int(tokens[3])
    dtype = tokens[4] if len(tokens) > 4 else "float"
    save_flag = _parse_int(tokens[5], 0) if len(tokens) > 5 else 0

    return PdArray(name, size, dtype, save_flag)


def _parse_connect(tokens: List[str]) -> PdConnect:
    """Parse #X connect line."""
    # #X connect source_id outlet_id sink_id inlet_id
    if len(tokens) < 6:
        raise ParseError(f"Invalid connect line: {tokens}")

    return PdConnect(
        _parse_int(tokens[2]),
        _parse_int(tokens[3]),
        _parse_int(tokens[4]),
        _parse_int(tokens[5]),
    )


def _parse_coords(tokens: List[str]) -> PdCoords:
    """Parse #X coords line."""
    if len(tokens) < 9:
        raise ParseError(f"Invalid coords line: {tokens}")

    return PdCoords(
        x_from=_parse_float(tokens[2]),
        y_from=_parse_float(tokens[3]),
        x_to=_parse_float(tokens[4]),
        y_to=_parse_float(tokens[5]),
        width=_parse_int(tokens[6]),
        height=_parse_int(tokens[7]),
        graph_on_parent=_parse_int(tokens[8], 1) if len(tokens) > 8 else 1,
        hide_name=_parse_int(tokens[9], 0) if len(tokens) > 9 else 0,
        x_margin=_parse_int(tokens[10], 0) if len(tokens) > 10 else 0,
        y_margin=_parse_int(tokens[11], 0) if len(tokens) > 11 else 0,
    )


def _parse_restore(tokens: List[str]) -> PdRestore:
    """Parse #X restore line."""
    # #X restore x y pd name
    if len(tokens) < 6:
        raise ParseError(f"Invalid restore line: {tokens}")

    pos = Position(_parse_int(tokens[2]), _parse_int(tokens[3]))
    # tokens[4] should be 'pd'
    name = " ".join(tokens[5:]) if len(tokens) > 5 else ""
    return PdRestore(pos, name)


def _preprocess(content: str) -> str:
    """Preprocess PureData file content.

    Handles line continuations (backslash at end of line) and
    normalizes line endings.
    """
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Handle line continuations
    content = content.replace("\\\n", "")

    return content


def _split_statements(content: str) -> List[str]:
    """Split content into individual PureData statements.

    Statements end with semicolons, but semicolons can be escaped.
    """
    statements = []
    current = []
    i = 0

    while i < len(content):
        char = content[i]
        if char == "\\" and i + 1 < len(content):
            # Escaped character
            current.append(char)
            current.append(content[i + 1])
            i += 2
        elif char == ";":
            current.append(char)
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
        else:
            current.append(char)
            i += 1

    # Handle trailing content without semicolon
    remaining = "".join(current).strip()
    if remaining:
        statements.append(remaining)

    return statements


def parse(content: str) -> PdPatch:
    """Parse PureData patch content into an AST.

    Parameters
    ----------
    content : str
        The content of a .pd file

    Returns
    -------
    PdPatch
        The parsed AST

    Raises
    ------
    ParseError
        If the content cannot be parsed
    """
    content = _preprocess(content)
    statements = _split_statements(content)

    if not statements:
        raise ParseError("Empty patch file")

    # Parse using a stack for nested subpatches
    patch_stack: List[Tuple[CanvasProperties, List[PdElement]]] = []
    current_canvas: Optional[CanvasProperties] = None
    current_elements: List[PdElement] = []

    for stmt in statements:
        tokens = _tokenize(stmt)
        if not tokens:
            continue

        directive = tokens[0] if tokens else ""
        cmd = tokens[1] if len(tokens) > 1 else ""

        if directive == "#N" and cmd == "canvas":
            canvas = _parse_canvas(tokens)
            if current_canvas is not None:
                # Starting a subpatch - push current state
                patch_stack.append((current_canvas, current_elements))
                current_elements = []
            current_canvas = canvas

        elif directive == "#X":
            if current_canvas is None:
                raise ParseError(f"Element before canvas: {stmt}")

            if cmd == "obj":
                current_elements.append(_parse_obj(tokens))
            elif cmd == "msg":
                current_elements.append(_parse_msg(tokens))
            elif cmd == "floatatom":
                current_elements.append(_parse_floatatom(tokens))
            elif cmd == "symbolatom":
                current_elements.append(_parse_symbolatom(tokens))
            elif cmd == "text":
                current_elements.append(_parse_text(tokens))
            elif cmd == "array":
                current_elements.append(_parse_array(tokens))
            elif cmd == "connect":
                current_elements.append(_parse_connect(tokens))
            elif cmd == "coords":
                current_elements.append(_parse_coords(tokens))
            elif cmd == "restore":
                # End of subpatch
                restore = _parse_restore(tokens)
                subpatch = PdSubpatch(current_canvas, current_elements, restore)

                if patch_stack:
                    # Pop parent state
                    current_canvas, current_elements = patch_stack.pop()
                    current_elements.append(subpatch)
                else:
                    raise ParseError("Restore without matching canvas")
            elif cmd == "pop":
                # Some patches use #X pop instead of #X restore
                pass
            # Add more commands as needed
            else:
                # Unknown command - store as generic object
                if len(tokens) >= 4:
                    pos = Position(_parse_int(tokens[2], 0), _parse_int(tokens[3], 0))
                    current_elements.append(PdObj(pos, cmd, tuple(tokens[4:])))

    if current_canvas is None:
        raise ParseError("No canvas found in patch")

    return PdPatch(current_canvas, current_elements)


def parse_file(filepath: str) -> PdPatch:
    """Parse a PureData file into an AST.

    Parameters
    ----------
    filepath : str
        Path to the .pd file

    Returns
    -------
    PdPatch
        The parsed AST
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return parse(content)


# Serializer


def serialize(patch: PdPatch) -> str:
    """Serialize a PdPatch AST back to PureData format.

    Parameters
    ----------
    patch : PdPatch
        The AST to serialize

    Returns
    -------
    str
        The PureData file content
    """
    lines = [f"#N canvas {patch.canvas};"]

    for elem in patch.elements:
        if isinstance(elem, PdSubpatch):
            lines.append(_serialize_subpatch(elem))
        else:
            lines.append(str(elem))

    return "\n".join(lines)


def _serialize_subpatch(subpatch: PdSubpatch) -> str:
    """Serialize a subpatch."""
    lines = [f"#N canvas {subpatch.canvas};"]

    for elem in subpatch.elements:
        if isinstance(elem, PdSubpatch):
            lines.append(_serialize_subpatch(elem))
        else:
            lines.append(str(elem))

    if subpatch.restore:
        lines.append(str(subpatch.restore))

    return "\n".join(lines)


def serialize_to_file(patch: PdPatch, filepath: str) -> None:
    """Serialize a PdPatch AST to a file.

    Parameters
    ----------
    patch : PdPatch
        The AST to serialize
    filepath : str
        Path to the output .pd file
    """
    content = serialize(patch)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# Bridge functions between builder API and AST


def from_builder(patch: "api.Patcher") -> PdPatch:
    """Convert a builder Patcher to an AST PdPatch.

    Parameters
    ----------
    patch : api.Patcher
        A patch created using the builder API

    Returns
    -------
    PdPatch
        The equivalent AST representation
    """
    from . import api

    canvas = CanvasProperties()
    elements: List[PdElement] = []

    for node in patch.nodes:
        if isinstance(node, api.Obj):
            text = node.parameters["text"]
            parts = text.split(None, 1)
            class_name = parts[0] if parts else ""
            args = tuple(parts[1].split()) if len(parts) > 1 else ()
            pos = Position(node.parameters["x_pos"], node.parameters["y_pos"])
            elements.append(PdObj(pos, class_name, args))

        elif isinstance(node, api.Msg):
            pos = Position(node.parameters["x_pos"], node.parameters["y_pos"])
            elements.append(PdMsg(pos, node.parameters["text"]))

        elif isinstance(node, api.Float):
            p = node.parameters
            pos = Position(p["x_pos"], p["y_pos"])
            elements.append(
                PdFloatatom(
                    pos,
                    p["width"],
                    p["lower_limit"],
                    p["upper_limit"],
                    0,
                    p["label"],
                    p["receive"],
                    p["send"],
                )
            )

        elif isinstance(node, api.Array):
            p = node.parameters
            elements.append(
                PdArray(p["name"], p["length"], p["element_type"], p["save_flag"])
            )

        elif isinstance(node, api.Subpatch):
            # Recursively convert subpatch
            inner_ast = from_builder(node.src)
            p = node.parameters
            pos = Position(p["x_pos"], p["y_pos"])
            subpatch_canvas = CanvasProperties(0, 0, 300, 180, 10, "(subpatch)", 0)
            restore = PdRestore(pos, p["name"])
            elements.append(PdSubpatch(subpatch_canvas, inner_ast.elements, restore))

    # Add connections
    for conn in patch.connections:
        elements.append(
            PdConnect(conn.source, conn.outlet_index, conn.sink, conn.inlet_index)
        )

    return PdPatch(canvas, elements)


def to_builder(ast: PdPatch) -> "api.Patcher":
    """Convert an AST PdPatch to a builder Patcher.

    Parameters
    ----------
    ast : PdPatch
        An AST patch

    Returns
    -------
    api.Patcher
        A builder Patcher that can be modified

    Notes
    -----
    This creates a new Patcher with absolute positioning
    (new_row and new_col are not used).
    """
    from . import api

    patch = api.Patcher()

    # First pass: create all nodes (non-connections)
    node_map: List[Optional[api.Node]] = []  # Track nodes for linking
    node: api.Node
    for elem in ast.elements:
        if isinstance(elem, PdObj):
            node = patch.add(elem.text, x_pos=elem.position.x, y_pos=elem.position.y)
            node_map.append(node)

        elif isinstance(elem, PdMsg):
            node = patch.add_msg(
                elem.content, x_pos=elem.position.x, y_pos=elem.position.y
            )
            node_map.append(node)

        elif isinstance(elem, PdFloatatom):
            node = api.Float(
                elem.position.x,
                elem.position.y,
                elem.width,
                int(elem.upper_limit),
                int(elem.lower_limit),
                elem.label,
                elem.receive,
                elem.send,
            )
            patch.nodes.append(node)
            node_map.append(node)

        elif isinstance(elem, PdSymbolatom):
            # Treat as a generic object for now
            node = patch.add("symbolatom", x_pos=elem.position.x, y_pos=elem.position.y)
            node_map.append(node)

        elif isinstance(elem, PdText):
            # Store as comment/generic obj
            node = patch.add(
                f"text {elem.content}", x_pos=elem.position.x, y_pos=elem.position.y
            )
            node_map.append(node)

        elif isinstance(elem, PdArray):
            node = patch.add_array(elem.name, elem.size)
            node_map.append(node)

        elif isinstance(elem, PdSubpatch):
            # Recursively convert subpatch
            inner_patch = to_builder(PdPatch(elem.canvas, elem.elements))
            name = elem.restore.name if elem.restore else "subpatch"
            pos = elem.restore.position if elem.restore else Position(0, 0)
            node = patch.add_subpatch(name, inner_patch, x_pos=pos.x, y_pos=pos.y)
            node_map.append(node)

        elif isinstance(elem, (PdBng, PdTgl)):
            # GUI objects - store as generic obj
            node = patch.add(
                str(elem).replace("#X obj ", "").rstrip(";"),
                x_pos=elem.position.x,
                y_pos=elem.position.y,
            )
            node_map.append(node)

        elif isinstance(elem, PdConnect):
            # Skip connections in first pass
            pass

        else:
            node_map.append(None)  # Placeholder for unknown elements

    # Second pass: add connections using link()
    for elem in ast.elements:
        if isinstance(elem, PdConnect):
            source = (
                node_map[elem.source_id] if elem.source_id < len(node_map) else None
            )
            sink = node_map[elem.sink_id] if elem.sink_id < len(node_map) else None
            if source is not None and sink is not None:
                patch.link(source, sink, outlet=elem.outlet_id, inlet=elem.inlet_id)

    return patch


# AST manipulation utilities


def transform(patch: PdPatch, transformer) -> PdPatch:
    """Apply a transformation function to all elements in a patch.

    Parameters
    ----------
    patch : PdPatch
        The patch to transform
    transformer : callable
        A function that takes a PdElement and returns a PdElement or None.
        If None is returned, the element is removed.

    Returns
    -------
    PdPatch
        A new patch with transformed elements
    """
    new_elements = []
    for elem in patch.elements:
        if isinstance(elem, PdSubpatch):
            # Recursively transform subpatch
            inner = transform(PdPatch(elem.canvas, elem.elements), transformer)
            transformed = transformer(
                PdSubpatch(elem.canvas, inner.elements, elem.restore)
            )
        else:
            transformed = transformer(elem)

        if transformed is not None:
            new_elements.append(transformed)

    return PdPatch(patch.canvas, new_elements)


def find_objects(patch: PdPatch, predicate) -> List[PdElement]:
    """Find all elements in a patch matching a predicate.

    Parameters
    ----------
    patch : PdPatch
        The patch to search
    predicate : callable
        A function that takes a PdElement and returns bool

    Returns
    -------
    list of PdElement
        All matching elements
    """
    results = []
    for elem in patch.elements:
        if predicate(elem):
            results.append(elem)
        if isinstance(elem, PdSubpatch):
            # Recursively search subpatch
            results.extend(find_objects(PdPatch(elem.canvas, elem.elements), predicate))
    return results


def rename_sends_receives(patch: PdPatch, old_name: str, new_name: str) -> PdPatch:
    """Rename all send/receive symbols in a patch.

    Parameters
    ----------
    patch : PdPatch
        The patch to modify
    old_name : str
        The name to find
    new_name : str
        The replacement name

    Returns
    -------
    PdPatch
        A new patch with renamed symbols
    """

    def rename(elem):
        if isinstance(elem, PdFloatatom):
            return PdFloatatom(
                elem.position,
                elem.width,
                elem.lower_limit,
                elem.upper_limit,
                elem.label_pos,
                new_name if elem.label == old_name else elem.label,
                new_name if elem.receive == old_name else elem.receive,
                new_name if elem.send == old_name else elem.send,
            )
        elif isinstance(elem, PdObj):
            # Check for send/receive objects
            if elem.class_name in (
                "send",
                "s",
                "receive",
                "r",
                "send~",
                "s~",
                "receive~",
                "r~",
            ):
                if elem.args and elem.args[0] == old_name:
                    return PdObj(
                        elem.position, elem.class_name, (new_name,) + elem.args[1:]
                    )
        return elem

    return transform(patch, rename)
