# py2pd - Python <-> PureData

Roundtrip parsing and generation of [pure-data](https://puredata.info) patches from python.

py2pd is a fork and extensive rewrite of Dylan Burati's [puredata-compiler](https://github.com/dylanburati/puredata-compiler) using some of the ideas from [py2max](https://github.com/shakfu/py2max).

## Install

```bash
pip install py2pd
```

## Quick Start

```python
from py2pd import Patcher

# Create a simple synthesizer patch
p = Patcher('synth.pd')

osc = p.add('osc~ 440')
gain = p.add('*~ 0.3')
dac = p.add('dac~')

p.link(osc, gain)
p.link(gain, dac)
p.link(gain, dac, inlet=1)  # stereo

p.save()
```

## Builder API

The `Patcher` class provides methods to add nodes and connect them.

### Adding Nodes

```python
from py2pd import Patcher

p = Patcher('example.pd')

# Objects
osc = p.add('osc~ 440')
filter_obj = p.add('lop~ 1000')

# Messages
bang = p.add_msg('bang')
freq_msg = p.add_msg('440')

# GUI Elements
slider = p.add_hslider(min_val=20, max_val=20000, width=150)
toggle = p.add_toggle(default_value=1, send='onoff')
numbox = p.add_numberbox(min_val=0, max_val=127)
bang_btn = p.add_bang(send='trigger', label='Click')
```

### Connecting Nodes

Use `link()` to connect nodes. By default, outlet 0 connects to inlet 0:

```python
p.link(osc, gain)              # outlet 0 -> inlet 0
p.link(gain, dac)              # left channel
p.link(gain, dac, inlet=1)     # right channel (stereo)
p.link(trigger, pack, outlet=1, inlet=2)  # specific ports
```

### Subpatches

Create reusable subpatches:

```python
def make_envelope() -> Patcher:
    p = Patcher()
    inlet = p.add('inlet')
    vline = p.add('vline~')
    outlet = p.add('outlet~')
    p.link(inlet, vline)
    p.link(vline, outlet)
    return p

main = Patcher('main.pd')
osc = main.add('osc~ 440')
env = main.add_subpatch('envelope', make_envelope())
vca = main.add('*~')

main.link(osc, vca)
main.link(env, vca, inlet=1)
```

### Graph-on-Parent

Subpatches can expose their GUI elements to the parent patch using graph-on-parent mode:

```python
inner = Patcher()
slider = inner.add_hslider(min_val=0, max_val=1000, label='freq')
outlet = inner.add('outlet')
inner.link(slider, outlet)

main = Patcher('main.pd')
ctrl = main.add_subpatch(
    'controls', inner,
    graph_on_parent=True,
    hide_name=True,
    gop_width=150,
    gop_height=40,
)
```

### Abstractions

Reference external `.pd` files as objects in your patch:

```python
from py2pd import Patcher

p = Patcher('main.pd')

# With explicit inlet/outlet counts
synth = p.add_abstraction('my-synth 440 0.5',
                          num_inlets=2, num_outlets=1)

# Auto-infer I/O from the source file
synth = p.add_abstraction('my-synth 440',
                          source_path='my-synth.pd')

dac = p.add('dac~')
p.link(synth, dac)
p.link(synth, dac, inlet=1)
```

### Layout Options

**Default layout** - nodes flow top-to-bottom:
```python
p = Patcher('patch.pd')
p.add('osc~ 440')   # Row 1
p.add('*~ 0.5')     # Row 2
p.add('dac~')       # Row 3
```

**Grid layout** - organized columns:
```python
from py2pd import Patcher, GridLayoutManager

grid = GridLayoutManager(columns=4, cell_width=80, cell_height=35)
p = Patcher('grid.pd', layout=grid)
```

**Auto layout** - arrange by signal flow:
```python
p = Patcher('patch.pd')
# Add nodes in any order...
p.auto_layout(margin=50, row_spacing=50, col_spacing=100)
```

### Saving and Export

```python
p.save()                    # Save to filename from constructor
p.save('other.pd')          # Save to specific file
p.save_svg('patch.svg')     # Export visualization as SVG
svg_str = p.to_svg()        # Get SVG as string
```

### Optimization

Clean up patches by removing unused elements and simplifying connections:

```python
p = Patcher()
osc = p.add('osc~ 440')
gain = p.add('*~ 0.5')
unused = p.add('+~ 0.1')  # not connected to anything
dac = p.add('dac~')
p.link(osc, gain)
p.link(gain, dac)
p.link(gain, dac)  # accidental duplicate

result = p.optimize()
# result == {'nodes_removed': 1, 'connections_removed': 2,
#            'duplicates_removed': 1, 'pass_throughs_collapsed': 0,
#            'subpatches_optimized': 0}
```

The three passes run in order:
1. **Deduplicate connections** -- removes exact-duplicate patch cords.
2. **Pass-through collapse** -- bypasses single-in/single-out nodes (opt-in via `collapsible_objects`).
3. **Unused element removal** -- removes disconnected `Obj` nodes. GUI elements, comments, subpatches, abstractions, arrays, messages, and floats are never removed. Nodes with active send/receive parameters are preserved.

Use `recursive=True` to optimize inner subpatches as well:

```python
result = p.optimize(recursive=True)
```

### Validation

```python
p.validate_connections(check_cycles=True)  # Raises on invalid connections
```

## AST API (Round-trip Parsing)

For modifying existing patches with immutable AST nodes:

```python
from py2pd import parse_file, serialize

# Parse existing patch
ast = parse_file('input.pd')

# Modify the AST...

# Write back
with open('output.pd', 'w') as f:
    f.write(serialize(ast))
```

### Converting Between APIs

You can convert between AST and Builder representations:

```python
from py2pd import parse_file, to_builder, from_builder

# AST -> Builder: parse then edit with the more convenient API
ast = parse_file('input.pd')
patch = to_builder(ast)
patch.add('osc~ 880')
patch.save('output.pd')

# Builder -> AST: for analysis or transformation
ast = from_builder(patch)
```

### When to Use Each API

| Use Case | Recommended API |
|----------|-----------------|
| Creating patches from scratch | Builder |
| Modifying existing patches | Builder (via `to_builder()`) |
| Lossless round-trip of complex patches | AST |
| Building analysis/refactoring tools | AST |
| Batch search/replace across .pd files | AST |

For most workflows, parse to AST then convert to Builder for editing. Use the AST API directly when you need to preserve elements the Builder doesn't model (e.g., `coords`, comments) or need immutable transformations.

AST node types are available from the `py2pd.ast` module:

```python
from py2pd.ast import PdPatch, PdObj, PdMsg, Position, transform, find_objects
```

## GUI Elements

| Method | Description |
|--------|-------------|
| `add_bang()` | Bang button |
| `add_toggle()` | On/off toggle |
| `add_numberbox()` | Editable number |
| `add_float()` | Float atom |
| `add_symbol()` | Symbol/text input |
| `add_hslider()` | Horizontal slider |
| `add_vslider()` | Vertical slider |
| `add_hradio()` | Horizontal radio buttons |
| `add_vradio()` | Vertical radio buttons |
| `add_canvas()` | Background/label area |
| `add_vu()` | VU meter |

## Discovery

Scan the filesystem for installed PureData externals:

```python
from py2pd import discover_externals, default_search_paths, extract_declare_paths

# Find all externals on platform-default search paths
registry = discover_externals()
# registry == {'my-external': (2, 1), 'reverb~': (None, None), ...}

# See which paths are searched
paths = default_search_paths()

# Extract -path declarations from a parsed patch
from py2pd import parse_file
ast = parse_file('input.pd')
declared = extract_declare_paths(ast)
```

`discover_externals()` returns a dict mapping external names to `(num_inlets, num_outlets)` tuples. For `.pd` abstractions the counts are inferred from the file; binary externals get `(None, None)`.

## Integrations

### Validation (cypd/libpd)

Validate patches by loading them into libpd and checking for errors:

```bash
pip install py2pd[extras]
```

```python
from py2pd.integrations.cypd import validate_patch

p = Patcher('synth.pd')
osc = p.add('osc~ 440')
dac = p.add('dac~')
p.link(osc, dac)

result = validate_patch(p)
if not result.ok:
    print("Errors:", result.errors)
    print("Warnings:", result.warnings)
```

### hvcc (Heavy Compiler Collection)

Build patches compatible with the [hvcc](https://github.com/Wasted-Audio/hvcc) compiler for generating C/C++ code:

```bash
pip install py2pd[extras]
```

**HeavyPatcher** validates objects at add-time:

```python
from py2pd.integrations.hvcc import HeavyPatcher, HvccGenerator

p = HeavyPatcher(generators=[HvccGenerator.DPF])

# add_param creates an [r __hv_param_name ...] receive object
freq = p.add_param('freq', min_val=20.0, max_val=20000.0, default=440.0)
osc = p.add('osc~')
dac = p.add('dac~')
p.link(freq, osc)
p.link(osc, dac)
p.link(osc, dac, inlet=1)
```

**Validate existing patches**:

```python
from py2pd.integrations.hvcc import validate_for_hvcc

result = validate_for_hvcc(p)
if not result.ok:
    print("Unsupported objects:", result.unsupported)
```

**Compile to C/C++** (requires `hvcc` installed):

```python
from py2pd.integrations.hvcc import compile_hvcc

result = compile_hvcc(p, name='MySynth', out_dir='build/')
if not result.ok:
    print(result.stderr)
```

## Error Handling

```python
from py2pd import (
    PdConnectionError,      # Invalid connection arguments
    NodeNotFoundError,      # Node not in patch
    InvalidConnectionError, # Bad inlet/outlet index
    CycleWarning,           # Feedback loop detected
)
```
