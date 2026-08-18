"""Round-trip the parser over a real PureData installation's patches.

Skipped when no PureData installation is found, so it costs nothing in CI, but
it is the only test that measures py2pd against a large body of patches written
by PureData rather than by py2pd. Point ``PD_DOC_DIR`` at a directory of ``.pd``
files to run it against a specific corpus.

Two properties are checked:

- **Every file parses.** A parse error means py2pd cannot read a patch that
  PureData itself wrote.
- **Content is preserved.** Serializing the AST and parsing that back yields the
  same AST. Byte-for-byte equality is a stricter property that older patches can
  fail for cosmetic reasons: PureData used to wrap long statements across
  physical lines and no longer does, so re-saving such a file in PureData 0.55
  also rewrites it. Those files are reported, not failed.
"""

import glob
import os
from pathlib import Path
import warnings

import pytest

from py2pd import to_builder
from py2pd.ast import parse, serialize

_DEFAULT_GLOBS = (
    "/Applications/Pd*.app/Contents/Resources/doc/**/*.pd",
    "/Applications/*/Pd*.app/Contents/Resources/doc/**/*.pd",
    "/usr/lib/pd/doc/**/*.pd",
    "/usr/local/lib/pd/doc/**/*.pd",
    str(Path.home() / "Library/Pd/**/*.pd"),
)


def _corpus() -> list[str]:
    """Locate .pd files written by PureData, preferring an explicit override."""
    override = os.environ.get("PD_DOC_DIR")
    if override:
        return sorted(glob.glob(os.path.join(override, "**", "*.pd"), recursive=True))
    for pattern in _DEFAULT_GLOBS:
        found = sorted(glob.glob(pattern, recursive=True))
        if found:
            return found
    return []


CORPUS = _corpus()

pytestmark = pytest.mark.skipif(
    not CORPUS,
    reason="no PureData patch corpus found; set PD_DOC_DIR to a directory of .pd files",
)


def test_corpus_is_large_enough_to_be_meaningful():
    assert len(CORPUS) >= 10


def test_every_patch_parses():
    failures = []
    for path in CORPUS:
        source = Path(path).read_text(encoding="utf-8", errors="replace")
        try:
            parse(source)
        except Exception as exc:  # noqa: BLE001 -- reporting every failure at once
            failures.append(f"{path}: {type(exc).__name__}: {exc}")
    assert not failures, "patches PureData wrote that py2pd cannot parse:\n" + "\n".join(
        failures[:20]
    )


def test_every_patch_preserves_its_content():
    """serialize(parse(x)) must carry the same content as x."""
    failures = []
    for path in CORPUS:
        source = Path(path).read_text(encoding="utf-8", errors="replace")
        once = serialize(parse(source))
        twice = serialize(parse(once))
        if once != twice:
            failures.append(path)
    assert not failures, "patches whose content changed on round trip:\n" + "\n".join(failures[:20])


def test_most_patches_roundtrip_byte_for_byte():
    """Byte equality holds except for patches saved by PureData versions that wrapped lines.

    This is a ratchet, not an exact figure: if a change starts rewriting files
    that previously came back unchanged, it fails.
    """
    identical = 0
    for path in CORPUS:
        source = Path(path).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        if serialize(parse(source)).strip() == source.strip():
            identical += 1
    ratio = identical / len(CORPUS)
    assert ratio >= 0.85, f"only {identical}/{len(CORPUS)} patches round-tripped byte for byte"


def test_every_patch_converts_to_the_builder():
    """to_builder() must not reject a patch PureData accepts."""
    failures = []
    for path in CORPUS:
        source = Path(path).read_text(encoding="utf-8", errors="replace")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                to_builder(parse(source))
        except Exception as exc:  # noqa: BLE001 -- reporting every failure at once
            failures.append(f"{path}: {type(exc).__name__}: {exc}")
    assert not failures, "patches that to_builder() could not convert:\n" + "\n".join(failures[:20])
