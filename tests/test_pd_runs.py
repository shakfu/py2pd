"""Drive generated patches with loadbang and check what PureData actually does.

Every other PureData test in this suite asks whether a patch *loads*. That is a
weaker property than it looks: a subpatch whose inlets are wired in reverse
loads in silence, because every connection index is valid and only the meaning
is wrong. The defect that prompted this module reached a released example and
survived the round-trip, field-value and load matrices; it took running the
patch to see it.

Each test here builds a patch that drives itself with ``loadbang``, wires
``print`` objects to the points of interest, and asserts on the console. Where
a test bangs one inlet and names the object that must answer, it is pinning a
contract PureData enforces and py2pd cannot check alone.

Skipped when no ``pd`` binary is found. Set ``PD_BIN`` to point at one.
"""

from pathlib import Path
import sys

import pytest

from py2pd import Patcher
from tests.pd_runner import PD_BIN, SKIP_REASON, run_in_pd

sys.path.insert(0, str(Path(__file__).parent / "examples"))

from example import (  # type: ignore[import-not-found]  # noqa: E402  # added to sys.path above
    envelope_subpatch,
)

pytestmark = pytest.mark.skipif(PD_BIN is None, reason=SKIP_REASON)


def run_patch(patch: Patcher, tmp_path, name: str) -> str:
    """Save *patch* and return the console output of running it."""
    target = tmp_path / name
    patch.save(str(target))
    return run_in_pd(str(target))


def assert_no_errors(console: str, patch: Patcher) -> None:
    errors = [line for line in console.splitlines() if line.startswith("error:")]
    assert not errors, f"PureData reported errors:\n{console}\n\n{patch}"


def labelled_inlet_subpatch(count: int) -> Patcher:
    """A subpatch whose n-th inlet prints ``IN<n>``, by creation order."""
    inner = Patcher()
    for i in range(count):
        inner.link(inner.add("inlet"), inner.add(f"print IN{i}"))
    return inner


class TestSubpatchInletOrder:
    """The n-th inlet created must be the n-th inlet of the parent object.

    PureData orders subpatch inlets by the x position of the inlet objects and
    breaks a tie in reverse file order, so this only holds because
    ``add_subpatch()`` spreads them. Banging one inlet and naming the object
    that must answer is the only way to see it.
    """

    @pytest.mark.parametrize("index", [0, 2, 4])
    def test_banging_inlet_reaches_the_matching_inlet_object(self, index, tmp_path):
        p = Patcher()
        env = p.add_subpatch("env", labelled_inlet_subpatch(5))
        p.link(p.add("loadbang"), env, inlet=index)
        console = run_patch(p, tmp_path, f"inlet{index}.pd")
        assert console == f"IN{index}: bang"

    def test_explicit_positions_keep_the_order_the_caller_laid_out(self, tmp_path):
        """Right-to-left placement means inlet 0 is the last one created."""
        inner = Patcher()
        count = 3
        for i in range(count):
            x = 200 - 70 * i
            inner.link(
                inner.add("inlet", x_pos=x, y_pos=25),
                inner.add(f"print IN{i}", x_pos=x, y_pos=60),
            )
        p = Patcher()
        env = p.add_subpatch("env", inner)
        p.link(p.add("loadbang"), env, inlet=0)
        assert run_patch(p, tmp_path, "explicit.pd") == f"IN{count - 1}: bang"

    def test_two_inlets_are_not_swapped(self, tmp_path):
        """The smallest case that a reverse ordering still gets wrong."""
        p = Patcher()
        env = p.add_subpatch("env", labelled_inlet_subpatch(2))
        p.link(p.add("loadbang"), env, inlet=0)
        assert run_patch(p, tmp_path, "two.pd") == "IN0: bang"


class TestSubpatchOutletOrder:
    """The n-th outlet created must be the n-th outlet of the parent object."""

    @pytest.mark.parametrize("index", [0, 2, 4])
    def test_inner_outlet_reaches_the_matching_parent_outlet(self, index, tmp_path):
        count = 5
        inner = Patcher()
        lb = inner.add("loadbang")
        outlets = [inner.add("outlet") for _ in range(count)]
        inner.link(lb, outlets[index])
        p = Patcher()
        env = p.add_subpatch("env", inner)
        for i in range(count):
            p.link(env, p.add(f"print OUT{i}"), outlet=i)
        console = run_patch(p, tmp_path, f"outlet{index}.pd")
        assert console == f"OUT{index}: bang"


class TestExamplePatchesRun:
    """The shipped examples must run, not merely load."""

    def test_envelope_runs_when_driven(self, tmp_path):
        """Set the four parameters, then trigger, exactly as a player would."""
        p = Patcher()
        env = p.add_subpatch("envelope", envelope_subpatch())
        # trigger fires its outlets right to left, so the parameters are set
        # before the leftmost outlet bangs the envelope.
        seq = p.add("t b b b b b")
        p.link(p.add("loadbang"), seq)
        for outlet, (inlet, value) in enumerate([(4, 200), (3, 0.6), (2, 150), (1, 10)]):
            msg = p.add_msg(str(value))
            p.link(seq, msg, outlet=outlet)
            p.link(msg, env, inlet=inlet)
        p.link(seq, env, outlet=4, inlet=0)
        p.link(env, p.add("dac~"))
        console = run_patch(p, tmp_path, "envelope_driven.pd")
        assert_no_errors(console, p)

    def test_trigger_inlet_does_not_error(self, tmp_path):
        """Banging the trigger alone was the reported failure."""
        p = Patcher()
        env = p.add_subpatch("envelope", envelope_subpatch())
        p.link(p.add("loadbang"), env, inlet=0)
        assert_no_errors(run_patch(p, tmp_path, "envelope_trigger.pd"), p)
