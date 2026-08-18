# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`pip install py2pd[extras]` failed outright on Windows and Linux ARM.** `cypd` publishes binary wheels only for macOS arm64 and Linux x86_64 and has no source distribution, so resolution errored rather than skipping it. The dependency now carries an environment marker matching the platforms it ships for; elsewhere the extra installs `hvcc` alone, and the libpd integration raises its usual ImportError if used. This also unbroke the Windows CI job, which had started installing the extras.
- **CI actions were pinned to versions running the deprecated Node 20 runtime**, which the runners were already force-migrating to Node 24 and warning about on every run. Bumped to `actions/checkout@v7`, `actions/upload-artifact@v7` and `actions/download-artifact@v8`. `astral-sh/setup-uv` moved to an exact `@v10.0.1`: it stopped publishing floating major tags at v8 as a supply-chain measure, so `@v10` does not resolve.

## [0.2.0]

Corrects the parser against PureData's actual file format. Every finding in `REVIEW.md` is addressed. Against the 371 patches shipped with PureData 0.55, parse errors went from 126 to 0 and byte-identical round-trips from 24 to 345; the remainder differ only where older PureData versions wrapped statements across physical lines, which 0.55 no longer does.

### Changed

### Changed -- incompatible

Several of these change types or field layouts that were simply wrong about the format. Code that constructed the affected AST nodes positionally, or relied on the old object registry, needs updating.

- `PdCoords` no longer has a `hide_name` field. PureData encodes "hide the object name" in the graph-on-parent flag itself (`2` rather than `1`), and the two values after that flag are the viewport margins. `hide_name` is now a read-only property, and `x_margin` / `y_margin` moved up one position and default to `None` (the seven-value form of the statement).

- `PdRestore` gained a `kind` field (`"pd"`, `"graph"` or `"pop"`) and `name` now defaults to `""`.

- `PdPatch` gained a `preamble` field for statements that precede the canvas line.

- Unrecognised statements parse to the new `PdRaw` node instead of being rewritten as `#X obj` boxes.

- `PD_OBJECT_REGISTRY` no longer contains `dac~`, `adc~`, `trigger`, `t`, `pack`, `unpack`, `route`, `select`, `sel` or `list`; their arity depends on creation arguments and they moved to `PD_OBJECT_IO_RULES`. Use `lookup_object_io(text)` rather than indexing either table directly. Fourteen further entries had incorrect counts and were corrected.

- `add_abstraction()` without explicit counts now reports unknown arity (`None`) rather than zero, so connections to it are no longer rejected.

- `Comment` escapes its content by default; pass `escaped=True` for text that is already in PureData's form.

- IEM colour fields and parameters are typed `int | str`, since PureData >= 0.47
  writes colours as hex strings.

- `link()` rejects negative inlet and outlet indices, which PureData refuses at load time.

- The project ships the MIT license text with upstream attribution. The repository previously carried GPL-3.0 text while all published releases declared MIT; see the licensing note under Fixed.

- **Documentation moved from Sphinx to MkDocs** (`mkdocs-material` + `mkdocstrings`). `docs/*.rst`, `docs/conf.py` and `docs/Makefile` are replaced by `docs/*.md` and `mkdocs.yml`; `make docs` builds to `site/` and `make docs-serve` runs the live-reload server. The API reference is generated from the same NumPy-style docstrings as before. `mkdocs.yml` sets `strict: true`, so a broken link or an unresolvable API reference fails the build, and CI now builds the docs on every push. `make docs-deploy` publishes the site to the `gh-pages` branch, served at <https://shakfu.github.io/py2pd/>.

- The architecture document was corrected while converting. Several statements had been left untrue by earlier changes: it described `validate_for_hvcc()` as skipping GUI nodes, `PD_OBJECT_REGISTRY` as the sole source of arity, an `unescape()` applied on read, a `LayoutManager.next_position()` and a `_serialize_element()` that do not exist, protected optimizer types that were never protected, and a `PdArrayData` AST node that was never added.

### Fixed

- **Parser: newlines are atom separators.** PureData wraps long statements across physical lines with no continuation marker, but `_tokenize()` split only on spaces and tabs, folding the newline into the adjacent token. Object arguments came back corrupted (`('...', 'ten\neleven', 'twelve')`) and wrapped GUI objects failed their argument-count check, silently degrading to plain `PdObj`. Serialization happened to stay byte-stable, which is why no test caught it.

- **Parser: `#X restore <x> <y> graph;`.** `_parse_restore()` required six tokens and hardcoded `pd` in the output, so any patch containing an array or graph canvas raised `ParseError` -- 126 of the 371 patches shipped with PureData 0.55. `PdRestore` now records the form in `kind` and round-trips both.

- **Parser: IEM colours.** PureData >= 0.47 writes colours as `#rrggbb`, which `_parse_int()` swallowed, substituting the legacy defaults. Every GUI object in every modern patch lost its colours on round trip. Colours are now typed
  `IemColor` (`int | str`) and preserved in whichever form they were read.

- **Parser: `tgl` argument count.** The threshold was 15 but a toggle line carries 14 values, so no real toggle ever parsed as `PdTgl` (239 in the PureData 0.55 corpus).

- **Parser: unmodelled statements are preserved.** `#N struct`, `#X scalar`, `#A` array data, `#X f` box widths and `#X listbox` were dropped, or -- worse -- rewritten as object boxes by the unknown-command fallback, producing a file that loads but is wrong. They now parse to the new `PdRaw` node and serialize verbatim. `PdPatch.preamble` holds statements that precede the canvas line, which is where PureData writes struct templates.

- **Parser: `#X coords` field layout.** The AST had a `hide_name` field that PureData does not write, which shifted both margins by one position. Hiding the object name is encoded in the graph-on-parent flag itself (`2` rather than `1`). `PdCoords.hide_name` is now a derived property, the seven- and nine-value forms both round-trip, and `Subpatch`'s `hide_name=True` finally has an effect -- it previously wrote the flag into the x-margin slot.

- **Parser: `#X declare -stdpath <value>`.** `-stdpath` and `-stdlib` take a value; treating them as bare flags dropped it. The statement is now also kept verbatim so it serializes back unchanged.

- **Parser: atom box font size.** PureData >= 0.52 appends a per-box font size to `#X floatatom` / `#X symbolatom`; it was dropped. Integral limits are also no longer rewritten as floats (`0` stayed `0`, not `0.0`).

- **`to_builder()` no longer double-escapes.** It passed already-escaped text through `escape()` a second time, turning `\$1` into a literal dollar sign and inserting stray backslash atoms. PureData loaded the result without complaint and interpreted it wrongly. `Obj`, `Msg`, `Abstraction`, `Patcher.add()` and `Patcher.add_msg()` accept `escaped=True` for text that is already in PureData's form.

- **`to_builder()` no longer rejects valid patches.** Connection validation now warns rather than raising while reading, since the object registry cannot know the arity of externals, abstractions, or anything absent from it. 25 of the 245 then-parseable PureData 0.55 patches raised `PdConnectionError`.

- **`to_builder()` reports what it cannot represent.** Statements and connections the builder has no node for now raise `UnsupportedElementWarning` instead of vanishing. Statements PureData does not count as objects no longer consume a connect index, which previously shifted every following connection.

- **`optimize()` no longer deletes the signal path.** Pass-through collapse built its bypass connections from stale indices, so a chain of adjacent collapsible nodes (`a -> p1 -> p2 -> b`) dropped both replacement connections and left `a` and `b` disconnected. Chains are now resolved transitively to a single connection.

- **`add_subpatch()`** no longer raises `IndexError` when the inner patch contains an object with empty text.

- **Licensing.** The repository shipped the GPL-3.0 text while `pyproject.toml` and all three published releases declared MIT, and the built wheel contained no license file at all. The GPL text was added by GitHub at repository creation, not inherited: upstream puredata-compiler carries no LICENSE file and declares `License :: OSI Approved :: MIT License` in its `setup.py`. `LICENSE` is now the MIT text, carries a copyright notice for Dylan Burati alongside one for this project -- required by MIT, since parts of `api.py` (`escape`, `get_display_lines`, `get_next_position` and the node class hierarchy) originate upstream -- and is included in the distribution via `license-files`.

- **hvcc validation only ever inspected `Obj` nodes.** The GUI classes are object boxes too, and the AST GUI dataclasses are not `PdObj` subclasses, so both walkers skipped every one of them: `HeavyPatcher().add_vu()` was accepted and `validate_for_hvcc()` reported `ok=True` for a patch containing it. `HeavyPatcher` now enforces on every `add_*` method rather than only `add()`, and abstractions are no longer reported as unsupported objects -- an abstraction names a user file, not a built-in class.

- **`compile_hvcc()` could hang or crash.** It shelled out to the `hvcc` console script after only checking that the package was importable, which is not the same as its entry point being on PATH, and `FileNotFoundError` was unhandled. It now resolves the script beside the running interpreter, falls back to PATH, returns a failed result rather than raising, and takes a `timeout` (default 600s).

- **`validate_patch()` said an object failed but not which one.** PureData logs the object text on the line before a generic `couldn't create`; that context is now attached to the error.

- **`link()` accepted negative indices**, producing `#X connect 0 0 1 -1;`, which PureData rejects on load with "connection failed".

- **`validate_connections()` could never return a non-empty list** -- it raised instead. `raise_on_error=False` now returns the errors.

- **`detect_cycles()` recursed**, raising `RecursionError` on a patch a few thousand nodes deep. `validate_connections()` calls it by default. It is now iterative.

- **`link()` was O(n) per call**, making patch construction quadratic. Node positions are now resolved through a self-healing `id()` cache: 5000 nodes went from 0.23s to 0.03s, and 20000 nodes now complete in 0.1s.

- **`add_abstraction()` without inlet/outlet counts defaulted to zero**, so the first `link()` to it always raised. Unknown counts are now `None`, which skips validation.

- **Comment text was never escaped.** `Comment(0, 0, "a; b")` emitted `#X text 0 0 a; b;`, which PureData reads as two statements. There is also a `Patcher.add_comment()` now -- comments were previously reachable only through `to_builder()`.

- **`optimize()` removed objects that work without patch cords.** A disconnected `[table]`, `[declare]`, `[block~]`, `[inlet]` or `[outlet]` is not unused; removing one changes what the patch does.

- **`#X pop` was ignored**, leaving the canvas on the parse stack so every following element was read into the wrong subpatch. It now closes the canvas and serializes back unchanged.

- **File writes used the locale encoding.** `save()` and `save_svg()` now specify UTF-8 explicitly, and `save()` terminates the file with a newline as PureData does.

- **`to_svg()` had unreachable branches** -- the message and array labels could never be produced, because the generic `"text" in params` check came first.

- **`unescape()`'s docstring claimed it reverses `escape()`.** It does not, and is not meant to: it renders text the way PureData displays it.

- Corrected `pip install py2pd[hvcc]` / `py2pd[validate]` in older CHANGELOG entries; the extra has always been named `extras`.

### Changed

- **Object arity is resolved from the full object text, not the class name.** `PD_OBJECT_REGISTRY` could not express `[dac~ 1 2 3 4]`, `[trigger b f s]`, `[route a b c]` or `[list split]`, whose inlet and outlet counts depend on their creation arguments. Those classes moved to `PD_OBJECT_IO_RULES`, and the new `lookup_object_io(text)` resolves either. Fourteen entries in the fixed table were also wrong; all counts were re-measured against PureData 0.55 by generating probe patches and reading back which connections it rejected.

- `Patcher(validate_links=False)` downgrades `link()`'s index check from `PdConnectionError` to the new `PdConnectionWarning`.

- `add_subpatch(is_graph=True)` writes `#X restore <x> <y> graph;`, and `gop_rect` / `gop_margins` control the values on the `#X coords` line.

- IEM colour parameters across the builder GUI types accept hex strings as well as packed integers.

### Added

- `tests/examples/pd_authored.pd` -- a fixture written by PureData 0.55 itself, covering wrapped statements, hex colours, a graph canvas, a graph-on-parent subpatch with a hidden name, a scalar and a struct template.

- `tests/test_roundtrip.py` -- byte-level round-trip tests against that fixture, with one test per defect above.

- `tests/test_corpus.py` -- runs the parser over a real PureData installation's patches when one is present, skipped otherwise. Set `PD_DOC_DIR` to choose a corpus.

- `tests/test_pd_loads.py` -- generates patches, opens them in PureData and requires a silent console. Unit tests can only confirm py2pd wrote the bytes it intended; this confirms PureData accepts them. Skipped when no `pd` binary is found; set `PD_BIN` to choose one.

- `Patcher.add_comment()`, and `escaped=` on `Obj`, `Msg`, `Comment`, `Patcher.add()` and `Patcher.add_msg()`.

- `Patcher(canvas_x=, canvas_y=, canvas_width=, canvas_height=, font_size=)` -- the main canvas line was previously hardcoded to `#N canvas 0 50 1000 600 10`. `to_builder()` now carries the source patch's geometry across.

- `Node.pd_class_name` on every builder node and AST element -- the PureData class name a validator should check it against, or None for elements that are not object boxes.

- `validate_patch(work_dir=...)` for validating a patch alongside its sibling abstractions.

- `py.typed` marker, so the annotations actually reach downstream users. The `Typing :: Typed` classifier had been declared without it.

- A release workflow, triggered by publishing a GitHub Release, using PyPI Trusted Publishing.

- CI now installs the optional extras (`--all-extras`), type-checks `tests/` as well as `src/`, and enforces a 90% coverage floor. Without the extras the `cypd` and `hvcc` integration tests silently skipped, which is how four genuine failures in that code went unnoticed.


## [0.1.3]

### Fixed

- `_infer_abstraction_io()` now uses AST parsing instead of string counting -- previous implementation (`content.count(" inlet;")`) could match inside comments, message boxes, and other non-object text. Now parses the file with `parse()` and counts only top-level `PdObj` nodes with `class_name in {"inlet", "inlet~", "outlet", "outlet~"}`. Subpatch inlets are correctly excluded.

- `Msg.num_inlets` changed from 1 to 2 -- PureData message boxes have two inlets (hot inlet for triggering, cold inlet for setting contents). The previous value silently allowed invalid connection validation results.

### Changed

- `Node.__getitem__` now validates the outlet index against `num_outlets` when known. Raises `ValueError` if the index is out of range. Objects with `num_outlets=None` (variable I/O) skip validation.

- `Patcher.link()` now validates outlet and inlet indices against `num_outlets`/`num_inlets` before creating the connection. Raises `PdConnectionError` for out-of-range indices. Skipped when counts are `None`.

- `optimize()` Pass 2 (pass-through collapse) replaced O(n*k) list scanning with O(n) dict-based index lookups. Builds `conn_by_source`/`conn_by_sink` dicts up front, collects removals via `id()` set, and applies in a single filter pass.

- GUI `add_*` methods now forward all constructor parameters to the underlying class. Previously, `add_bang()` exposed 5 of 13 params (missing `hold`, `interrupt`, `label_x`, `label_y`, `font`, `font_size`, `bg_color`, `fg_color`, `label_color`). The same gap existed across all 10 GUI types. All constructor params now have matching keyword arguments with identical defaults.

- Deduplicated `_walk_builder_nodes` / `_walk_builder_nodes_into` in `hvcc.py` -- the top-level function now delegates to the recursive helper instead of duplicating its body.

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

  - `hvcc` is an optional dependency (`pip install py2pd[extras]`); authoring and validation work without it.

- Tests for hvcc module (registry, validation, HeavyPatcher, annotations, compile unit tests; integration tests skip if hvcc not installed)

- **Patch validation via libpd** (`integrations/cypd.py`, was `validate.py`):

  - `validate_patch()` -- loads a patch in libpd (via optional `cypd` dependency) and captures print output to detect missing objects, unresolved externals, and other errors. Accepts both `Patcher` and `PdPatch` inputs. Configurable search paths, declare-path extraction, and receiver existence checking.

  - `ValidationResult` dataclass -- `ok`, `errors`, `warnings`, `log` fields.

  - `cypd` is an optional dependency (`pip install py2pd[extras]`); py2pd works fine without it.

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

[Unreleased]: https://github.com/shakfu/py2pd/compare/v0.2.0...HEAD [0.2.0]: https://github.com/shakfu/py2pd/compare/v0.1.3...v0.2.0 [0.1.3]: https://github.com/shakfu/py2pd/compare/v0.1.2...v0.1.3 [0.1.2]: https://github.com/shakfu/py2pd/compare/v0.1.1...v0.1.2 [0.1.1]: https://github.com/shakfu/py2pd/compare/v0.1.0...v0.1.1 [0.1.0]: https://github.com/shakfu/py2pd/releases/tag/v0.1.0
