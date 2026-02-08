"""Tests for py2pd.discover module."""

import os
import tempfile

import pytest

from py2pd import default_search_paths, discover_externals, extract_declare_paths, parse
from py2pd.discover import _platform_key


class TestDefaultSearchPaths:
    """Tests for default_search_paths function."""

    def test_returns_list(self):
        result = default_search_paths()
        assert isinstance(result, list)
        for p in result:
            assert isinstance(p, str)

    def test_only_existing(self):
        result = default_search_paths()
        for p in result:
            assert os.path.isdir(p), f"{p} does not exist"


class TestDiscoverExternals:
    """Tests for discover_externals function."""

    def test_discover_pd_abstractions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .pd file with inlet and outlet
            pd_content = "#N canvas 0 50 450 300 10;\n#X obj 50 50 inlet;\n#X obj 50 100 outlet;\n"
            with open(os.path.join(tmpdir, "mysynth.pd"), "w") as f:
                f.write(pd_content)

            registry = discover_externals([tmpdir], include_defaults=False)
            assert "mysynth" in registry
            assert registry["mysynth"] == (1, 1)

    def test_discover_pd_multiple_io(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pd_content = (
                "#N canvas 0 50 450 300 10;\n"
                "#X obj 50 50 inlet;\n"
                "#X obj 50 80 inlet~;\n"
                "#X obj 50 100 outlet;\n"
                "#X obj 50 130 outlet;\n"
                "#X obj 50 160 outlet~;\n"
            )
            with open(os.path.join(tmpdir, "multi.pd"), "w") as f:
                f.write(pd_content)

            registry = discover_externals([tmpdir], include_defaults=False)
            assert registry["multi"] == (2, 3)

    def test_discover_binary_externals(self):
        platform = _platform_key()
        from py2pd.discover import _EXTERNAL_EXTENSIONS

        exts = _EXTERNAL_EXTENSIONS.get(platform, ())
        if not exts:
            pytest.skip(f"No binary extensions defined for platform {platform}")

        ext = exts[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake binary external
            with open(os.path.join(tmpdir, f"reverb{ext}"), "w") as f:
                f.write("")

            registry = discover_externals([tmpdir], include_defaults=False)
            assert "reverb" in registry
            assert registry["reverb"] == (None, None)

    def test_first_found_wins(self):
        with tempfile.TemporaryDirectory() as dir1, tempfile.TemporaryDirectory() as dir2:
            # Create same-named .pd file in both dirs with different IO
            pd1 = "#N canvas 0 50 450 300 10;\n#X obj 50 50 inlet;\n#X obj 50 100 outlet;\n"
            pd2 = (
                "#N canvas 0 50 450 300 10;\n"
                "#X obj 50 50 inlet;\n"
                "#X obj 50 80 inlet;\n"
                "#X obj 50 100 outlet;\n"
            )
            with open(os.path.join(dir1, "dupe.pd"), "w") as f:
                f.write(pd1)
            with open(os.path.join(dir2, "dupe.pd"), "w") as f:
                f.write(pd2)

            registry = discover_externals([dir1, dir2], include_defaults=False)
            assert registry["dupe"] == (1, 1)  # first dir wins

    def test_empty_paths(self):
        registry = discover_externals([], include_defaults=False)
        assert registry == {}

    def test_include_defaults_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pd_content = "#N canvas 0 50 450 300 10;\n#X obj 50 50 inlet;\n"
            with open(os.path.join(tmpdir, "test.pd"), "w") as f:
                f.write(pd_content)

            registry = discover_externals([tmpdir], include_defaults=False)
            # Only the explicitly provided path should be scanned
            assert "test" in registry

    def test_mixed(self):
        platform = _platform_key()
        from py2pd.discover import _EXTERNAL_EXTENSIONS

        exts = _EXTERNAL_EXTENSIONS.get(platform, ())
        if not exts:
            pytest.skip(f"No binary extensions for platform {platform}")

        ext = exts[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            # Abstraction
            pd_content = "#N canvas 0 50 450 300 10;\n#X obj 50 50 inlet;\n#X obj 50 100 outlet;\n"
            with open(os.path.join(tmpdir, "abstraction.pd"), "w") as f:
                f.write(pd_content)
            # Binary
            with open(os.path.join(tmpdir, f"binary{ext}"), "w") as f:
                f.write("")

            registry = discover_externals([tmpdir], include_defaults=False)
            assert "abstraction" in registry
            assert registry["abstraction"] == (1, 1)
            assert "binary" in registry
            assert registry["binary"] == (None, None)

    def test_nonexistent_path_ignored(self):
        registry = discover_externals(["/nonexistent/path/abc123"], include_defaults=False)
        assert registry == {}

    def test_no_args_uses_defaults(self):
        # Calling with no arguments should not raise
        registry = discover_externals()
        assert isinstance(registry, dict)


class TestExtractDeclarePaths:
    """Tests for extract_declare_paths function."""

    def test_extract_paths(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#X declare -path /externals -path /libs;\n"
            "#X obj 50 50 osc~ 440;"
        )
        patch = parse(content)
        paths = extract_declare_paths(patch)
        assert paths == ["/externals", "/libs"]

    def test_extract_empty(self):
        content = "#N canvas 0 50 1000 600 10;\n#X obj 50 50 osc~ 440;"
        patch = parse(content)
        paths = extract_declare_paths(patch)
        assert paths == []

    def test_extract_from_subpatch(self):
        content = (
            "#N canvas 0 50 1000 600 10;\n"
            "#N canvas 0 0 300 200 sub 0;\n"
            "#X declare -path /inner;\n"
            "#X obj 50 50 inlet;\n"
            "#X restore 100 100 pd sub;\n"
            "#X declare -path /outer;"
        )
        patch = parse(content)
        paths = extract_declare_paths(patch)
        assert "/inner" in paths
        assert "/outer" in paths
        # Inner declare comes first (depth-first)
        assert paths.index("/inner") < paths.index("/outer")

    def test_extract_multiple_declares(self):
        content = "#N canvas 0 50 1000 600 10;\n#X declare -path /a;\n#X declare -path /b -path /c;"
        patch = parse(content)
        paths = extract_declare_paths(patch)
        assert paths == ["/a", "/b", "/c"]
