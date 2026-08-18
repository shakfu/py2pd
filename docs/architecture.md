# Architecture

## Overview

py2pd provides two complementary APIs for working with PureData patches:

- **Builder API** (`api.py`) -- mutable, imperative patch construction. Best for creating patches programmatically.

- **AST API** (`ast.py`) -- frozen dataclasses for round-trip parsing. Best for reading, analysing, and transforming existing patches.

Bridge functions connect them: `from_builder()` converts a `Patcher` to a `PdPatch`, and `to_builder()` goes the other way.

Two optional integration modules extend the core:

- **cypd** (`integrations/cypd.py`) -- patch validation via libpd.

- **hvcc** (`integrations/hvcc.py`) -- Heavy Compiler Collection integration for compiling patches to C/C++.

A **discovery** module (`discover.py`) provides platform-aware filesystem scanning for `.pd` abstractions and binary externals.

## Class diagrams

### Node hierarchy (Builder API)

All builder nodes inherit from `Node`. Each stores its state in a `self.parameters` dict, which enables uniform serialization and bridging.

```text
Node (base)
 +-- Obj (generic #X obj)
 |    +-- Abstraction (external .pd file reference)
 +-- Msg (#X msg)
 +-- Float (#X floatatom)
 +-- Comment (#X text)
 +-- Subpatch (#N canvas ... #X restore)
 +-- Array (#X array)
 +-- Bang, Toggle, Symbol, NumberBox    (GUI - IEM)
 +-- VSlider, HSlider, VRadio, HRadio   (GUI - IEM)
 +-- Canvas, VU                         (GUI - IEM)
```

`Obj` is the workhorse -- it represents any `#X obj` line. `Abstraction` extends `Obj` to reference external `.pd` files, with I/O counts auto-inferred from the source file. The 10 GUI types each have dedicated constructors exposing IEM-specific parameters (colours, labels, ranges, and so on).

Every node exposes `pd_class_name`: the PureData class a validator should check it against (`osc~`, `bng`, `floatatom`), or `None` for nodes that are not object boxes -- messages, comments, arrays -- and for abstractions, whose name refers to a user file rather than a built-in class.

### AST hierarchy

AST types are frozen dataclasses. Immutability makes `transform()` safe -- no accidental mutation of shared nodes.

```text
PdElement (union)
 +-- PdObj, PdMsg, PdFloatAtom, PdSymbolAtom, PdText
 +-- PdArray, PdCoords, PdDeclare, PdRaw
 +-- PdSubpatch (contains elements list)
 +-- PdConnect (source/sink index pairs)
 +-- PdBng, PdTgl, PdNbx, PdVsl, PdHsl   (GUI)
 +-- PdVradio, PdHradio, PdCnv, PdVu     (GUI)

PdPatch (root: CanvasProperties + elements list + preamble)
```

`PdPatch` is the root container. `PdSubpatch` nests recursively. `PdDeclare` represents `#X declare` statements. `PdRaw` holds any statement py2pd does not model -- `#N struct`, `#X scalar`, `#A` array data, `#X f` box widths, `#X listbox` -- preserved verbatim so that parsing and re-serializing does not discard it. `PdPatch.preamble` holds statements that appear above the `#N canvas` line, which is where PureData writes struct templates.

`PdRaw.is_object` records whether PureData counts the statement as an object on the canvas. That matters because `#X connect` indices are object indices: a `#X scalar` occupies one, a `#A` line does not.

### Patcher composition

```text
Patcher
 +-- nodes: List[Node]
 +-- connections: List[Connection]
 +-- layout: LayoutManager
 +-- filename: Optional[str]
 +-- validate_links: bool
 +-- canvas_x / canvas_y / canvas_width / canvas_height / font_size
```

`Connection` is a `(source_index, outlet, sink_index, inlet)` tuple. `LayoutManager` tracks cursor position for automatic node placement. The canvas fields populate the `#N canvas` line.

## Data flow

### Patch creation

```text
Patcher -> add() / add_*() -> Node instances
                                  |
                              link() -> Connection instances
                                  |
                              str(Patcher) -> .pd text
```

Every `add_*()` method funnels through `Patcher._register()`, which appends the node and updates layout state. That single choke point is what lets a subclass inspect or reject nodes from any constructor -- `HeavyPatcher` uses it to enforce the hvcc object subset.

`link()` resolves each endpoint's index through an `id()` cache (so construction is linear rather than quadratic), validates the inlet and outlet indices, and appends a `Connection`. `str(Patcher)` serializes the `#N canvas` header, each node's `__str__()`, and each connection's `__str__()`.

### Connection validation

Inlet and outlet counts come from `lookup_object_io(text)`, which resolves the object's full text rather than only its class name. Two tables back it:

- `PD_OBJECT_REGISTRY` -- fixed `(num_inlets, num_outlets)` pairs for classes whose arity does not vary.

- `PD_OBJECT_IO_RULES` -- callables for classes whose arity depends on creation arguments: `dac~`, `adc~`, `trigger`, `pack`, `unpack`, `route`, `select`, `list`.

Anything absent from both is unknown, and validation is skipped for it -- which is the case for every external and abstraction.

An out-of-range index raises `PdConnectionError` while `validate_links` is True (the default for authoring) and warns with `PdConnectionWarning` when it is False. Reading an existing patch uses False, because the registry cannot know the arity of every object a real patch may contain, and a patch PureData accepts must remain representable. A negative index always raises, since PureData rejects it outright.

### Parsing

```text
.pd text -> parse() -> PdPatch (frozen AST)
```

`parse()` normalises line endings, splits the text into semicolon-terminated statements, tokenizes each one, then dispatches to type-specific parsers. The result is a `PdPatch` tree of frozen dataclasses.

Tokenization treats newlines as atom separators, because PureData's `binbuf_write` wraps long statements across physical lines with no continuation marker. A newline inside a statement is exactly as significant as a space.

### Round-trip bridging

```text
Patcher  --from_builder()--> PdPatch
PdPatch  --to_builder()----> Patcher
```

`from_builder()` converts mutable builder nodes to frozen AST nodes. `to_builder()` reconstructs mutable `Patcher` state from an AST tree.

The AST holds text in PureData's escaped form, so `to_builder()` passes `escaped=True` when constructing nodes; escaping it a second time would corrupt every escaped semicolon, comma and dollar argument in the patch.

Elements the builder cannot represent -- `PdRaw` statements, and connections whose endpoints are among them -- raise `UnsupportedElementWarning` rather than vanishing. Statements PureData does not count as objects do not consume a connect index, so the remaining connections keep their meaning.

### Validation

```text
Patcher or PdPatch -> validate_patch()    (cypd/libpd)
Patcher or PdPatch -> validate_for_hvcc() (hvcc)
```

`validate_patch()` serializes the patch to a temporary file, opens it in libpd, and collects print output. A `_PrintAccumulator` buffers libpd's word-fragment callbacks into complete lines, which are then classified as errors or warnings. Because PureData logs a failing object's text on the line *before* the generic "couldn't create" error, that context is attached to the error message. libpd is a process-wide singleton, so calls are serialized behind a lock.

`validate_for_hvcc()` walks every node's `pd_class_name` -- including the GUI types, which are object boxes too -- and checks each against the `HVCC_SUPPORTED_OBJECTS` set. Subpatches are recursed into.

### Optimization

`Patcher.optimize()` runs three passes:

1. **Dedup** -- remove exact-duplicate patch cords.

2. **Pass-through collapse** -- bypass single-in/single-out nodes, opt-in via `collapsible_objects`. A run of adjacent collapsible nodes is resolved transitively into one connection rather than being dropped.

3. **Unused removal** -- remove disconnected `Obj` nodes, except protected types (GUI, `Comment`, `Subpatch`, `Abstraction`, `Array`, `Msg`, `Float`), objects with an active send or receive parameter, and structural objects that do their job without patch cords -- `inlet`, `outlet`, `table`, `array`, `declare`, `block~`, `switch~`, `namecanvas` and the rest of `_STRUCTURAL_OBJECTS`. For those, being disconnected says nothing about whether they are used.

### Layout

`_resolve_position()` tracks a cursor that advances as nodes are added. `auto_layout()` performs a topological sort of the connection graph and assigns positions by depth.

## Design decisions

### Why two APIs?

The Builder API is ergonomic for construction -- you call `add()`, `link()`, and get a patch. But it is lossy: it does not model every construct a `.pd` file may hold.

The AST API preserves the detail of existing patches on round trip. But frozen dataclasses would make the construction API painful: no in-place mutation, no position tracking.

Neither alone covers both use cases well, so both exist with bridge functions between them.

### Why frozen AST dataclasses?

Immutability makes `transform()` safe. When you walk an AST and produce a new one, there is no risk of accidentally mutating a shared node. It forces explicit reconstruction, which is the correct model for tree transformations.

### Why a mutable builder?

Patch construction is inherently stateful: position tracking, connection indexing and sequential node addition all benefit from mutation. A frozen builder would require threading state through every call, making the API awkward.

### Why a `parameters` dict?

All `Node` subclasses store state in `self.parameters`. This enables:

- uniform serialization (`__str__` reads dict values)

- uniform bridging (`from_builder`/`to_builder` read dict keys)

- easy extension (new parameters do not require schema changes)

The trade-off is no IDE autocomplete on parameter access. Constructor arguments provide the discoverability instead.

### Why resolve arity from the full object text?

PureData objects have I/O counts that depend on creation arguments. `[trigger b f s]` has one inlet and three outlets; `[trigger b]` has one of each. `[dac~ 1 2 3 4]` has four inlets where a bare `[dac~]` has two. A `name -> (in, out)` table cannot express that, so argument-dependent classes are resolved by rule instead, and `lookup_object_io()` hides the distinction.

The counts were measured against PureData 0.55 by generating probe patches and reading back which connections it rejected, rather than transcribed from memory.

### Why lazy `_ensure_libpd()`?

libpd's `release()` function is fragile and can crash the process. The init-once-never-release pattern in `_ensure_libpd()` avoids this. The function is called lazily on first validation, not at import time, so the optional dependency does not affect users who do not need it.

### Why `escape()`?

The PureData format reserves certain characters: semicolons terminate statements, commas separate messages, and dollar signs denote patch-local variables. The format escapes them as `\;`, `\,` and `\$`. Node text passes through `escape()` on the way in, unless the caller passes `escaped=True` to say the text is already in that form.

`unescape()` is a *display* transform, not the inverse: it turns an escaped semicolon into a newline, because that is where PureData breaks the line on screen. Use it to render text for a human, not to recover source text.

## Extension points

### Adding a new node type

1. Subclass `Node` in `api.py`.

2. Implement `__init__` (populate `self.parameters`), `__str__` (PureData format output), `__repr__`, and the `dimensions` property.

3. Override `pd_class_name` if the node serializes as an object box.

4. Set `num_inlets` and `num_outlets`.

5. Add an `add_*()` convenience method on `Patcher` that routes through `self._register()`.

6. Add to `_PROTECTED_TYPES` if the node should survive `optimize()`.

### Adding an AST node type

1. Add a frozen dataclass to `ast.py` and include it in the `PdElement` union.

2. Give it a `__str__` that emits the statement, including its trailing semicolon.

3. Update the `_parse_*` functions and the dispatch table in `parse()` to recognise the statement.

4. Update `from_builder()` and `to_builder()` for bridge support, deciding whether the element occupies a `#X connect` index.

### Custom layout

Subclass `LayoutManager` and override `compute_position()` (where a node goes) and `register_node()` (how that updates the cursor). Pass the custom manager to `Patcher(layout=...)`. `GridLayoutManager` is a worked example.

### New integration module

1. Add a new module under `integrations/`.

2. Re-export public symbols from `integrations/__init__.py`.

3. Use the optional dependency pattern:

    ```python
    try:
        import some_library
    except ImportError:
        raise ImportError(
            "some_library is required: pip install py2pd[extras]"
        ) from None
    ```

4. Add the dependency to `pyproject.toml` under `[project.optional-dependencies]`.

### Extending the object registry

Add fixed arities to `PD_OBJECT_REGISTRY` in `api.py` as `"name": (num_inlets, num_outlets)`, or a callable to `PD_OBJECT_IO_RULES` for a class whose arity depends on its arguments. Use `None` for a count that cannot be determined; validation is then skipped for that end. Both tables are consulted through `lookup_object_io()`, which `link()` and `validate_connections()` use.
