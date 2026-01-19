# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-01-19

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
  - `ConnectionError`, `NodeNotFoundError`, `InvalidConnectionError`, `CycleWarning`

[Unreleased]: https://github.com/username/py2pd/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/username/py2pd/releases/tag/v0.1.0
