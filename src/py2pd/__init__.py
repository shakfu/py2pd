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
    COLUMN_WIDTH as COLUMN_WIDTH,
)
from .api import (
    DEFAULT_MARGIN as DEFAULT_MARGIN,
)
from .api import (
    # Layout constants
    ROW_HEIGHT as ROW_HEIGHT,
)
from .api import (
    SUBPATCH_CANVAS_HEIGHT as SUBPATCH_CANVAS_HEIGHT,
)
from .api import (
    SUBPATCH_CANVAS_WIDTH as SUBPATCH_CANVAS_WIDTH,
)
from .api import (
    PdConnectionError as PdConnectionError,
)
from .api import (
    CycleWarning as CycleWarning,
)
from .api import (
    GridLayoutManager as GridLayoutManager,
)
from .api import (
    InvalidConnectionError as InvalidConnectionError,
)
from .api import (
    LayoutManager as LayoutManager,
)
from .api import (
    NodeNotFoundError as NodeNotFoundError,
)
from .api import (
    Patcher as Patcher,
)
from .ast import (
    ParseError as ParseError,
)
from .ast import (
    from_builder as from_builder,
)

# AST API (node types available via: from py2pd.ast import PdPatch, PdObj, ...)
from .ast import (
    parse as parse,
)
from .ast import (
    parse_file as parse_file,
)
from .ast import (
    serialize as serialize,
)
from .ast import (
    serialize_to_file as serialize_to_file,
)
from .ast import (
    to_builder as to_builder,
)

__version__ = "0.1.1"
