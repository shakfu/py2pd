# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3]

### Changed

- **BREAKING**: `Abstraction` now subclasses `Obj` instead of `Node`. Constructor takes a single `text` string (e.g., `Abstraction(0, 0, "my-synth 440 0.5")`) instead of `name, *args`. The `parameters["name"]` key is removed; use the `.name` property instead.
- **BREAKING**: `add_abstraction()` takes a single `text` string (e.g., `add_abstraction("my-synth 440")`) instead of `name, *args`. All other parameters are keyword-only.
- `add()` now accepts an optional `source_path` keyword argument. When provided, creates an `Abstraction` (with inferred I/O) instead of a plain `Obj`.
- `Abstraction` inherits `__str__`, `dimensions`, `__getitem__` from `Obj`. New read-only properties: `.name` (first token of text), `.source_path`.
- `from_builder()` simplified: removed separate `Abstraction` branch since `isinstance(node, Obj)` now catches both.

## [0.1.2]

### Added

- **Patch optimization** (`Patcher.optimize()`):
  - `optimize()` method removes unused elements and simplifies connections in three passes: (1) deduplicate exact-duplicate patch cords, (2) collapse pass-through nodes (opt-in via `collapsible_objects`), (3) remove disconnected `Obj` nodes that are not protected types and have no active send/receive.
  - Protected types (GUI, Comment, Subpatch, Abstraction, Array, Msg, Float) are never removed.
  - `recursive=True` optimizes inner subpatches first.
  - Returns stats dict: `nodes_removed`, `connections_removed`, `duplicates_removed`, `pass_throughs_collapsed`, `subpatches_optimized`.
  - Uses index-remapping rebuild approach to maintain connection integrity after node removal.
  - Module-level helpers: `_PROTECTED_TYPES`, `_SEND_RECEIVE_INACTIVE`, `_has_active_send_receive()`.
- Tests for optimize (36 tests: helpers, unused removal, protected type preservation, send/receive preservation, index remapping, serialization, duplicate removal, pass-through collapse, idempotency, combined operations, recursive subpatch, edge cases)
- **`py2pd.integrations` subpackage**: Moved `validate.py` and `hvcc.py` into `py2pd/integrations/` as `cypd.py` and `hvcc.py` respectively. Integration symbols are no longer re-exported from `py2pd.__init__`; import from `py2pd.integrations.cypd` or `py2pd.integrations.hvcc` (or from `py2pd.integrations` which re-exports both).
- **hvcc integration** (`integrations/hvcc.py`, was `hvcc.py`):
  - `HeavyPatcher` -- `Patcher` subclass that enforces hvcc-supported objects at `add()` time. Provides `add_param()`, `add_param_output()`, `add_event()`, `add_table()` for hvcc annotations (`@hv_param`, `@hv_event`, `@hv_table`).
  - `validate_for_hvcc()` -- standalone validation of any `Patcher` or `PdPatch` against the hvcc object subset (~163 objects). Recurses into subpatches. Optional generator-specific MIDI validation.
  - `compile_hvcc()` -- serialize to tempfile and shell out to the `hvcc` CLI. Supports all generators (C, DPF, Daisy, JS, OWL, pdext, Unity, Wwise).
  - `HVCC_SUPPORTED_OBJECTS` -- complete registry of ~163 hvcc-supported Pd objects.
  - `HvccGenerator` enum, `HvccValidationResult`/`HvccCompileResult` dataclasses, `HvccError`/`HvccUnsupportedError`/`HvccCompileError` exceptions.
  - `hvcc` is an optional dependency (`pip install py2pd[hvcc]`); authoring and validation work without it.
- Tests for hvcc module (registry, validation, HeavyPatcher, annotations, compile unit tests; integration tests skip if hvcc not installed)
- **Patch validation via libpd** (`integrations/cypd.py`, was `validate.py`):
  - `validate_patch()` -- loads a patch in libpd (via optional `cypd` dependency) and captures print output to detect missing objects, unresolved externals, and other errors. Accepts both `Patcher` and `PdPatch` inputs. Configurable search paths, declare-path extraction, and receiver existence checking.
  - `ValidationResult` dataclass -- `ok`, `errors`, `warnings`, `log` fields.
  - `cypd` is an optional dependency (`pip install py2pd[validate]`); py2pd works fine without it.
- Tests for validation module (unit tests run without cypd; integration tests skip if cypd is not installed)
- **`PdDeclare` AST node**: Parse and serialize `#X declare -path ... -lib ... -stdpath -stdlib` statements. Skipped silently in `to_builder()` (no builder equivalent). Does not affect object indexing for connections.
- **Externals discovery** (`discover.py` module):
  - `discover_externals()` -- scan filesystem paths for `.pd` abstractions (with inferred I/O counts) and compiled binary externals (platform-aware: `.pd_darwin`, `.pd_linux`, `.dll`, etc.). First-found-wins semantics.
  - `default_search_paths()` -- returns platform-appropriate PureData search paths (macOS, Linux, Windows) that exist on disk.
  - `extract_declare_paths()` -- recursively walks a parsed patch collecting all `-path` values from `PdDeclare` nodes.
- Tests for `PdDeclare` (serialization, parsing, roundtrip, bridge, multiple paths)
- Tests for discovery module (default paths, abstraction/binary/mixed discovery, first-found-wins, edge cases, declare path extraction)
- **Graph-on-Parent (GOP)**: `add_subpatch()` and `Subpatch` now support `graph_on_parent`, `hide_name`, `gop_width`, `gop_height` parameters. Emits `#X coords` line in output. Round-trips through `from_builder()`/`to_builder()`.
- **Abstractions**: `Abstraction` class and `add_abstraction()` method for referencing external `.pd` files. Supports manual or auto-inferred inlet/outlet counts via `source_path`. Serializes as standard `#X obj`.
- `_infer_abstraction_io()` helper to count inlets/outlets from a `.pd` file
- `from_builder()` now preserves subpatch `canvas_width`/`canvas_height` instead of hardcoding 300x180
- `to_builder()` now preserves subpatch canvas dimensions from AST
- Tests for GOP (builder output, dimensions, hide_name, round-trip)
- Tests for Abstraction (str, args, dimensions, linking, IO inference, round-trip)
- 7 IEM GUI AST types: `PdNbx`, `PdVsl`, `PdHsl`, `PdVradio`, `PdHradio`, `PdCnv`, `PdVu` -- full round-trip parsing and serialization
- `PD_OBJECT_REGISTRY` mapping ~80 common Pd objects to inlet/outlet counts, auto-filled by `Patcher.add()`
- `link()` now accepts `Node.Outlet` objects (e.g. `p.link(osc[1], dac)`) in addition to plain `Node`
- `add_subpatch()` auto-infers `num_inlets`/`num_outlets` from inner `inlet`/`outlet` objects
- `Comment` node type and `PdText` round-trip support through `from_builder()`/`to_builder()`
- `__all__` in `__init__.py` for explicit public API
- `pytest-cov` for coverage reporting (94% coverage)
- `-> None` return type on all `__init__` methods in `api.py`
- Type hint on `rename()` in `ast.py`
- Tests for `save()` method (no filename, argument, constructor, override)
- Tests for parser internals (`_preprocess`, `_split_statements`)
- Tests for parser robustness (truncated lines, missing fields, binary data)
- Tests for `PdCoords` parsing and serialization
- Integration tests for all example functions (`test_examples.py`)
- Tests for all 7 new IEM GUI types (parse, to_builder, from_builder, roundtrip)
- Tests for `PD_OBJECT_REGISTRY`, `link()` with `Outlet`, subpatch auto-inference

### Changed

- `from_builder()` now uses dedicated handlers for all 10 GUI types instead of falling through to `PdObj`
- `to_builder()` now uses proper constructors for all GUI types instead of string-stripping hacks
- `_parse_canvas()` subpatch detection uses `len(tokens) >= 8` instead of `not tokens[6].isdigit()`, fixing numeric subpatch names (e.g. `pd 42`)
- Test count increased from 335 to 422

## [0.1.1]

### Fixed

- `unescape()` dollar sign regex was not matching `\$` mid-string (missing `\` before `$` in pattern)
- `auto_layout()` infinite loop on cyclic graphs -- now uses iterative DFS to detect back-edges, builds a DAG, and runs BFS on the DAG
- `from_builder()` silently dropped GUI types other than Bang/Toggle/Symbol -- now handles all 10 GUI types (NumberBox, VSlider, HSlider, VRadio, HRadio, Canvas, VU via PdObj)
- `to_builder()` constructed PdBng/PdTgl using a string-stripping hack -- now properly constructs Bang/Toggle with all parameters preserved

### Changed

- Renamed `ConnectionError` to `PdConnectionError` to avoid shadowing the Python builtin
- Renamed `size` property to `dimensions` on all Node subclasses to distinguish from the `size` constructor parameter (single int)
- Switched build backend from hatchling to uv_build
- Code formatted with ruff (line-length 100)

### Added

- GitHub Actions CI workflow (ubuntu, macos, windows; Python 3.13; lint, typecheck, test, build)
- Project metadata in pyproject.toml (license, authors, classifiers, keywords, URLs)
- Tool configuration for pytest, mypy, and ruff in pyproject.toml
- Tests for auto_layout with cycles (single cycle, self-loop, multiple independent cycles)
- Tests for unescape dollar sign roundtrip
- Tests for from_builder/to_builder with all GUI types
- Tests for Bang and Toggle roundtrip through from_builder/to_builder

## [0.1.0]

Initial release. A complete rewrite of [puredata-compiler](https://github.com/dylanburati/puredata-compiler).

### Added

- **Builder API** (`Patcher` class)
  - `add()` - add objects (e.g., `osc~`, `dac~`, `+`)
  - `add_msg()` - add message boxes
  - `add_float()` - add float atoms
  - `add_subpatch()` - add nested subpatches
  - `add_array()` - add arrays
  - `link()` - connect nodes with inlet/outlet specification
  - `save()` / `save('filename.pd')` - save patches

- **GUI elements**
  - `add_bang()`, `add_toggle()`, `add_numberbox()`
  - `add_hslider()`, `add_vslider()`
  - `add_hradio()`, `add_vradio()`
  - `add_symbol()`, `add_canvas()`, `add_vu()`

- **Layout management**
  - `LayoutManager` - default top-to-bottom flow
  - `GridLayoutManager` - organized grid placement
  - `auto_layout()` - automatic signal-flow-based arrangement

- **Validation and export**
  - `validate_connections()` - check connection validity with cycle detection
  - `to_svg()` / `save_svg()` - SVG visualization export

- **AST API** (round-trip parsing)
  - `parse()` / `parse_file()` - parse .pd files into AST
  - `serialize()` / `serialize_to_file()` - write AST back to .pd format
  - `from_builder()` / `to_builder()` - convert between Builder and AST APIs
  - `transform()`, `find_objects()`, `rename_sends_receives()` - AST utilities

- **Exception types**
  - `PdConnectionError`, `NodeNotFoundError`, `InvalidConnectionError`, `CycleWarning`

[Unreleased]: https://github.com/shakfu/py2pd/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/shakfu/py2pd/compare/v0.1.2...v0.2.0
[0.1.1]: https://github.com/shakfu/py2pd/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/shakfu/py2pd/releases/tag/v0.1.0
