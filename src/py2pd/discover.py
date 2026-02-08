"""Externals discovery for PureData.

Scans filesystem paths for PureData externals (compiled binaries and
abstraction .pd files) and returns a registry mapping names to I/O counts.

Supports platform-aware default search paths for macOS, Linux, and Windows.
"""

import glob as _glob
import os
import sys
from typing import Dict, List, Optional, Tuple

from .api import _infer_abstraction_io
from .ast import PdDeclare, PdPatch, PdSubpatch

# Maps sys.platform prefix to recognized binary extensions for externals
_EXTERNAL_EXTENSIONS = {
    "darwin": (".pd_darwin", ".d_fat", ".d_amd64", ".d_arm64"),
    "linux": (".pd_linux", ".l_amd64", ".l_arm64", ".l_arm"),
    "win32": (".dll", ".m_amd64", ".m_i386"),
}

ExternalsRegistry = Dict[str, Tuple[Optional[int], Optional[int]]]


def _platform_key() -> str:
    """Return the platform key for the current system."""
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def default_search_paths() -> List[str]:
    """Return platform-appropriate PureData external search paths that exist on disk.

    Returns
    -------
    list of str
        Existing directory paths where PureData externals may be found.
    """
    candidates: List[str] = []
    platform = _platform_key()

    if platform == "darwin":
        home = os.path.expanduser("~")
        candidates.extend(
            [
                os.path.join(home, "Library", "Pd"),
                os.path.join(home, "Library", "Pd", "externals"),
                "/usr/local/lib/pd/extra",
            ]
        )
        # Look for Pd*.app bundles under /Applications
        for app in _glob.glob("/Applications/Pd*.app"):
            extra = os.path.join(app, "Contents", "Resources", "extra")
            candidates.append(extra)

    elif platform == "linux":
        home = os.path.expanduser("~")
        candidates.extend(
            [
                os.path.join(home, ".local", "lib", "pd", "extra"),
                "/usr/lib/pd/extra",
                "/usr/local/lib/pd/extra",
            ]
        )

    elif platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            candidates.append(os.path.join(appdata, "Pd", "extra"))
        candidates.append(os.path.join("C:\\", "Program Files", "Pd", "extra"))

    return [p for p in candidates if os.path.isdir(p)]


def discover_externals(
    search_paths: Optional[List[str]] = None,
    *,
    include_defaults: bool = True,
) -> ExternalsRegistry:
    """Scan filesystem paths for PureData externals.

    Discovers both .pd abstraction files (with inferred I/O counts) and
    compiled binary externals (registered with unknown I/O counts).

    Parameters
    ----------
    search_paths : list of str, optional
        Explicit directories to scan. Searched before defaults.
    include_defaults : bool
        Whether to also scan platform default paths (default True).

    Returns
    -------
    ExternalsRegistry
        Mapping of external name to (num_inlets, num_outlets).
        Binary externals have (None, None) since I/O cannot be inferred.
        First-found wins when the same name appears in multiple paths.
    """
    paths: List[str] = []
    if search_paths:
        paths.extend(search_paths)
    if include_defaults:
        paths.extend(default_search_paths())

    platform = _platform_key()
    binary_exts = _EXTERNAL_EXTENSIONS.get(platform, ())

    registry: ExternalsRegistry = {}

    for directory in paths:
        if not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except OSError:
            continue

        for entry in entries:
            full_path = os.path.join(directory, entry)
            if not os.path.isfile(full_path):
                continue

            # Check .pd abstractions
            if entry.endswith(".pd"):
                name = entry[:-3]
                if name and name not in registry:
                    try:
                        inlets, outlets = _infer_abstraction_io(full_path)
                        registry[name] = (inlets, outlets)
                    except OSError:
                        continue
                continue

            # Check binary externals
            for ext in binary_exts:
                if entry.endswith(ext):
                    name = entry[: -len(ext)]
                    if name and name not in registry:
                        registry[name] = (None, None)
                    break

    return registry


def extract_declare_paths(patch: PdPatch) -> List[str]:
    """Extract all -path values from #X declare statements in a patch.

    Walks the patch elements and recursively into subpatches.

    Parameters
    ----------
    patch : PdPatch
        A parsed PureData patch.

    Returns
    -------
    list of str
        All declared paths in the order encountered.
    """
    result: List[str] = []
    _collect_declare_paths(patch.elements, result)
    return result


def _collect_declare_paths(elements: list, out: List[str]) -> None:
    """Recursively collect declare paths from elements."""
    for elem in elements:
        if isinstance(elem, PdDeclare):
            out.extend(elem.paths)
        elif isinstance(elem, PdSubpatch):
            _collect_declare_paths(elem.elements, out)
