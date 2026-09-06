"""Locate a PureData binary and run patches through it.

Shared by the load tests (does PureData accept these bytes?), the run tests
(does the patch behave when something drives it?) and
``tests/examples/check_output.py``.

Skipped everywhere when no ``pd`` binary is found. Set ``PD_BIN`` to point at
one.
"""

import glob
import os
import shutil
import subprocess
from typing import Optional

_CANDIDATE_GLOBS = (
    "/Applications/Pd*.app/Contents/Resources/bin/pd",
    "/Applications/*/Pd*.app/Contents/Resources/bin/pd",
)


def _find_pd() -> Optional[str]:
    override = os.environ.get("PD_BIN")
    if override:
        return override if os.path.isfile(override) else None
    found = shutil.which("pd")
    if found:
        return found
    for pattern in _CANDIDATE_GLOBS:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    return None


PD_BIN = _find_pd()

SKIP_REASON = "no PureData binary found; set PD_BIN to run these"


def run_in_pd(path: str) -> str:
    """Open *path* in PureData and return whatever it wrote to the console.

    PureData fires ``loadbang`` before processing the quit message, so a patch
    driven by one has already run by the time this returns.
    """
    assert PD_BIN is not None
    proc = subprocess.run(
        [
            PD_BIN,
            "-nogui",
            "-noaudio",
            "-stderr",
            "-open",
            os.path.basename(path),
            "-send",
            "pd quit",
        ],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(path),
        timeout=60,
    )
    return (proc.stdout + proc.stderr).strip()
