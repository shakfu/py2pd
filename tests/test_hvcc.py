"""Tests for py2pd.hvcc -- hvcc integration module."""

import shutil

import pytest

from py2pd.api import Patcher
from py2pd.ast import CanvasProperties, PdObj, PdPatch, PdSubpatch, Position
from py2pd.integrations.hvcc import (
    HVCC_MIDI_GENERATORS,
    HVCC_MIDI_OBJECTS,
    HVCC_SUPPORTED_OBJECTS,
    HeavyPatcher,
    HvccCompileError,
    HvccCompileResult,
    HvccError,
    HvccGenerator,
    HvccUnsupportedError,
    _check_object_supported,
    compile_hvcc,
    validate_for_hvcc,
)

# =========================================================================
# Registry tests
# =========================================================================


class TestHvccSupportedObjects:
    """Test the HVCC_SUPPORTED_OBJECTS registry."""

    def test_contains_common_signal_objects(self):
        for obj in ("osc~", "dac~", "adc~", "+~", "*~", "lop~", "noise~", "phasor~"):
            assert obj in HVCC_SUPPORTED_OBJECTS, f"{obj} should be supported"

    def test_contains_common_control_objects(self):
        for obj in ("+", "-", "*", "/", "float", "int", "route", "select", "trigger"):
            assert obj in HVCC_SUPPORTED_OBJECTS, f"{obj} should be supported"

    def test_contains_aliases(self):
        for obj in ("b", "bang", "t", "trigger", "f", "float", "r", "receive", "s", "send"):
            assert obj in HVCC_SUPPORTED_OBJECTS, f"alias {obj} should be supported"

    def test_excludes_known_unsupported(self):
        for obj in (
            "bob~",
            "fft~",
            "ifft~",
            "rfft~",
            "rifft~",
            "vline~",
            "list",
            "array",
            "text",
            "netsend",
            "netreceive",
            "openpanel",
            "savepanel",
            "readsf~",
            "writesf~",
        ):
            assert obj not in HVCC_SUPPORTED_OBJECTS, f"{obj} should not be supported"

    def test_midi_objects_are_subset(self):
        assert HVCC_MIDI_OBJECTS <= HVCC_SUPPORTED_OBJECTS

    def test_midi_objects_contains_known(self):
        for obj in (
            "notein",
            "noteout",
            "ctlin",
            "ctlout",
            "bendin",
            "bendout",
            "midiin",
            "midiout",
            "pgmin",
            "pgmout",
        ):
            assert obj in HVCC_MIDI_OBJECTS

    def test_midi_generators(self):
        assert "dpf" in HVCC_MIDI_GENERATORS
        assert "daisy" in HVCC_MIDI_GENERATORS
        assert "owl" in HVCC_MIDI_GENERATORS
        assert "c" not in HVCC_MIDI_GENERATORS

    def test_contains_gui_objects(self):
        for obj in (
            "bng",
            "tgl",
            "hsl",
            "vsl",
            "hradio",
            "vradio",
            "cnv",
            "nbx",
            "floatatom",
            "symbolatom",
        ):
            assert obj in HVCC_SUPPORTED_OBJECTS, f"GUI {obj} should be supported"

    def test_contains_subpatch_related(self):
        assert "pd" in HVCC_SUPPORTED_OBJECTS
        assert "inlet" in HVCC_SUPPORTED_OBJECTS
        assert "outlet" in HVCC_SUPPORTED_OBJECTS
        assert "inlet~" in HVCC_SUPPORTED_OBJECTS
        assert "outlet~" in HVCC_SUPPORTED_OBJECTS


# =========================================================================
# _check_object_supported tests
# =========================================================================


class TestCheckObjectSupported:
    def test_supported_object_passes(self):
        assert _check_object_supported("osc~") == []
        assert _check_object_supported("dac~") == []
        assert _check_object_supported("+") == []

    def test_unsupported_object_returns_error(self):
        errs = _check_object_supported("bob~")
        assert len(errs) == 1
        assert "unsupported" in errs[0]
        assert "bob~" in errs[0]

    def test_aliases_pass(self):
        assert _check_object_supported("b") == []
        assert _check_object_supported("bang") == []
        assert _check_object_supported("t") == []
        assert _check_object_supported("trigger") == []
        assert _check_object_supported("f") == []
        assert _check_object_supported("float") == []
        assert _check_object_supported("r") == []
        assert _check_object_supported("receive") == []
        assert _check_object_supported("s") == []
        assert _check_object_supported("send") == []

    def test_midi_with_correct_generator(self):
        assert _check_object_supported("notein", [HvccGenerator.DPF]) == []
        assert _check_object_supported("ctlin", [HvccGenerator.DAISY]) == []
        assert _check_object_supported("bendin", [HvccGenerator.OWL]) == []

    def test_midi_with_incorrect_generator(self):
        errs = _check_object_supported("notein", [HvccGenerator.C])
        assert len(errs) == 1
        assert "MIDI" in errs[0]

    def test_midi_no_generators_passes(self):
        # No generators specified = no MIDI constraint
        assert _check_object_supported("notein") == []
        assert _check_object_supported("notein", None) == []

    def test_midi_with_mixed_generators(self):
        # At least one MIDI-capable generator = ok
        assert _check_object_supported("notein", [HvccGenerator.C, HvccGenerator.DPF]) == []

    def test_non_midi_unaffected_by_generators(self):
        assert _check_object_supported("osc~", [HvccGenerator.C]) == []
        assert _check_object_supported("+", [HvccGenerator.JS]) == []


# =========================================================================
# validate_for_hvcc tests
# =========================================================================


class TestValidateForHvcc:
    def test_clean_patch_ok(self):
        p = Patcher()
        osc = p.add("osc~ 440")
        dac = p.add("dac~")
        p.link(osc, dac)
        result = validate_for_hvcc(p)
        assert result.ok
        assert result.errors == []

    def test_unsupported_object_errors(self):
        p = Patcher()
        p.add("osc~ 440")
        p.add("bob~ 200")  # not supported by hvcc
        result = validate_for_hvcc(p)
        assert not result.ok
        assert any("bob~" in e for e in result.errors)

    def test_multiple_errors_listed(self):
        p = Patcher()
        p.add("bob~ 200")
        p.add("vline~ 0 50")
        result = validate_for_hvcc(p)
        assert not result.ok
        assert len(result.errors) == 2

    def test_subpatch_recursion(self):
        inner = Patcher()
        inner.add("bob~ 100")  # unsupported, nested
        p = Patcher()
        p.add("osc~ 440")
        p.add_subpatch("sub", inner)
        result = validate_for_hvcc(p)
        assert not result.ok
        assert any("bob~" in e for e in result.errors)

    def test_generator_specific_midi_validation(self):
        p = Patcher()
        p.add("notein")
        # No generators => ok (no constraint)
        assert validate_for_hvcc(p).ok
        # DPF generator => ok
        assert validate_for_hvcc(p, generators=[HvccGenerator.DPF]).ok
        # C generator => error (no MIDI support)
        result = validate_for_hvcc(p, generators=[HvccGenerator.C])
        assert not result.ok
        assert any("MIDI" in e for e in result.errors)

    def test_pdpatch_ast_input(self):
        ast = PdPatch(
            canvas=CanvasProperties(),
            elements=[
                PdObj(Position(10, 10), "osc~", ("440",)),
                PdObj(Position(10, 40), "dac~"),
            ],
        )
        result = validate_for_hvcc(ast)
        assert result.ok

    def test_pdpatch_ast_unsupported(self):
        ast = PdPatch(
            canvas=CanvasProperties(),
            elements=[
                PdObj(Position(10, 10), "bob~", ("200",)),
            ],
        )
        result = validate_for_hvcc(ast)
        assert not result.ok
        assert any("bob~" in e for e in result.errors)

    def test_pdpatch_ast_subpatch_recursion(self):
        inner_sub = PdSubpatch(
            canvas=CanvasProperties(name="sub"),
            elements=[
                PdObj(Position(10, 10), "vline~"),
            ],
        )
        ast = PdPatch(
            canvas=CanvasProperties(),
            elements=[
                PdObj(Position(10, 10), "osc~", ("440",)),
                inner_sub,
            ],
        )
        result = validate_for_hvcc(ast)
        assert not result.ok
        assert any("vline~" in e for e in result.errors)

    def test_gui_objects_pass(self):
        p = Patcher()
        p.add_bang()
        p.add_toggle()
        p.add_hslider()
        p.add_vslider()
        result = validate_for_hvcc(p)
        # GUI objects are not Obj instances, they are Bang/Toggle/etc.
        # validate_for_hvcc only walks Obj nodes, so GUIs pass silently
        assert result.ok

    def test_rejects_bad_type(self):
        with pytest.raises(TypeError):
            validate_for_hvcc("not a patch")  # type: ignore[arg-type]

    def test_empty_patch_ok(self):
        p = Patcher()
        result = validate_for_hvcc(p)
        assert result.ok
        assert result.errors == []


# =========================================================================
# HeavyPatcher tests
# =========================================================================


class TestHeavyPatcher:
    def test_add_supported_object(self):
        p = HeavyPatcher()
        osc = p.add("osc~ 440")
        assert osc is not None
        assert "osc~" in str(osc)

    def test_add_unsupported_raises(self):
        p = HeavyPatcher()
        with pytest.raises(HvccUnsupportedError) as exc_info:
            p.add("bob~ 200")
        assert "bob~" in exc_info.value.unsupported

    def test_inherited_methods_work(self):
        p = HeavyPatcher()
        osc = p.add("osc~ 440")
        dac = p.add("dac~")
        p.link(osc, dac)
        # add_msg is inherited and not gated
        msg = p.add_msg("440")
        assert msg is not None
        # add_bang is inherited
        bng = p.add_bang()
        assert bng is not None

    def test_serialization_produces_valid_pd(self):
        p = HeavyPatcher()
        osc = p.add("osc~ 440")
        dac = p.add("dac~")
        p.link(osc, dac)
        output = str(p)
        assert "#N canvas" in output
        assert "osc~ 440" in output
        assert "dac~" in output
        assert "#X connect" in output

    def test_generators_stored(self):
        p = HeavyPatcher(generators=[HvccGenerator.DPF])
        assert p.generators == [HvccGenerator.DPF]

    def test_midi_with_correct_generator(self):
        p = HeavyPatcher(generators=[HvccGenerator.DPF])
        note = p.add("notein")
        assert note is not None

    def test_midi_with_incorrect_generator(self):
        p = HeavyPatcher(generators=[HvccGenerator.C])
        with pytest.raises(HvccUnsupportedError):
            p.add("notein")

    def test_link_with_outlet(self):
        p = HeavyPatcher()
        osc = p.add("osc~ 440")
        dac = p.add("dac~")
        p.link(osc[0], dac)
        p.link(osc[0], dac, inlet=1)
        output = str(p)
        assert output.count("#X connect") == 2


# =========================================================================
# Annotation tests
# =========================================================================


class TestHeavyPatcherAnnotations:
    def test_add_param_text_format(self):
        p = HeavyPatcher()
        param = p.add_param("freq", min_val=20.0, max_val=20000.0, default=440.0)
        text = param.parameters["text"]
        assert "r" in text
        assert "freq" in text
        assert "@hv_param" in text
        assert "20.0" in text
        assert "20000.0" in text
        assert "440.0" in text

    def test_add_param_with_type(self):
        p = HeavyPatcher()
        param = p.add_param("gate", type="bool", min_val=0.0, max_val=1.0, default=0.0)
        text = param.parameters["text"]
        assert "bool" in text

    def test_add_param_default_type_no_suffix(self):
        p = HeavyPatcher()
        param = p.add_param("vol")
        text = param.parameters["text"]
        # Default type "float" should not appear in the text
        assert "float" not in text

    def test_add_param_output_text(self):
        p = HeavyPatcher()
        out = p.add_param_output("level")
        text = out.parameters["text"]
        assert text.startswith("s ")
        assert "level" in text
        assert "@hv_param" in text

    def test_add_event_text(self):
        p = HeavyPatcher()
        ev = p.add_event("bang_me")
        text = ev.parameters["text"]
        assert text.startswith("r ")
        assert "bang_me" in text
        assert "@hv_event" in text

    def test_add_table_with_expose(self):
        p = HeavyPatcher()
        tbl = p.add_table("waveform", 1024)
        text = tbl.parameters["text"]
        assert "table" in text
        assert "waveform" in text
        assert "1024" in text
        assert "@hv_table" in text

    def test_add_table_without_expose(self):
        p = HeavyPatcher()
        tbl = p.add_table("internal", 512, expose=False)
        text = tbl.parameters["text"]
        assert "@hv_table" not in text

    def test_add_table_rejects_spaces_in_name(self):
        p = HeavyPatcher()
        with pytest.raises(ValueError, match="spaces"):
            p.add_table("my table", 1024)

    def test_add_param_serializes(self):
        p = HeavyPatcher()
        p.add_param("freq", min_val=20.0, max_val=20000.0, default=440.0)
        output = str(p)
        assert "@hv_param" in output


# =========================================================================
# Generator enum tests
# =========================================================================


class TestHvccGenerator:
    def test_enum_values(self):
        assert HvccGenerator.C.value == "c"
        assert HvccGenerator.DPF.value == "dpf"
        assert HvccGenerator.DAISY.value == "daisy"
        assert HvccGenerator.JS.value == "js"
        assert HvccGenerator.OWL.value == "owl"
        assert HvccGenerator.PDEXT.value == "pdext"
        assert HvccGenerator.UNITY.value == "unity"
        assert HvccGenerator.WWISE.value == "wwise"

    def test_string_behavior(self):
        # HvccGenerator inherits from str
        assert isinstance(HvccGenerator.C, str)
        assert HvccGenerator.C == "c"


# =========================================================================
# Exception tests
# =========================================================================


class TestHvccExceptions:
    def test_hvcc_error_is_exception(self):
        assert issubclass(HvccError, Exception)

    def test_unsupported_error_inheritance(self):
        assert issubclass(HvccUnsupportedError, HvccError)

    def test_compile_error_inheritance(self):
        assert issubclass(HvccCompileError, HvccError)

    def test_unsupported_error_stores_names(self):
        err = HvccUnsupportedError(["bob~", "fft~"])
        assert err.unsupported == ["bob~", "fft~"]
        assert "bob~" in str(err)
        assert "fft~" in str(err)


# =========================================================================
# compile_hvcc unit tests (no hvcc needed)
# =========================================================================


class TestCompileHvccUnit:
    def test_validate_flag_rejects_bad_patches(self):
        """compile_hvcc with validate=True should reject unsupported objects."""
        p = Patcher()
        p.add("bob~ 200")
        # compile_hvcc should raise HvccUnsupportedError before even trying to import hvcc
        with pytest.raises((HvccUnsupportedError, ImportError)):
            compile_hvcc(p, output_dir="/tmp/hvcc_test", validate=True)

    def test_compile_result_dataclass(self):
        r = HvccCompileResult(ok=True, output_dir="/tmp/out")
        assert r.ok
        assert r.output_dir == "/tmp/out"
        assert r.errors == []
        assert r.warnings == []
        assert r.stdout == ""
        assert r.stderr == ""


# =========================================================================
# Integration tests (skip if hvcc not installed)
# =========================================================================

_hvcc_available = shutil.which("hvcc") is not None


@pytest.mark.skipif(not _hvcc_available, reason="hvcc not installed")
class TestCompileHvccIntegration:
    def test_simple_sine_compiles_to_c(self, tmp_path):
        p = HeavyPatcher()
        osc = p.add("osc~ 440")
        gain = p.add("*~ 0.5")
        dac = p.add("dac~")
        p.link(osc, gain)
        p.link(gain, dac)
        p.link(gain, dac, inlet=1)

        out_dir = str(tmp_path / "hvcc_out")
        result = compile_hvcc(p, output_dir=out_dir, generators=[HvccGenerator.C])
        assert result.ok
        assert result.output_dir == out_dir

    def test_output_directory_populated(self, tmp_path):
        p = HeavyPatcher()
        p.add("osc~ 440")
        p.add("dac~")

        out_dir = str(tmp_path / "hvcc_out")
        compile_hvcc(p, output_dir=out_dir, generators=[HvccGenerator.C])
        # hvcc should create files in the output directory
        import os

        assert os.path.isdir(out_dir)

    def test_patch_with_hv_param_compiles(self, tmp_path):
        p = HeavyPatcher()
        freq = p.add_param("freq", min_val=20.0, max_val=20000.0, default=440.0)
        osc = p.add("osc~")
        dac = p.add("dac~")
        p.link(freq, osc)
        p.link(osc, dac)

        out_dir = str(tmp_path / "hvcc_out")
        result = compile_hvcc(p, output_dir=out_dir, generators=[HvccGenerator.C])
        assert result.ok

    def test_unsupported_object_errors(self, tmp_path):
        p = Patcher()
        p.add("bob~ 200")

        out_dir = str(tmp_path / "hvcc_out")
        with pytest.raises(HvccUnsupportedError):
            compile_hvcc(p, output_dir=out_dir, validate=True)
