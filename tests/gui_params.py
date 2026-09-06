"""One distinctive value per builder parameter, shared by the GUI matrices.

The values are deliberately all different. Two adjacent fields that both hold a
default of 0 can be written in the wrong order and still round-trip, which is
how ``#X floatatom`` shipped with its limits reversed and its ``label_pos``
field missing. Distinctive values make a swap or an omission visible.

Constraints the values must respect:

- ``min_val`` is positive, so ``log_flag=1`` is a legal range for a slider.
- Colours are legacy packed negative integers, distinct from one another.
- Symbols are three letters, so no field can pass for another.
"""

import inspect
from typing import Any, Dict, Tuple

from py2pd import Patcher

# Every add_* method that writes a GUI statement.
GUI_METHODS: Tuple[str, ...] = (
    "add_bang",
    "add_canvas",
    "add_float",
    "add_hradio",
    "add_hslider",
    "add_numberbox",
    "add_symbol",
    "add_toggle",
    "add_vradio",
    "add_vslider",
    "add_vu",
)

# Position is supplied by the test, not by the table.
_POSITIONAL = frozenset({"self", "new_row", "new_col", "x_pos", "y_pos"})

PARAM_VALUES: Dict[str, Any] = {
    "size": 19,
    "width": 37,
    "height": 41,
    "number": 7,
    "min_val": 3.5,
    "max_val": 97.0,
    "lower_limit": 5.5,
    "upper_limit": 91.0,
    "label": "lbl",
    "send": "snd",
    "receive": "rcv",
    "label_pos": 3,
    "label_x": 11,
    "label_y": 13,
    "font": 1,
    "font_size": 9,
    "hold": 251,
    "interrupt": 53,
    "init": 1,
    "init_value": 1,
    "default_value": 1,
    "steady": 0,
    "scale": 0,
    "new_old": 1,
    "log_flag": 1,
    "log_height": 123,
    "bg_color": -262144,
    "fg_color": -262145,
    "label_color": -262146,
}


def gui_parameters(method: str) -> Tuple[str, ...]:
    """Names of every keyword parameter *method* accepts, position aside."""
    sig = inspect.signature(getattr(Patcher, method))
    return tuple(
        name
        for name, param in sig.parameters.items()
        if name not in _POSITIONAL and param.default is not inspect.Parameter.empty
    )


def kwargs_for(method: str) -> Dict[str, Any]:
    """Every parameter of *method*, set to its distinctive value.

    Raises
    ------
    KeyError
        If a parameter has no entry in ``PARAM_VALUES``. A new GUI parameter
        must be given a value here before the matrices will cover it.
    """
    return {name: PARAM_VALUES[name] for name in gui_parameters(method)}


# The AST node each GUI method writes. The AST layer was corrected against
# PureData-authored files, so it is the reference for what each field means.
AST_NODE_NAMES: Dict[str, str] = {
    "add_bang": "PdBng",
    "add_canvas": "PdCnv",
    "add_float": "PdFloatAtom",
    "add_hradio": "PdHradio",
    "add_hslider": "PdHsl",
    "add_numberbox": "PdNbx",
    "add_symbol": "PdSymbolAtom",
    "add_toggle": "PdTgl",
    "add_vradio": "PdVradio",
    "add_vslider": "PdVsl",
    "add_vu": "PdVu",
}


def ast_node_for(method: str) -> type:
    """The AST class *method* is expected to serialize to."""
    from py2pd import ast

    return getattr(ast, AST_NODE_NAMES[method])  # type: ignore[no-any-return]


# Every add_* method that does not write a GUI statement. Kept here so the
# coverage guard can assert that no builder method escapes both matrices.
NON_GUI_METHODS: Tuple[str, ...] = (
    "add_abstraction",
    "add_array",
    "add_comment",
    "add_link",
    "add_msg",
    "add_subpatch",
)


def all_add_methods() -> Tuple[str, ...]:
    """Every ``add_*`` method the builder exposes."""
    return tuple(sorted(name for name in dir(Patcher) if name.startswith("add_")))
