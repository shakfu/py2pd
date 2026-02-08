"""Tests for py2pd.validate module.

Unit tests run without cypd.  Integration tests are skipped if cypd is
not installed.
"""

import pytest

from py2pd.api import Patcher
from py2pd.ast import CanvasProperties, PdPatch
from py2pd.integrations.cypd import (
    ValidationResult,
    _classify_messages,
    _PrintAccumulator,
    _serialize_input,
)

# =========================================================================
# Unit tests -- no cypd required
# =========================================================================


class TestPrintAccumulator:
    """Test _PrintAccumulator line-splitting logic."""

    def test_single_complete_line(self):
        acc = _PrintAccumulator()
        acc("hello world\n")
        assert acc.lines == ["hello world"]

    def test_fragments_to_line(self):
        acc = _PrintAccumulator()
        acc("hello")
        acc(" ")
        acc("world\n")
        assert acc.lines == ["hello world"]

    def test_multi_line(self):
        acc = _PrintAccumulator()
        acc("line1\nline2\n")
        assert acc.lines == ["line1", "line2"]

    def test_partial_then_complete(self):
        acc = _PrintAccumulator()
        acc("partial")
        assert acc.lines == []
        acc(" end\n")
        assert acc.lines == ["partial end"]

    def test_flush_partial(self):
        acc = _PrintAccumulator()
        acc("no newline")
        acc.flush()
        assert acc.lines == ["no newline"]

    def test_flush_empty(self):
        acc = _PrintAccumulator()
        acc.flush()
        assert acc.lines == []

    def test_flush_whitespace_only(self):
        acc = _PrintAccumulator()
        acc("   ")
        acc.flush()
        assert acc.lines == []

    def test_empty_lines_skipped(self):
        acc = _PrintAccumulator()
        acc("\n\n")
        assert acc.lines == []

    def test_mixed_fragments_and_newlines(self):
        acc = _PrintAccumulator()
        acc("a\nb")
        acc("c\nd\n")
        assert acc.lines == ["a", "bc", "d"]


class TestClassifyMessages:
    """Test _classify_messages error/warning detection."""

    def test_error_couldnt_create(self):
        lines = ["... couldn't create"]
        errors, warnings = _classify_messages(lines)
        assert len(errors) == 1
        assert len(warnings) == 0

    def test_error_no_such_object(self):
        lines = ["bogus_obj: no such object"]
        errors, warnings = _classify_messages(lines)
        assert len(errors) == 1

    def test_error_generic(self):
        lines = ["error: something went wrong"]
        errors, warnings = _classify_messages(lines)
        assert len(errors) == 1

    def test_warning_pattern(self):
        lines = ["warning: old syntax"]
        errors, warnings = _classify_messages(lines)
        assert len(errors) == 0
        assert len(warnings) == 1

    def test_deprecated_pattern(self):
        lines = ["deprecated feature used"]
        errors, warnings = _classify_messages(lines)
        assert len(errors) == 0
        assert len(warnings) == 1

    def test_clean_log(self):
        lines = ["print: hello", "some info"]
        errors, warnings = _classify_messages(lines)
        assert len(errors) == 0
        assert len(warnings) == 0

    def test_mixed(self):
        lines = [
            "print: ok",
            "error: bad thing",
            "warning: careful",
            "info line",
        ]
        errors, warnings = _classify_messages(lines)
        assert len(errors) == 1
        assert len(warnings) == 1

    def test_case_insensitive(self):
        lines = ["ERROR: caps", "Warning: mixed"]
        errors, warnings = _classify_messages(lines)
        assert len(errors) == 1
        assert len(warnings) == 1

    def test_empty(self):
        errors, warnings = _classify_messages([])
        assert errors == []
        assert warnings == []


class TestSerializePatch:
    """Test _serialize_input with different input types."""

    def test_patcher_input(self):
        p = Patcher()
        p.add("osc~ 440")
        result = _serialize_input(p)
        assert "#N canvas" in result
        assert "osc~ 440" in result

    def test_pdpatch_input(self):
        ast = PdPatch(canvas=CanvasProperties(), elements=[])
        result = _serialize_input(ast)
        assert "#N canvas" in result

    def test_invalid_type(self):
        with pytest.raises(TypeError, match="Expected Patcher or PdPatch"):
            _serialize_input("not a patch")

    def test_invalid_type_dict(self):
        with pytest.raises(TypeError):
            _serialize_input({"key": "value"})


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_defaults(self):
        r = ValidationResult(ok=True)
        assert r.ok is True
        assert r.errors == []
        assert r.warnings == []
        assert r.log == []

    def test_with_errors(self):
        r = ValidationResult(
            ok=False,
            errors=["bad object"],
            warnings=["old syntax"],
            log=["line1", "line2"],
        )
        assert r.ok is False
        assert len(r.errors) == 1
        assert len(r.warnings) == 1
        assert len(r.log) == 2


class TestImportErrorWithoutCypd:
    """Test that validate_patch raises ImportError when cypd is missing."""

    def test_importerror_without_cypd(self, monkeypatch):
        import py2pd.integrations.cypd as mod

        # Reset the init flag so _ensure_libpd tries to import again
        monkeypatch.setattr(mod, "_libpd_initialized", False)

        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "cypd":
                raise ImportError("no cypd")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        from py2pd.integrations.cypd import validate_patch

        p = Patcher()
        p.add("osc~ 440")
        with pytest.raises(ImportError, match="cypd is required"):
            validate_patch(p)


# =========================================================================
# Integration tests -- require cypd
# =========================================================================

_has_cypd = pytest.importorskip is not None  # just a truthy sentinel
try:
    import cypd as _cypd  # noqa: F401

    _has_cypd = True
except ImportError:
    _has_cypd = False

requires_cypd = pytest.mark.skipif(not _has_cypd, reason="cypd not installed")


@requires_cypd
class TestValidatePatchIntegration:
    """Integration tests that exercise real libpd loading."""

    def test_valid_patch(self):
        from py2pd.integrations.cypd import validate_patch

        p = Patcher()
        osc = p.add("osc~ 440")
        dac = p.add("dac~")
        p.link(osc, dac)
        p.link(osc, dac, inlet=1)
        result = validate_patch(p)
        assert result.ok is True
        assert result.errors == []

    def test_missing_external(self):
        from py2pd.integrations.cypd import validate_patch

        p = Patcher()
        p.add("__nonexistent_bogus_object_xyz__")
        result = validate_patch(p)
        assert result.ok is False
        assert any("__nonexistent_bogus_object_xyz__" in e for e in result.errors)

    def test_ast_input(self):
        from py2pd.ast import from_builder
        from py2pd.integrations.cypd import validate_patch

        p = Patcher()
        osc = p.add("osc~ 440")
        dac = p.add("dac~")
        p.link(osc, dac)
        ast = from_builder(p)
        result = validate_patch(ast)
        assert result.ok is True

    def test_check_receivers_found(self):
        from py2pd.integrations.cypd import validate_patch

        p = Patcher()
        p.add("r mytestreceiver")
        result = validate_patch(p, check_receivers=["mytestreceiver"])
        assert "receiver not found: mytestreceiver" not in result.errors

    def test_check_receivers_missing(self):
        from py2pd.integrations.cypd import validate_patch

        p = Patcher()
        p.add("osc~ 440")
        result = validate_patch(p, check_receivers=["__totally_missing_receiver__"])
        assert any("__totally_missing_receiver__" in e for e in result.errors)
        assert result.ok is False

    def test_search_paths(self, tmp_path):
        from py2pd.integrations.cypd import validate_patch

        abs_file = tmp_path / "myabs.pd"
        abs_file.write_text(
            "#N canvas 0 50 450 300 10;\n#X obj 10 10 inlet;\n#X obj 10 40 outlet;\n"
        )
        p = Patcher()
        p.add("myabs")
        result = validate_patch(
            p,
            search_paths=[str(tmp_path)],
            include_default_paths=False,
        )
        assert result.ok is True

    def test_log_populated(self):
        from py2pd.integrations.cypd import validate_patch

        p = Patcher()
        p.add("print hello")
        result = validate_patch(p)
        assert isinstance(result.log, list)
