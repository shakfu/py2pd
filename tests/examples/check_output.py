"""Verify the .pd files written by example.py.

Two checks, weakest first:

- Every file re-parses and re-serializes byte-identically. This catches output
  py2pd itself can no longer read back, which a build that only ran example.py
  would report as success.
- Every file opens in PureData with a silent console. This is the only check
  that catches bytes which serialize perfectly but describe a patch PureData
  rejects, such as an out-of-range connection index. Skipped when no ``pd``
  binary is found; set ``PD_BIN`` to point at one.

Exits non-zero on the first failing file. Run it via ``make examples``.
"""

import difflib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from example import OUTPUT_DIR  # noqa: E402  # sibling module, same directory

from py2pd import parse  # noqa: E402
from py2pd.ast import serialize  # noqa: E402
from tests.pd_runner import PD_BIN, run_in_pd  # noqa: E402


def check_roundtrip(path: Path) -> str:
    """Return a diff of *path* against its reserialization, empty if identical."""
    written = path.read_text(encoding="utf-8")
    reserialized = serialize(parse(written))
    if reserialized.strip() == written.strip():
        return ""
    return "\n".join(
        difflib.unified_diff(
            written.strip().splitlines(),
            reserialized.strip().splitlines(),
            "written",
            "reserialized",
            lineterm="",
        )
    )


def main() -> int:
    patches = sorted(OUTPUT_DIR.glob("*.pd"))
    if not patches:
        print(f"no .pd files in {OUTPUT_DIR}; run example.py first", file=sys.stderr)
        return 1

    failures = 0
    for path in patches:
        diff = check_roundtrip(path)
        if diff:
            print(f"FAIL round-trip {path.name}\n{diff}", file=sys.stderr)
            failures += 1
            continue
        if PD_BIN is None:
            print(f"  ok (round-trip) {path.name}")
            continue
        output = run_in_pd(str(path))
        if output:
            print(f"FAIL PureData rejected {path.name}\n{output}", file=sys.stderr)
            failures += 1
        else:
            print(f"  ok {path.name}")

    if PD_BIN is None:
        print("\nno PureData binary found; load checks skipped (set PD_BIN)")
    if failures:
        print(f"\n{failures} of {len(patches)} file(s) failed", file=sys.stderr)
        return 1
    print(f"\n{len(patches)} file(s) verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
