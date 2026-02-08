# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
- Test count increased from 335 to 372

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

[Unreleased]: https://github.com/shakfu/py2pd/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/shakfu/py2pd/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/shakfu/py2pd/releases/tag/v0.1.0
