"""Integration tests for example.py functions."""

from pathlib import Path
import sys

# Add the examples directory to the path so we can import example.py
sys.path.insert(0, str(Path(__file__).parent / "examples"))

from example import (
    auto_layout_demo,
    grid_layout_demo,
    gui_elements_demo,
    poly_voice,
    simple_synth,
    synth_with_subpatch,
)


class TestExampleSimpleSynth:
    """Tests for simple_synth example."""

    def test_builds_patch(self):
        patch = simple_synth()
        assert len(patch.nodes) == 3
        assert len(patch.connections) == 3

    def test_saves_and_validates(self, tmp_path):
        patch = simple_synth()
        filepath = tmp_path / "simple_synth.pd"
        patch.save(str(filepath))
        content = filepath.read_text()
        assert "#N canvas" in content
        assert "osc~ 440" in content
        assert "dac~" in content
        assert content.count("#X connect") == 3


class TestExampleGUIElements:
    """Tests for gui_elements_demo example."""

    def test_builds_patch(self):
        patch = gui_elements_demo()
        assert len(patch.nodes) == 11

    def test_saves_and_validates(self, tmp_path):
        patch = gui_elements_demo()
        filepath = tmp_path / "gui_demo.pd"
        patch.save(str(filepath))
        content = filepath.read_text()
        assert "#N canvas" in content
        assert "bng" in content
        assert "tgl" in content
        assert "nbx" in content
        assert "vsl" in content
        assert "hsl" in content
        assert "vradio" in content
        assert "hradio" in content
        assert "symbolatom" in content
        assert "floatatom" in content
        assert "cnv" in content
        assert "vu" in content


class TestExampleSynthWithSubpatch:
    """Tests for synth_with_subpatch example."""

    def test_builds_patch(self):
        patch = synth_with_subpatch()
        assert len(patch.nodes) > 5
        assert len(patch.connections) > 5

    def test_saves_and_validates(self, tmp_path):
        patch = synth_with_subpatch()
        filepath = tmp_path / "synth_envelope.pd"
        patch.save(str(filepath))
        content = filepath.read_text()
        assert "#N canvas" in content
        assert "pd envelope" in content
        assert "inlet" in content
        assert "outlet" in content
        assert "vline~" in content


class TestExampleGridLayout:
    """Tests for grid_layout_demo example."""

    def test_builds_patch(self):
        patch = grid_layout_demo()
        assert len(patch.nodes) == 16
        assert len(patch.connections) == 15

    def test_saves_and_validates(self, tmp_path):
        patch = grid_layout_demo()
        filepath = tmp_path / "grid_demo.pd"
        patch.save(str(filepath))
        content = filepath.read_text()
        assert "#N canvas" in content
        assert content.count("#X connect") == 15


class TestExampleAutoLayout:
    """Tests for auto_layout_demo example."""

    def test_builds_patch(self):
        patch = auto_layout_demo()
        assert len(patch.nodes) == 6
        assert len(patch.connections) == 6

    def test_saves_and_validates(self, tmp_path):
        patch = auto_layout_demo()
        filepath = tmp_path / "auto_layout.pd"
        patch.save(str(filepath))
        content = filepath.read_text()
        assert "#N canvas" in content
        assert "osc~ 440" in content
        assert "osc~ 550" in content

    def test_layout_applied(self):
        patch = auto_layout_demo()
        # After auto_layout, sources should be above sinks
        # osc nodes should be above gain nodes which should be above mixer/dac
        osc_y = min(n.position[1] for n in patch.nodes if "osc~" in str(n))
        dac_y = max(n.position[1] for n in patch.nodes if "dac~" in str(n))
        assert osc_y < dac_y


class TestExamplePolyVoice:
    """Tests for poly_voice example."""

    def test_builds_patch(self):
        patch = poly_voice()
        assert len(patch.nodes) > 10
        assert len(patch.connections) > 10

    def test_saves_and_validates(self, tmp_path):
        patch = poly_voice()
        filepath = tmp_path / "poly_voice.pd"
        patch.save(str(filepath))
        content = filepath.read_text()
        assert "#N canvas" in content
        assert "osc~" in content
        assert "lop~" in content
        assert "vline~" in content
        assert "outlet~" in content
