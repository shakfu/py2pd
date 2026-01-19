# TODO

## AST Node Types

Missing IEM GUI objects in AST parser:

- [ ] `PdVsl` - Vertical slider
- [ ] `PdHsl` - Horizontal slider
- [ ] `PdVradio` - Vertical radio buttons
- [ ] `PdHradio` - Horizontal radio buttons
- [ ] `PdCnv` - IEM canvas (different from graph-on-parent canvas)
- [ ] `PdNbx` - IEM number box
- [ ] `PdVu` - VU meter

## Concrete Object Support

Currently all Pd objects are created via generic `add('osc~ 440')`. Consider adding typed constructors with parameter validation for common objects.

### Audio Objects (~)

**Oscillators:**
- [ ] `osc~` - Cosine oscillator
- [ ] `phasor~` - Sawtooth oscillator (0-1 ramp)
- [ ] `noise~` - White noise
- [ ] `tabosc4~` - 4-point interpolating table oscillator

**Math:**
- [ ] `+~`, `-~`, `*~`, `/~` - Arithmetic
- [ ] `cos~`, `sin~` - Trigonometry
- [ ] `sqrt~`, `abs~`, `wrap~`, `clip~` - Utilities
- [ ] `pow~`, `log~`, `exp~` - Exponential

**Filters:**
- [ ] `lop~` - Low-pass filter
- [ ] `hip~` - High-pass filter
- [ ] `bp~` - Band-pass filter
- [ ] `vcf~` - Voltage-controlled filter
- [ ] `bob~` - Moog-style filter
- [ ] `slop~` - Slew-limited low-pass

**Delays:**
- [ ] `delwrite~` - Delay line write
- [ ] `delread~` - Delay line read
- [ ] `delread4~` - 4-point interpolating delay read
- [ ] `vd~` - Variable delay read

**I/O:**
- [ ] `adc~` - Audio input
- [ ] `dac~` - Audio output
- [ ] `readsf~` - Read sound file
- [ ] `writesf~` - Write sound file
- [ ] `soundfiler` - Load/save audio files

**Envelope/Control:**
- [ ] `line~` - Linear ramp generator
- [ ] `vline~` - Sample-accurate line
- [ ] `env~` - Envelope follower
- [ ] `threshold~` - Signal threshold detector
- [ ] `samphold~` - Sample and hold

**FFT:**
- [ ] `fft~`, `ifft~` - Complex FFT
- [ ] `rfft~`, `rifft~` - Real FFT
- [ ] `block~` - Set block size
- [ ] `switch~` - DSP on/off

**Tables:**
- [ ] `tabread~` - Read from table (non-interpolating)
- [ ] `tabread4~` - Read from table (4-point interpolating)
- [ ] `tabwrite~` - Write to table
- [ ] `tabsend~`, `tabreceive~` - Table send/receive

### Control Objects

**Math:**
- [ ] `+`, `-`, `*`, `/` - Arithmetic
- [ ] `mod`, `div` - Integer math
- [ ] `pow`, `log`, `exp` - Exponential
- [ ] `abs`, `sqrt` - Utilities
- [ ] `min`, `max` - Comparison
- [ ] `random`, `expr` - Random, expressions

**Logic:**
- [ ] `==`, `!=`, `>`, `<`, `>=`, `<=` - Comparison
- [ ] `&&`, `||` - Boolean logic

**Routing:**
- [ ] `trigger` / `t` - Trigger multiple outputs
- [ ] `pack`, `unpack` - Pack/unpack lists
- [ ] `route` - Route by first element
- [ ] `select` / `sel` - Select by value
- [ ] `spigot` - Pass/block messages
- [ ] `swap` - Swap two values
- [ ] `moses` - Split numbers by threshold

**Time:**
- [ ] `delay` - Delay message
- [ ] `metro` - Metronome
- [ ] `timer` - Measure time
- [ ] `pipe` - Delay stream of messages
- [ ] `line` - Linear ramp (control rate)

**Data:**
- [ ] `float` / `f` - Store float
- [ ] `int` / `i` - Store integer
- [ ] `symbol` - Store symbol
- [ ] `list` - Store list
- [ ] `value` / `v` - Named value
- [ ] `text` - Text buffer

**Arrays:**
- [ ] `array` - Array operations
- [ ] `tabread` - Read from array (control)
- [ ] `tabwrite` - Write to array (control)
- [ ] `soundfiler` - Load/save audio

**Send/Receive:**
- [ ] `send` / `s` - Send to named receiver
- [ ] `receive` / `r` - Receive from named sender
- [ ] `throw~`, `catch~` - Audio send/receive

**MIDI:**
- [ ] `notein`, `noteout` - MIDI notes
- [ ] `ctlin`, `ctlout` - Control change
- [ ] `bendin`, `bendout` - Pitch bend
- [ ] `pgmin`, `pgmout` - Program change
- [ ] `touchin`, `touchout` - Aftertouch
- [ ] `midiin`, `midiout` - Raw MIDI
- [ ] `makenote`, `stripnote` - Note utilities

**Misc:**
- [ ] `bang`, `loadbang` - Bang messages
- [ ] `print` - Print to console
- [ ] `inlet`, `outlet` - Subpatch I/O
- [ ] `inlet~`, `outlet~` - Audio subpatch I/O
- [ ] `openpanel`, `savepanel` - File dialogs
- [ ] `netsend`, `netreceive` - Network I/O

## Features

- [ ] Graph-on-parent support
- [ ] Abstractions (external .pd file references)
- [ ] Externals discovery
- [ ] Pd-extended / Purr Data compatibility
- [ ] libpd integration for patch validation
- [ ] Patch optimization (unused element removal, connection simplification)

## Documentation

- [ ] API Reference
  - [ ] All parameters and their valid ranges
  - [ ] Outlet indices meaning for different object types
  - [ ] PureData format details
  - [ ] Error conditions and how to handle them
- [ ] Architecture Documentation
  - [ ] Class diagrams
  - [ ] Data flow explanations
  - [ ] Design decision rationale
  - [ ] Extension points

## Code Quality

- [ ] Add `__all__` to `__init__.py` for explicit public API
- [ ] Add comment explaining `get_display_lines` regex in `api.py`
- [ ] Improve type hints for better IDE support
- [ ] Add integration test that runs `example.py` and validates output
- [ ] Convert `example.py` to pytest with output validation
