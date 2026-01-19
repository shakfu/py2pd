"""
py2pd - Python to PureData
==========================

Write PureData patches as Python programs.

Builder API example:
  >>> from py2pd import Patcher
  >>> p = Patcher('patch.pd')
  >>> osc = p.add('osc~ 440')
  >>> dac = p.add('dac~')
  >>> p.link(osc, dac)
  >>> p.link(osc, dac, inlet=1)  # stereo
  >>> p.save()

AST API example (round-trip):
  >>> from py2pd import parse_file, serialize
  >>> ast = parse_file('input.pd')
  >>> # Modify the AST...
  >>> with open('output.pd', 'w') as f:
  ...     f.write(serialize(ast))
"""

# Builder API
from .api import (
    Patcher as Patcher,
    LayoutManager as LayoutManager,
    GridLayoutManager as GridLayoutManager,
    ConnectionError as ConnectionError,
    NodeNotFoundError as NodeNotFoundError,
    InvalidConnectionError as InvalidConnectionError,
    CycleWarning as CycleWarning,
    # Layout constants
    ROW_HEIGHT as ROW_HEIGHT,
    COLUMN_WIDTH as COLUMN_WIDTH,
    DEFAULT_MARGIN as DEFAULT_MARGIN,
    SUBPATCH_CANVAS_WIDTH as SUBPATCH_CANVAS_WIDTH,
    SUBPATCH_CANVAS_HEIGHT as SUBPATCH_CANVAS_HEIGHT,
)

# AST API
from .ast import (
    # AST node types
    PdPatch as PdPatch,
    PdObj as PdObj,
    PdMsg as PdMsg,
    PdFloatatom as PdFloatatom,
    PdSymbolatom as PdSymbolatom,
    PdText as PdText,
    PdArray as PdArray,
    PdConnect as PdConnect,
    PdCoords as PdCoords,
    PdSubpatch as PdSubpatch,
    PdRestore as PdRestore,
    PdBng as PdBng,
    PdTgl as PdTgl,
    Position as Position,
    CanvasProperties as CanvasProperties,
    # Parser/serializer
    parse as parse,
    parse_file as parse_file,
    serialize as serialize,
    serialize_to_file as serialize_to_file,
    ParseError as ParseError,
    # Bridge functions
    from_builder as from_builder,
    to_builder as to_builder,
    # Utilities
    transform as transform,
    find_objects as find_objects,
    rename_sends_receives as rename_sends_receives,
)


"""
    :""'""'""'""'"";
    *              *
    *    python    *
    *              *
    :######=.......;
      %%
    :#######""'""'""'""'"'"#######;
    *                             *                      
    *                             *
    *   p>>>o.      :d            *
    *   p    o      :d            *
    *   p<<<o.  .d<<<d            *
    *   p,      d    d            *
    *   o.      'd>>>d            *
    *                             *
    *                             *
    :######=......................;

"""
