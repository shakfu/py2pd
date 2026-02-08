"""Patch validation via libpd (cypd).

Loads a patch into libpd and captures print output to detect errors
(missing objects, unresolved externals, etc.). Requires the optional
``cypd`` package -- raises ``ImportError`` if not installed.

Usage::

    from py2pd import validate_patch, Patcher
    p = Patcher()
    osc = p.add('osc~ 440')
    dac = p.add('dac~')
    p.link(osc, dac)
    result = validate_patch(p)
    assert result.ok
"""

import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..api import Patcher
from ..ast import PdPatch, parse, serialize

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of validating a PureData patch via libpd."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Print accumulator -- libpd delivers fragments, we need complete lines
# ---------------------------------------------------------------------------


class _PrintAccumulator:
    """Collects libpd print fragments and splits them into complete lines.

    libpd's print hook delivers output as word-level fragments (e.g.
    ``"hello"``, ``" "``, ``"world\\n"``).  This callable buffers fragments
    and produces finished lines on each ``\\n``.
    """

    def __init__(self) -> None:
        self._buffer: str = ""
        self.lines: list[str] = []

    def __call__(self, fragment: str) -> None:
        self._buffer += fragment
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:
                self.lines.append(line)

    def flush(self) -> None:
        """Flush any remaining partial line."""
        if self._buffer.strip():
            self.lines.append(self._buffer.strip())
        self._buffer = ""


# ---------------------------------------------------------------------------
# Message classification
# ---------------------------------------------------------------------------

_ERROR_PATTERNS = ("couldn't create", "no such object", "error:")
_WARNING_PATTERNS = ("warning:", "deprecated")


def _classify_messages(lines: list[str]) -> tuple[list[str], list[str]]:
    """Classify accumulated libpd lines into errors and warnings.

    Returns (errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []
    for line in lines:
        lower = line.lower()
        if any(pat in lower for pat in _ERROR_PATTERNS):
            errors.append(line)
        elif any(pat in lower for pat in _WARNING_PATTERNS):
            warnings.append(line)
    return errors, warnings


# ---------------------------------------------------------------------------
# libpd lazy init
# ---------------------------------------------------------------------------

_libpd_initialized = False


def _ensure_libpd() -> None:
    """Lazy-initialize libpd exactly once.  Raises ImportError if cypd is missing."""
    global _libpd_initialized
    if _libpd_initialized:
        return

    try:
        import cypd  # noqa: F401
    except ImportError:
        raise ImportError(
            "cypd is required for patch validation but is not installed. "
            "Install it with: pip install cypd"
        ) from None

    cypd.init()
    cypd.init_audio(1, 2, 44100)
    _libpd_initialized = True


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _serialize_input(patch: "Patcher | PdPatch") -> str:
    """Serialize a Patcher or PdPatch to .pd file content."""
    if isinstance(patch, Patcher):
        return str(patch)
    if isinstance(patch, PdPatch):
        return serialize(patch)
    raise TypeError(f"Expected Patcher or PdPatch, got {type(patch).__name__}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_patch(
    patch: "Patcher | PdPatch",
    *,
    search_paths: Optional[Sequence[str]] = None,
    include_default_paths: bool = True,
    use_declare_paths: bool = True,
    check_receivers: Optional[Sequence[str]] = None,
) -> ValidationResult:
    """Validate a PureData patch by loading it in libpd.

    Serializes the patch to a temporary file, configures search paths,
    loads the patch via cypd, and captures libpd print output to detect
    errors (missing objects, unresolved externals, etc.).

    Parameters
    ----------
    patch : Patcher or PdPatch
        The patch to validate.
    search_paths : sequence of str, optional
        Additional directories to add to libpd's search path.
    include_default_paths : bool
        Whether to include platform-default PureData search paths
        (default ``True``).
    use_declare_paths : bool
        Whether to extract and add ``#X declare -path`` entries from the
        patch (default ``True``).
    check_receivers : sequence of str, optional
        Receiver names to verify exist after loading the patch.

    Returns
    -------
    ValidationResult
        Contains ``ok`` (bool), ``errors``, ``warnings``, and ``log``.

    Raises
    ------
    ImportError
        If ``cypd`` is not installed.
    TypeError
        If *patch* is not a ``Patcher`` or ``PdPatch``.
    """
    _ensure_libpd()

    import cypd

    content = _serialize_input(patch)

    # Set up print accumulator
    acc = _PrintAccumulator()
    cypd.set_print_callback(acc)

    # Configure search paths
    cypd.clear_search_path()
    if search_paths:
        for p in search_paths:
            cypd.add_to_search_path(p)
    if include_default_paths:
        from ..discover import default_search_paths

        for p in default_search_paths():
            cypd.add_to_search_path(p)
    if use_declare_paths:
        try:
            ast = parse(content)
            from ..discover import extract_declare_paths

            for p in extract_declare_paths(ast):
                cypd.add_to_search_path(p)
        except Exception:
            pass  # non-fatal: declare extraction is best-effort

    # Write to temp file and load
    tmp_path: Optional[str] = None
    patch_id = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pd", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        tmp_dir = os.path.dirname(tmp_path)
        tmp_name = os.path.basename(tmp_path)
        patch_id = cypd.open_patch(tmp_name, tmp_dir)

        # Flush any remaining print fragments
        acc.flush()

        # Classify messages
        errors, warnings = _classify_messages(acc.lines)

        # Check receivers if requested
        if check_receivers:
            for name in check_receivers:
                if not cypd.exists(name):
                    errors.append(f"receiver not found: {name}")

        return ValidationResult(
            ok=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            log=list(acc.lines),
        )

    except IOError as exc:
        acc.flush()
        errors, warnings = _classify_messages(acc.lines)
        errors.append(f"failed to open patch: {exc}")
        return ValidationResult(
            ok=False,
            errors=errors,
            warnings=warnings,
            log=list(acc.lines),
        )
    finally:
        if patch_id is not None:
            try:
                cypd.close_patch(patch_id)
            except Exception:
                pass
        cypd.clear_search_path()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
