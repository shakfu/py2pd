# py2pd

Roundtrip parsing and generation of [PureData](https://puredata.info) patches from
Python.

py2pd is a fork and extensive rewrite of Dylan Burati's
[puredata-compiler](https://github.com/dylanburati/puredata-compiler), using some
of the ideas from [py2max](https://github.com/shakfu/py2max).

## Install

```bash
pip install py2pd
```

The optional integrations pull in [cypd](https://github.com/shakfu/cypd) for libpd
validation and [hvcc](https://github.com/Wasted-Audio/hvcc) for compiling patches
to C/C++:

```bash
pip install py2pd[extras]
```

## Two APIs

py2pd offers a mutable **Builder** for writing patches and a frozen **AST** for
reading them, with bridge functions in both directions. [Architecture](architecture.md)
explains why both exist and when to reach for each.

### Builder

```python
from py2pd import Patcher

p = Patcher('synth.pd')

osc = p.add('osc~ 440')
gain = p.add('*~ 0.3')
dac = p.add('dac~')

p.link(osc, gain)
p.link(gain, dac)
p.link(gain, dac, inlet=1)  # stereo

p.save()
```

### AST

```python
from py2pd import parse_file, serialize

patch = parse_file('input.pd')

# inspect or transform the frozen tree...

with open('output.pd', 'w', encoding='utf-8') as f:
    f.write(serialize(patch))
```

### Bridging

```python
from py2pd import parse_file, to_builder, from_builder

patch = to_builder(parse_file('input.pd'))  # AST -> Builder, to edit
patch.add('osc~ 880')
patch.save('output.pd')

tree = from_builder(patch)                  # Builder -> AST, to analyse
```

## Choosing an API

| Use case | API |
|---|---|
| Creating patches from scratch | Builder |
| Modifying existing patches | Builder, via `to_builder()` |
| Round-trip of complex patches | AST |
| Building analysis or refactoring tools | AST |
| Batch search/replace across `.pd` files | AST |

The Builder models the common subset of the file format. Statements it has no node
for -- data structure templates, scalars, array data, box widths -- survive in the
AST but cannot be carried into a `Patcher`; `to_builder()` warns with
`UnsupportedElementWarning` rather than dropping them silently. Use the AST
directly when you need to preserve them.

## Further reading

- [Architecture](architecture.md) -- how the pieces fit together, and the reasoning
  behind the design.
- [API Reference](api.md) -- every public class and function.
- The [README](https://github.com/shakfu/py2pd#readme) covers the Builder's GUI
  constructors, layout managers, optimisation and the integrations in more detail.
