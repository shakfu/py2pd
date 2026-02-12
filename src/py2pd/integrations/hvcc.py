"""hvcc (Heavy Compiler Collection) integration for py2pd.

Provides:
- ``HVCC_SUPPORTED_OBJECTS`` -- the set of Pd objects that hvcc can compile
- ``HeavyPatcher`` -- a ``Patcher`` subclass that enforces the hvcc subset
- ``validate_for_hvcc()`` -- check any Patcher or PdPatch for hvcc compatibility
- ``compile_hvcc()`` -- shell out to the ``hvcc`` CLI (requires ``hvcc`` installed)

hvcc is an optional dependency.  Authoring and validation work without it;
only ``compile_hvcc()`` requires the ``hvcc`` package.

Usage::

    from py2pd.integrations.hvcc import HeavyPatcher, validate_for_hvcc, HvccGenerator

    p = HeavyPatcher()
    freq = p.add_param("freq", min_val=20.0, max_val=20000.0, default=440.0)
    osc = p.add("osc~")
    dac = p.add("dac~")
    p.link(freq, osc)
    p.link(osc, dac)
    p.link(osc, dac, inlet=1)

    result = validate_for_hvcc(p)
    assert result.ok
"""

from dataclasses import dataclass, field
from enum import Enum
import os
import subprocess
import tempfile
from typing import Optional, Sequence, Union

from ..api import LayoutManager, Obj, Patcher, Subpatch
from ..ast import PdObj, PdPatch, PdSubpatch, serialize

# ---------------------------------------------------------------------------
# Object registry
# ---------------------------------------------------------------------------

HVCC_SUPPORTED_OBJECTS: set[str] = {
    # Message objects (~95)
    "!=",
    "%",
    "&",
    "&&",
    "|",
    "||",
    "*",
    "+",
    "-",
    "/",
    "<",
    "<<",
    "<=",
    "==",
    ">",
    ">=",
    ">>",
    "abs",
    "atan",
    "atan2",
    "b",
    "bang",
    "bendin",
    "bendout",
    "bng",
    "change",
    "clip",
    "cnv",
    "cos",
    "ctlin",
    "ctlout",
    "dbtopow",
    "dbtorms",
    "declare",
    "del",
    "delay",
    "div",
    "exp",
    "expr",
    "f",
    "float",
    "floatatom",
    "ftom",
    "hradio",
    "hsl",
    "i",
    "inlet",
    "int",
    "line",
    "loadbang",
    "log",
    "makenote",
    "max",
    "metro",
    "midiin",
    "midiout",
    "midirealtimein",
    "min",
    "mod",
    "moses",
    "mtof",
    "nbx",
    "notein",
    "noteout",
    "outlet",
    "pack",
    "pd",
    "pgmin",
    "pgmout",
    "pipe",
    "poly",
    "polytouchin",
    "polytouchout",
    "pow",
    "powtodb",
    "print",
    "r",
    "random",
    "receive",
    "rmstodb",
    "route",
    "s",
    "sel",
    "select",
    "send",
    "sin",
    "spigot",
    "sqrt",
    "stripnote",
    "swap",
    "symbol",
    "symbolatom",
    "t",
    "table",
    "tabread",
    "tabwrite",
    "tan",
    "tgl",
    "timer",
    "touchin",
    "touchout",
    "trigger",
    "unpack",
    "until",
    "vradio",
    "vsl",
    "wrap",
    # Signal objects (~68)
    "*~",
    "+~",
    "-~",
    "/~",
    "abs~",
    "adc~",
    "bang~",
    "biquad~",
    "block~",
    "bp~",
    "catch~",
    "clip~",
    "complex-mod~",
    "cos~",
    "cpole~",
    "czero_rev~",
    "czero~",
    "dac~",
    "dbtopow~",
    "dbtorms~",
    "delread~",
    "delread4~",
    "delwrite~",
    "env~",
    "exp~",
    "expr~",
    "ftom~",
    "hilbert~",
    "hip~",
    "inlet~",
    "line~",
    "lop~",
    "max~",
    "min~",
    "mtof~",
    "noise~",
    "osc~",
    "outlet~",
    "phasor~",
    "pow~",
    "powtodb~",
    "q8_rsqrt~",
    "q8_sqrt~",
    "r~",
    "receive~",
    "rmstodb~",
    "rpole~",
    "rsqrt~",
    "rzero_rev~",
    "rzero~",
    "s~",
    "samphold~",
    "samplerate~",
    "send~",
    "sig~",
    "snapshot~",
    "sqrt~",
    "tabosc4~",
    "tabplay~",
    "tabread4~",
    "tabread~",
    "tabwrite~",
    "throw~",
    "vcf~",
    "vd~",
    "wrap~",
}

HVCC_MIDI_OBJECTS: set[str] = {
    "notein",
    "noteout",
    "ctlin",
    "ctlout",
    "bendin",
    "bendout",
    "midiin",
    "midiout",
    "midirealtimein",
    "pgmin",
    "pgmout",
    "touchin",
    "touchout",
    "polytouchin",
    "polytouchout",
}

HVCC_MIDI_GENERATORS: frozenset[str] = frozenset({"dpf", "daisy", "owl"})

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HvccError(Exception):
    """Base exception for hvcc-related errors."""


class HvccUnsupportedError(HvccError):
    """Raised when a patch contains objects not supported by hvcc."""

    def __init__(self, unsupported: list[str]) -> None:
        self.unsupported = unsupported
        names = ", ".join(sorted(unsupported))
        super().__init__(f"Unsupported hvcc objects: {names}")


class HvccCompileError(HvccError):
    """Raised when hvcc compilation fails."""


# ---------------------------------------------------------------------------
# Generator enum
# ---------------------------------------------------------------------------


class HvccGenerator(str, Enum):
    """hvcc output generators."""

    C = "c"
    DAISY = "daisy"
    DPF = "dpf"
    JS = "js"
    OWL = "owl"
    PDEXT = "pdext"
    UNITY = "unity"
    WWISE = "wwise"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class HvccValidationResult:
    """Result of validating a patch for hvcc compatibility."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _check_object_supported(
    class_name: str,
    generators: Sequence[HvccGenerator] | None = None,
) -> list[str]:
    """Check whether a single object name is hvcc-compatible.

    Returns a list of error strings (empty if supported).
    """
    errors: list[str] = []
    if class_name not in HVCC_SUPPORTED_OBJECTS:
        errors.append(f"unsupported object: {class_name}")
        return errors
    if generators and class_name in HVCC_MIDI_OBJECTS:
        gen_values = {g.value if isinstance(g, HvccGenerator) else g for g in generators}
        if not gen_values & HVCC_MIDI_GENERATORS:
            errors.append(
                f"MIDI object '{class_name}' requires a generator that supports MIDI "
                f"({', '.join(sorted(HVCC_MIDI_GENERATORS))}), "
                f"but generators are: {', '.join(sorted(gen_values))}"
            )
    return errors


def _walk_builder_nodes(patch: Patcher) -> list[str]:
    """Extract object class names from a Patcher, recursing into subpatches."""
    names: list[str] = []
    _walk_builder_nodes_into(patch, names)
    return names


def _walk_builder_nodes_into(patch: Patcher, names: list[str]) -> None:
    """Recursive helper for _walk_builder_nodes."""
    for node in patch.nodes:
        if isinstance(node, Subpatch):
            _walk_builder_nodes_into(node.src, names)
            continue
        if isinstance(node, Obj):
            text = node.parameters.get("text", "")
            parts = text.split()
            if parts:
                names.append(parts[0])


def _walk_ast_nodes(patch: PdPatch) -> list[str]:
    """Extract object class names from a PdPatch AST, recursing into subpatches."""
    names: list[str] = []
    _walk_ast_elements(patch.elements, names)
    return names


def _walk_ast_elements(elements: list, names: list[str]) -> None:
    """Recursive helper for _walk_ast_nodes."""
    for elem in elements:
        if isinstance(elem, PdObj):
            names.append(elem.class_name)
        elif isinstance(elem, PdSubpatch):
            _walk_ast_elements(elem.elements, names)


def validate_for_hvcc(
    patch: Union[Patcher, PdPatch],
    *,
    generators: Sequence[HvccGenerator] | None = None,
) -> HvccValidationResult:
    """Validate a patch for hvcc compatibility.

    Walks all nodes (recursing into subpatches) and checks each object name
    against ``HVCC_SUPPORTED_OBJECTS``.  If *generators* is given, also checks
    MIDI objects against generator constraints.

    Parameters
    ----------
    patch : Patcher or PdPatch
        The patch to validate.
    generators : sequence of HvccGenerator, optional
        Target generators.  If provided, MIDI objects are checked for
        generator compatibility.

    Returns
    -------
    HvccValidationResult
        Contains ``ok``, ``errors``, and ``warnings``.
    """
    if isinstance(patch, Patcher):
        class_names = _walk_builder_nodes(patch)
    elif isinstance(patch, PdPatch):
        class_names = _walk_ast_nodes(patch)
    else:
        raise TypeError(f"Expected Patcher or PdPatch, got {type(patch).__name__}")

    errors: list[str] = []
    warnings: list[str] = []

    for name in class_names:
        errs = _check_object_supported(name, generators)
        errors.extend(errs)

    return HvccValidationResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# HeavyPatcher
# ---------------------------------------------------------------------------


class HeavyPatcher(Patcher):
    """A Patcher subclass that enforces hvcc-supported objects.

    All ``add()`` calls are validated against ``HVCC_SUPPORTED_OBJECTS``
    before delegating to the parent class.  Provides convenience methods
    for hvcc annotations (``@hv_param``, ``@hv_event``, ``@hv_table``).

    Parameters
    ----------
    filename : str, optional
        Default filename for save().
    layout : LayoutManager, optional
        Custom layout manager.
    generators : sequence of HvccGenerator, optional
        Target generators (used for MIDI validation).
    """

    def __init__(
        self,
        filename: Optional[str] = None,
        layout: Optional[LayoutManager] = None,
        generators: Sequence[HvccGenerator] | None = None,
    ) -> None:
        super().__init__(filename=filename, layout=layout)
        self.generators = generators

    def add(
        self,
        text: str,
        *,
        source_path: Optional[str] = None,
        new_row: float = 1,
        new_col: float = 0,
        x_pos: int = -1,
        y_pos: int = -1,
        num_inlets: Optional[int] = None,
        num_outlets: Optional[int] = None,
    ) -> Obj:
        """Add an object, validating hvcc compatibility first.

        Parameters
        ----------
        text : str
            Object text (e.g., ``'osc~ 440'``)

        Raises
        ------
        HvccUnsupportedError
            If the object is not supported by hvcc.

        Returns
        -------
        Obj
            The created object
        """
        parts = text.split()
        class_name = parts[0] if parts else ""
        errs = _check_object_supported(class_name, self.generators)
        if errs:
            raise HvccUnsupportedError([class_name])
        return super().add(
            text,
            source_path=source_path,
            new_row=new_row,
            new_col=new_col,
            x_pos=x_pos,
            y_pos=y_pos,
            num_inlets=num_inlets,
            num_outlets=num_outlets,
        )

    def add_param(
        self,
        name: str,
        *,
        min_val: float = 0.0,
        max_val: float = 1.0,
        default: float = 0.5,
        type: str = "float",
        **kwargs,
    ) -> Obj:
        """Add a ``[r name @hv_param min max default [type]]`` receiver.

        Creates a receive object with the ``@hv_param`` annotation, exposing
        a parameter to the host (e.g. DAW plugin parameter).

        Parameters
        ----------
        name : str
            Parameter name (also the receive symbol).
        min_val : float
            Minimum value (default: 0.0).
        max_val : float
            Maximum value (default: 1.0).
        default : float
            Default value (default: 0.5).
        type : str
            Parameter type -- ``"float"`` or ``"bool"`` (default: ``"float"``).
        **kwargs
            Forwarded to ``add()`` (e.g. ``new_row``, ``x_pos``).

        Returns
        -------
        Obj
            The created receive object.
        """
        text = f"r {name} @hv_param {min_val} {max_val} {default}"
        if type != "float":
            text += f" {type}"
        return self.add(text, **kwargs)

    def add_param_output(self, name: str, **kwargs) -> Obj:
        """Add a ``[s name @hv_param]`` sender for output parameters.

        Parameters
        ----------
        name : str
            Parameter name (also the send symbol).
        **kwargs
            Forwarded to ``add()`` (e.g. ``new_row``, ``x_pos``).

        Returns
        -------
        Obj
            The created send object.
        """
        return self.add(f"s {name} @hv_param", **kwargs)

    def add_event(self, name: str, **kwargs) -> Obj:
        """Add a ``[r name @hv_event]`` receiver for events.

        Parameters
        ----------
        name : str
            Event name (also the receive symbol).
        **kwargs
            Forwarded to ``add()`` (e.g. ``new_row``, ``x_pos``).

        Returns
        -------
        Obj
            The created receive object.
        """
        return self.add(f"r {name} @hv_event", **kwargs)

    def add_table(
        self,
        name: str,
        size: int,
        *,
        expose: bool = True,
        **kwargs,
    ) -> Obj:
        """Add a ``[table name size [@hv_table]]`` object.

        Parameters
        ----------
        name : str
            Table name.  Must not contain spaces.
        size : int
            Table size in samples.
        expose : bool
            If True (default), append ``@hv_table`` to expose to the host.
        **kwargs
            Forwarded to ``add()`` (e.g. ``new_row``, ``x_pos``).

        Returns
        -------
        Obj
            The created table object.

        Raises
        ------
        ValueError
            If *name* contains spaces.
        """
        if " " in name:
            raise ValueError(f"Table name must not contain spaces: {name!r}")
        text = f"table {name} {size}"
        if expose:
            text += " @hv_table"
        return self.add(text, **kwargs)


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------


@dataclass
class HvccCompileResult:
    """Result of running the hvcc compiler."""

    ok: bool
    output_dir: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


def compile_hvcc(
    patch: Union[Patcher, PdPatch],
    *,
    output_dir: str,
    name: str = "heavy",
    generators: Sequence[HvccGenerator] = (HvccGenerator.C,),
    search_paths: Sequence[str] | None = None,
    metadata_file: str | None = None,
    copyright: str | None = None,
    validate: bool = True,
) -> HvccCompileResult:
    """Compile a patch using the hvcc CLI.

    Serializes the patch to a temporary file, builds the ``hvcc`` command
    line, and runs it via ``subprocess.run()``.

    Parameters
    ----------
    patch : Patcher or PdPatch
        The patch to compile.
    output_dir : str
        Directory for hvcc output.
    name : str
        Patch name passed to hvcc ``-n`` (default: ``"heavy"``).
    generators : sequence of HvccGenerator
        Target generators (default: C only).
    search_paths : sequence of str, optional
        Additional search paths for hvcc ``-p``.
    metadata_file : str, optional
        Path to metadata JSON file for hvcc ``-m``.
    copyright : str, optional
        Copyright string for hvcc ``--copyright``.
    validate : bool
        If True (default), run ``validate_for_hvcc()`` before compiling.

    Returns
    -------
    HvccCompileResult

    Raises
    ------
    ImportError
        If ``hvcc`` is not installed.
    HvccUnsupportedError
        If *validate* is True and the patch contains unsupported objects.
    """
    try:
        import hvcc as _hvcc  # noqa: F401
    except ImportError:
        raise ImportError(
            "hvcc is required for compilation but is not installed. "
            "Install it with: pip install hvcc"
        ) from None

    if validate:
        result = validate_for_hvcc(patch, generators=generators)
        if not result.ok:
            raise HvccUnsupportedError(
                [
                    e.removeprefix("unsupported object: ")
                    for e in result.errors
                    if e.startswith("unsupported object: ")
                ]
            )

    # Serialize patch
    if isinstance(patch, Patcher):
        content = str(patch)
    elif isinstance(patch, PdPatch):
        content = serialize(patch)
    else:
        raise TypeError(f"Expected Patcher or PdPatch, got {type(patch).__name__}")

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pd", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Build command
        cmd = ["hvcc", tmp_path, "-o", output_dir, "-n", name]
        for gen in generators:
            gen_val = gen.value if isinstance(gen, HvccGenerator) else str(gen)
            cmd.extend(["-g", gen_val])
        if search_paths:
            for sp in search_paths:
                cmd.extend(["-p", sp])
        if metadata_file:
            cmd.extend(["-m", metadata_file])
        if copyright:
            cmd.extend(["--copyright", copyright])

        proc = subprocess.run(cmd, capture_output=True, text=True)

        errors: list[str] = []
        warnings: list[str] = []
        for line in proc.stderr.splitlines():
            lower = line.lower()
            if "error" in lower:
                errors.append(line)
            elif "warning" in lower:
                warnings.append(line)

        if proc.returncode != 0 and not errors:
            errors.append(f"hvcc exited with code {proc.returncode}")

        return HvccCompileResult(
            ok=proc.returncode == 0,
            output_dir=output_dir,
            errors=errors,
            warnings=warnings,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
