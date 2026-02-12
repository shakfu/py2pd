Architecture
============

Overview
--------

py2pd provides two complementary APIs for working with PureData patches:

- **Builder API** (``api.py``) -- Mutable, imperative patch construction. Best for
  creating patches programmatically.
- **AST API** (``ast.py``) -- Frozen dataclasses for lossless round-trip parsing. Best
  for reading, analyzing, and transforming existing patches.

Bridge functions connect them: ``from_builder()`` converts a ``Patcher`` to a
``PdPatch``, and ``to_builder()`` goes the other way.

Two optional integration modules extend the core:

- **cypd** (``integrations/cypd.py``) -- Patch validation via libpd.
- **hvcc** (``integrations/hvcc.py``) -- Heavy Compiler Collection integration for
  compiling patches to C/C++.

A **discovery** module (``discover.py``) provides platform-aware filesystem scanning
for ``.pd`` abstractions and binary externals.


Class Diagrams
--------------

Node Hierarchy (Builder API)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All builder nodes inherit from ``Node``. Each stores its state in a
``self.parameters`` dict, which enables uniform serialization and bridging.

::

    Node (base)
     +-- Obj (generic #X obj)
     |    +-- Abstraction (external .pd file reference)
     +-- Msg (#X msg)
     +-- Float (#X floatatom)
     +-- Comment (#X text)
     +-- Subpatch (#N canvas ... #X restore)
     +-- Array (#X array)
     +-- Bang, Toggle, Symbol, NumberBox    (GUI - IEM)
     +-- VSlider, HSlider, VRadio, HRadio  (GUI - IEM)
     +-- Canvas, VU                         (GUI - IEM)

``Obj`` is the workhorse -- it represents any ``#X obj`` line.
``Abstraction`` extends ``Obj`` to reference external ``.pd`` files, with I/O counts
auto-inferred from the source file. The 10 GUI types each have dedicated constructors
exposing IEM-specific parameters (colors, labels, ranges, etc.).

AST Hierarchy
~~~~~~~~~~~~~

AST types are frozen dataclasses. Immutability makes ``transform()`` safe -- no
accidental mutation of shared nodes.

::

    PdElement (base)
     +-- PdObj, PdMsg, PdFloatAtom, PdSymbolAtom, PdText
     +-- PdArray, PdArrayData, PdCoords, PdDeclare
     +-- PdSubpatch (contains elements list)
     +-- PdConnect (source/sink index pairs)
     +-- PdBng, PdTgl, PdNbx, PdVsl, PdHsl  (GUI)
     +-- PdVradio, PdHradio, PdCnv, PdVu     (GUI)

    PdPatch (root: CanvasProperties + elements list)

``PdPatch`` is the root container. ``PdSubpatch`` nests recursively.
``PdDeclare`` represents ``#X declare`` statements (parsed but skipped in
``to_builder()`` since the builder has no equivalent).

Patcher Composition
~~~~~~~~~~~~~~~~~~~

::

    Patcher
     +-- nodes: List[Node]
     +-- connections: List[Connection]
     +-- layout: LayoutManager
     +-- filename: Optional[str]

``Connection`` is a ``(source_index, outlet, sink_index, inlet)`` tuple.
``LayoutManager`` tracks cursor position for automatic node placement.


Data Flow
---------

Patch Creation
~~~~~~~~~~~~~~

::

    Patcher -> add() / add_*() -> Node instances
                                      |
                                  link() -> Connection instances
                                      |
                                  str(Patcher) -> .pd text

``add()`` creates nodes and appends them to ``Patcher.nodes``. ``link()`` validates
inlet/outlet indices using ``PD_OBJECT_REGISTRY`` (which maps ~80 common Pd objects
to known I/O counts) and appends a ``Connection``. ``str(Patcher)`` serializes the
``#N canvas`` header, each node's ``__str__()``, and each connection's ``__str__()``.

Parsing
~~~~~~~

::

    .pd text -> parse() -> PdPatch (frozen AST)

``parse()`` preprocesses the raw text (normalizing line continuations), splits into
statements, then dispatches each statement to type-specific parsers. The result is
a ``PdPatch`` tree of frozen dataclasses.

Round-Trip Bridging
~~~~~~~~~~~~~~~~~~~

::

    Patcher  --from_builder()--> PdPatch
    PdPatch  --to_builder()----> Patcher

``from_builder()`` converts mutable builder nodes to frozen AST nodes.
``to_builder()`` reconstructs mutable ``Patcher`` state from an AST tree.
``PdDeclare`` nodes are skipped during ``to_builder()`` (no builder equivalent)
and do not affect object indexing for connections.

Validation
~~~~~~~~~~

::

    Patcher or PdPatch -> validate_patch()    (cypd/libpd)
    Patcher or PdPatch -> validate_for_hvcc() (hvcc)

``validate_patch()`` serializes the patch to a temp file, opens it in libpd, and
collects print output. A ``_PrintAccumulator`` buffers libpd's word-fragment
callbacks into complete lines, which are then classified as errors or warnings.

``validate_for_hvcc()`` walks ``Obj``/``PdObj`` nodes and checks each against the
``HVCC_SUPPORTED_OBJECTS`` set (~163 objects). GUI nodes are skipped (they are not
``Obj`` instances). Subpatches are recursed into.

Optimization
~~~~~~~~~~~~

``Patcher.optimize()`` runs three passes:

1. **Dedup** -- Remove duplicate connections.
2. **Pass-through collapse** -- Collapse nodes that simply pass signals through
   (e.g., ``[trigger a]`` with one outlet).
3. **Unused removal** -- Remove nodes with no connections (excluding protected
   types like ``dac~``, ``adc~``, GUI objects).

Layout
~~~~~~

``_resolve_position()`` tracks a cursor that advances as nodes are added.
``auto_layout()`` performs a topological sort of the connection graph and assigns
positions to minimize crossing.


Design Decisions
----------------

Why Two APIs?
~~~~~~~~~~~~~

The Builder API is ergonomic for construction -- you call ``add()``, ``link()``, and
get a patch. But it is lossy: it doesn't preserve every formatting detail of an
existing ``.pd`` file.

The AST API preserves every detail for lossless round-trip of existing patches. But
frozen dataclasses would make the construction API painful (no in-place mutation,
no position tracking).

Neither alone covers both use cases well, so both exist with bridge functions
between them.

Why Frozen AST Dataclasses?
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Immutability makes ``transform()`` safe. When you walk an AST and produce a new one,
there is no risk of accidentally mutating a shared node. It forces explicit
reconstruction, which is the correct model for tree transformations.

Why Mutable Builder?
~~~~~~~~~~~~~~~~~~~~

Patch construction is inherently stateful: position tracking, connection indexing,
and sequential node addition all benefit from mutation. A frozen builder would
require threading state through every call, making the API awkward.

Why a ``parameters`` Dict?
~~~~~~~~~~~~~~~~~~~~~~~~~~

All ``Node`` subclasses store state in ``self.parameters``. This enables:

- Uniform serialization (``__str__`` iterates dict values)
- Uniform bridging (``from_builder``/``to_builder`` iterate dict keys)
- Easy extension (new parameters don't require schema changes)

The trade-off is no IDE autocomplete on parameter access. Constructor arguments
provide the discoverability instead.

Why ``PD_OBJECT_REGISTRY``?
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pd objects have variable I/O counts that depend on creation arguments. For example,
``[trigger a b c]`` has 1 inlet and 3 outlets, while ``[trigger a]`` has 1 inlet and
1 outlet. The registry provides known counts for common objects; ``None`` means the
count is variable and cannot be statically validated.

Why Lazy ``_ensure_libpd()``?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

libpd's ``release()`` function is fragile and can crash the process. The
init-once-never-release pattern in ``_ensure_libpd()`` avoids this. The function
is called lazily on first validation, not at import time, so the optional
dependency doesn't affect users who don't need it.

Why ``escape()`` / ``unescape()``?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pd format reserves certain characters: semicolons terminate statements, commas
separate messages, and dollar signs denote patch-local variables. The format uses
``\;``, ``\,``, and ``\$`` as escape sequences. All node text passes through
``escape()`` on write and ``unescape()`` on read to handle this transparently.


Extension Points
----------------

Adding a New Node Type
~~~~~~~~~~~~~~~~~~~~~~

1. Subclass ``Node`` in ``api.py``.
2. Implement ``__init__`` (populate ``self.parameters``), ``__str__`` (Pd format
   output), ``__repr__``, and the ``dimensions`` property.
3. Set ``num_inlets`` and ``num_outlets`` class attributes.
4. Add an ``add_*()`` convenience method on ``Patcher``.
5. Add to ``_PROTECTED_TYPES`` if the node should survive ``optimize()``.

Adding an AST Node Type
~~~~~~~~~~~~~~~~~~~~~~~~

1. Add a frozen dataclass to ``ast.py``, inheriting from ``PdElement``.
2. Update the ``_parse_*`` functions to recognize the new format.
3. Update ``_serialize_element`` to emit the correct Pd text.
4. Update ``from_builder()`` and ``to_builder()`` for bridge support.

Custom Layout
~~~~~~~~~~~~~

Subclass ``LayoutManager`` and override ``next_position()``. Pass the custom
layout manager to ``Patcher(layout=...)``.

New Integration Module
~~~~~~~~~~~~~~~~~~~~~~

1. Add a new module under ``integrations/``.
2. Re-export public symbols from ``integrations/__init__.py``.
3. Use the optional dependency pattern::

       try:
           import some_library
       except ImportError:
           raise ImportError(
               "some_library is required: pip install py2pd[some_extra]"
           )

4. Add the extra to ``pyproject.toml`` under ``[project.optional-dependencies]``.

Expanding ``PD_OBJECT_REGISTRY``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add entries to the dict in ``api.py`` as ``"name": (num_inlets, num_outlets)``.
Use ``None`` for variable counts that depend on creation arguments. The registry
is used by ``link()`` for connection validation and by ``validate_connections()``
for reporting.
