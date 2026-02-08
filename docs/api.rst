API Reference
=============

Builder API (``py2pd.api``)
---------------------------

Patcher
~~~~~~~

.. autoclass:: py2pd.api.Patcher
   :members:
   :exclude-members: filename, nodes, connections, layout

Abstraction
~~~~~~~~~~~

.. autoclass:: py2pd.api.Abstraction
   :members:

Node Types
~~~~~~~~~~

.. autoclass:: py2pd.api.Node
   :members:
   :exclude-members: num_inlets, num_outlets

.. autoclass:: py2pd.api.Obj
   :members:

.. autoclass:: py2pd.api.Msg
   :members:

.. autoclass:: py2pd.api.Float
   :members:

.. autoclass:: py2pd.api.Comment
   :members:

.. autoclass:: py2pd.api.Subpatch
   :members:
   :exclude-members: src, canvas_width, canvas_height

.. autoclass:: py2pd.api.Array
   :members:

.. autoclass:: py2pd.api.Connection
   :members:

GUI Elements
~~~~~~~~~~~~

.. autoclass:: py2pd.api.Bang
   :members:

.. autoclass:: py2pd.api.Toggle
   :members:

.. autoclass:: py2pd.api.Symbol
   :members:

.. autoclass:: py2pd.api.NumberBox
   :members:

.. autoclass:: py2pd.api.VSlider
   :members:

.. autoclass:: py2pd.api.HSlider
   :members:

.. autoclass:: py2pd.api.VRadio
   :members:

.. autoclass:: py2pd.api.HRadio
   :members:

.. autoclass:: py2pd.api.Canvas
   :members:

.. autoclass:: py2pd.api.VU
   :members:

Layout
~~~~~~

.. autoclass:: py2pd.api.LayoutManager
   :members:
   :exclude-members: row_head, row_tail

.. autoclass:: py2pd.api.GridLayoutManager
   :members:

Exceptions
~~~~~~~~~~

.. autoclass:: py2pd.api.PdConnectionError

.. autoclass:: py2pd.api.NodeNotFoundError

.. autoclass:: py2pd.api.InvalidConnectionError

.. autoclass:: py2pd.api.CycleWarning

Utility Functions
~~~~~~~~~~~~~~~~~

.. autofunction:: py2pd.api.escape

.. autofunction:: py2pd.api.unescape

.. autofunction:: py2pd.api.get_display_lines

AST API (``py2pd.ast``)
------------------------

.. automodule:: py2pd.ast
   :members:
   :undoc-members:

Discovery (``py2pd.discover``)
------------------------------

.. automodule:: py2pd.discover
   :members:
   :undoc-members:

Integrations
------------

Validation -- cypd (``py2pd.integrations.cypd``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: py2pd.integrations.cypd
   :members:
   :undoc-members:

hvcc (``py2pd.integrations.hvcc``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: py2pd.integrations.hvcc
   :members:
   :undoc-members:
