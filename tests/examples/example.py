"""
PureData Compiler - Comprehensive Examples
==========================================

This module demonstrates all major features of py2pd:
- Basic patch creation with the new Patcher API
- All node types (objects, messages, GUI elements)
- Connection patterns with link()
- Subpatch creation and nesting
- Layout options (default, grid, auto-layout)
- SVG visualization export
- Validation and error handling
"""

from py2pd import (
    Patcher,
    GridLayoutManager,
    NodeNotFoundError,
    InvalidConnectionError,
    CycleWarning,
)


# =============================================================================
# Example 1: Simple Synthesizer
# =============================================================================


def simple_synth() -> Patcher:
    """A basic synthesizer: oscillator -> gain -> output."""
    p = Patcher("simple_synth.pd")

    osc = p.add("osc~ 440")
    gain = p.add("*~ 0.3")
    dac = p.add("dac~")

    p.link(osc, gain)
    p.link(gain, dac)
    p.link(gain, dac, inlet=1)  # stereo

    return p


# =============================================================================
# Example 2: All GUI Element Types
# =============================================================================


def gui_elements_demo() -> Patcher:
    """Demonstrates all available GUI elements."""
    p = Patcher("gui_demo.pd")

    # Bang button - sends bang on click
    p.add_bang(send="trigger", label="Click")

    # Toggle - on/off switch
    p.add_toggle(default_value=1, send="onoff")

    # Number box - editable number display
    p.add_numberbox(min_val=0, max_val=127, width=5)

    # Sliders - vertical and horizontal
    p.add_vslider(min_val=0, max_val=1000, height=100)
    p.add_hslider(min_val=20, max_val=20000, width=150)

    # Radio buttons - vertical and horizontal
    p.add_vradio(number=4)
    p.add_hradio(number=8)

    # Symbol atom - text input
    p.add_symbol(width=15)

    # Float atom - number input
    p.add_float(width=8, lower_limit=0, upper_limit=100)

    # Canvas - background/label area
    p.add_canvas(width=200, height=30, label="Controls")

    # VU meter - level display
    p.add_vu(height=80)

    return p


# =============================================================================
# Example 3: Subpatch Patterns
# =============================================================================


def envelope_subpatch() -> Patcher:
    """An ADSR envelope generator as a reusable subpatch."""
    p = Patcher()

    # Inlets for parameters
    inlet_trig = p.add("inlet")  # trigger
    inlet_attack = p.add("inlet")  # attack time ms
    inlet_decay = p.add("inlet")  # decay time ms
    inlet_sustain = p.add("inlet")  # sustain level 0-1
    inlet_release = p.add("inlet")  # release time ms

    # Pack parameters
    pack = p.add("pack f f f f")
    p.link(inlet_attack, pack, inlet=0)
    p.link(inlet_decay, pack, inlet=1)
    p.link(inlet_sustain, pack, inlet=2)
    p.link(inlet_release, pack, inlet=3)

    # Envelope state
    trigger = p.add("t b b")
    p.link(inlet_trig, trigger)

    # ADSR implementation using vline~
    adsr = p.add("vline~")
    msg_attack = p.add_msg("0, 1 $1")
    p.add_msg("$3 $2")
    p.add_msg("0 $4")

    p.link(trigger, msg_attack, outlet=0)
    p.link(pack, msg_attack, inlet=1)
    p.link(msg_attack, adsr)

    # Output
    outlet = p.add("outlet~")
    p.link(adsr, outlet)

    return p


def synth_with_subpatch() -> Patcher:
    """A synthesizer using the envelope subpatch."""
    p = Patcher("synth_with_envelope.pd")

    # Oscillator section
    freq = p.add_float(label="freq")
    osc = p.add("osc~")
    p.link(freq, osc)

    # Envelope section
    bang = p.add_bang(label="trigger")
    attack = p.add_float(label="A")
    decay = p.add_float(label="D")
    sustain = p.add_float(label="S")
    release = p.add_float(label="R")

    env = p.add_subpatch("envelope", envelope_subpatch())
    p.link(bang, env, inlet=0)
    p.link(attack, env, inlet=1)
    p.link(decay, env, inlet=2)
    p.link(sustain, env, inlet=3)
    p.link(release, env, inlet=4)

    # VCA (voltage controlled amplifier)
    vca = p.add("*~")
    p.link(osc, vca)
    p.link(env, vca, inlet=1)

    # Output
    dac = p.add("dac~")
    p.link(vca, dac)
    p.link(vca, dac, inlet=1)

    return p


# =============================================================================
# Example 4: Grid Layout
# =============================================================================


def grid_layout_demo() -> Patcher:
    """Demonstrates GridLayoutManager for organized node placement."""
    grid = GridLayoutManager(columns=4, cell_width=80, cell_height=35)
    p = Patcher("grid_demo.pd", layout=grid)

    # Create a 4x4 grid of objects
    nodes = []
    for i in range(16):
        node = p.add(f"obj{i}")
        nodes.append(node)

    # Connect in a chain
    for i in range(15):
        p.link(nodes[i], nodes[i + 1])

    return p


# =============================================================================
# Example 5: Auto Layout for Signal Flow
# =============================================================================


def auto_layout_demo() -> Patcher:
    """Demonstrates auto_layout() for automatic signal flow arrangement."""
    p = Patcher("auto_layout_demo.pd")

    # Create nodes in arbitrary order
    dac = p.add("dac~")
    mixer = p.add("+~")
    osc1 = p.add("osc~ 440")
    osc2 = p.add("osc~ 550")
    gain1 = p.add("*~ 0.3")
    gain2 = p.add("*~ 0.3")

    # Build signal flow
    p.link(osc1, gain1)
    p.link(osc2, gain2)
    p.link(gain1, mixer)
    p.link(gain2, mixer, inlet=1)
    p.link(mixer, dac)
    p.link(mixer, dac, inlet=1)

    # Auto-arrange based on signal flow
    p.auto_layout(margin=50, row_spacing=50, col_spacing=100)

    return p


# =============================================================================
# Example 6: Error Handling
# =============================================================================


def error_handling_demo():
    """Demonstrates proper error handling."""
    p = Patcher()

    # Create some nodes
    osc = p.add("osc~ 440")
    dac = p.add("dac~")
    p.link(osc, dac)

    # Example 1: NodeNotFoundError - linking nodes from different patches
    p2 = Patcher()
    other_node = p2.add("test")
    try:
        p.link(osc, other_node)  # other_node not in p
    except NodeNotFoundError as e:
        print(f"NodeNotFoundError: {e}")

    # Example 2: Validation with inlet/outlet counts
    p3 = Patcher()
    p3.add("osc~", num_inlets=2, num_outlets=1)
    p3.add("dac~", num_inlets=2, num_outlets=0)

    # Manually add an invalid connection (outlet 5 doesn't exist)
    from py2pd.api import Connection

    p3.connections.append(Connection(0, 5, 1, 0))

    try:
        p3.validate_connections(check_cycles=False)
    except InvalidConnectionError as e:
        print(f"InvalidConnectionError: {e}")

    # Example 3: Cycle detection
    import warnings

    p4 = Patcher()
    a = p4.add("delread~ delay")
    b = p4.add("+~")
    c = p4.add("delwrite~ delay")
    p4.link(a, b)
    p4.link(b, c)
    p4.link(c, a)  # Creates a cycle (feedback loop)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        p4.validate_connections(check_cycles=True)
        if w and issubclass(w[0].category, CycleWarning):
            print(f"CycleWarning: {w[0].message}")

    # Example 4: Save without filename
    p5 = Patcher()  # No filename
    p5.add("test")
    try:
        p5.save()  # No filename specified
    except ValueError as e:
        print(f"ValueError: {e}")


# =============================================================================
# Example 7: SVG Visualization
# =============================================================================


def svg_export_demo() -> Patcher:
    """Demonstrates SVG export for patch visualization."""
    p = Patcher("svg_demo.pd")

    # Build a simple patch
    loadbang = p.add("loadbang")
    msg = p.add_msg("440")
    osc = p.add("osc~")
    gain = p.add("*~ 0.5")
    dac = p.add("dac~")

    p.link(loadbang, msg)
    p.link(msg, osc)
    p.link(osc, gain)
    p.link(gain, dac)
    p.link(gain, dac, inlet=1)

    # Export as SVG
    p.save_svg("svg_demo.svg")
    print("SVG saved to svg_demo.svg")

    # Get SVG as string
    svg_content = p.to_svg(padding=30, node_height=25)
    print(f"SVG length: {len(svg_content)} characters")

    return p


# =============================================================================
# Example 8: Complex Patch - Polyphonic Synthesizer Voice
# =============================================================================


def poly_voice() -> Patcher:
    """A complete synthesizer voice with oscillators, filter, and envelope."""
    p = Patcher("poly_voice.pd")

    # --- Control inputs ---
    freq_in = p.add("inlet")
    gate_in = p.add("inlet")
    vel_in = p.add("inlet")

    # --- Oscillator section ---
    # Oscillator 1
    osc1 = p.add("osc~")
    p.link(freq_in, osc1)

    # Oscillator 2 (detuned)
    detune = p.add("* 1.01")  # Slight detune
    p.link(freq_in, detune)
    osc2 = p.add("osc~")
    p.link(detune, osc2)

    # Mix oscillators
    osc_mix = p.add("+~")
    p.link(osc1, osc_mix)
    p.link(osc2, osc_mix, inlet=1)

    # --- Filter section ---
    cutoff = p.add("* 4")  # Cutoff tracks frequency
    p.link(freq_in, cutoff)
    filter_obj = p.add("lop~")
    p.link(osc_mix, filter_obj)
    p.link(cutoff, filter_obj, inlet=1)

    # --- Amplitude envelope ---
    env_adsr = p.add("vline~")
    gate_trigger = p.add("t b b")
    p.link(gate_in, gate_trigger)

    env_attack = p.add_msg("0, 1 10")
    env_release = p.add_msg("0 100")
    p.link(gate_trigger, env_attack, outlet=0)
    p.link(gate_trigger, env_release, outlet=1)
    p.link(env_attack, env_adsr)
    p.link(env_release, env_adsr)

    # --- VCA ---
    vca = p.add("*~")
    p.link(filter_obj, vca)
    p.link(env_adsr, vca, inlet=1)

    # --- Velocity scaling ---
    vel_scale = p.add("/ 127")
    p.link(vel_in, vel_scale)
    vel_vca = p.add("*~")
    p.link(vca, vel_vca)
    p.link(vel_scale, vel_vca, inlet=1)

    # --- Output ---
    outlet = p.add("outlet~")
    p.link(vel_vca, outlet)

    # Auto-arrange for clean layout
    p.auto_layout(margin=30, row_spacing=35, col_spacing=90)

    return p


# =============================================================================
# Main - Run all examples
# =============================================================================

if __name__ == "__main__":
    print("PureData Compiler Examples")
    print("=" * 50)

    # Example 1: Simple synth
    print("\n1. Simple Synthesizer")
    patch = simple_synth()
    patch.save()
    print(
        f"   Saved: simple_synth.pd ({len(patch.nodes)} nodes, {len(patch.connections)} connections)"
    )

    # Example 2: GUI elements
    print("\n2. GUI Elements Demo")
    patch = gui_elements_demo()
    patch.save()
    print(f"   Saved: gui_demo.pd ({len(patch.nodes)} nodes)")

    # Example 3: Subpatch
    print("\n3. Synthesizer with Envelope Subpatch")
    patch = synth_with_subpatch()
    patch.save()
    print("   Saved: synth_with_envelope.pd")

    # Example 4: Grid layout
    print("\n4. Grid Layout Demo")
    patch = grid_layout_demo()
    patch.save()
    print("   Saved: grid_demo.pd (4x4 grid)")

    # Example 5: Auto layout
    print("\n5. Auto Layout Demo")
    patch = auto_layout_demo()
    patch.save()
    print("   Saved: auto_layout_demo.pd (auto-arranged)")

    # Example 6: Error handling
    print("\n6. Error Handling Demo")
    error_handling_demo()

    # Example 7: SVG export
    print("\n7. SVG Export Demo")
    patch = svg_export_demo()
    patch.save()

    # Example 8: Complex patch
    print("\n8. Polyphonic Voice")
    patch = poly_voice()
    patch.save()
    print(
        f"   Saved: poly_voice.pd ({len(patch.nodes)} nodes, {len(patch.connections)} connections)"
    )

    print("\n" + "=" * 50)
    print("All examples completed successfully!")
