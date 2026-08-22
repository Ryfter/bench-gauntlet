"""The overlay's state logic, kept separate from its window.

The GUI is a thin shell; this is the part that decides what the light means, so
this is the part that gets tested. Yellow is the state worth building the whole
thing for: a model resident in VRAM with nothing running is power being spent
for no reason, and it is invisible without an indicator.
"""
from __future__ import annotations

import os

from gauntlet.overlay import IN_USE, FREE, IDLE, indicator_state
from gauntlet.runstatus import RunStatus


def _running(**kw) -> RunStatus:
    """A marker for a genuinely live process -- our own. `is_alive` really does
    check the OS, so a made-up pid would read as stale and quietly turn every
    'live run' assertion below into a test of the wrong branch."""
    base = dict(run_id="r1", pid=os.getpid(), started_at="t",
                cells_done=30, cells_total=63)
    base.update(kw)
    return RunStatus(**base)


class _Dead(RunStatus):
    @property
    def is_alive(self) -> bool:
        return False


def test_a_live_run_is_green():
    state = indicator_state(_running(model="gemma-4-12b", capability="code-gen"),
                            loaded=["gemma-4-12b"])
    assert state.level is IN_USE
    assert "gemma-4-12b" in state.detail


def test_a_live_run_shows_progress():
    state = indicator_state(_running(), loaded=["m"])
    assert "30/63" in state.detail or "48%" in state.detail


def test_progress_within_the_current_cell_is_shown():
    """Without this the lamp sits unchanged for the hours one 108-case cell can
    take, which looks identical to a hung run."""
    state = indicator_state(_running(cases_done=43, cases_total=108), loaded=["m"])
    assert "43/108" in state.detail


def test_models_loaded_with_no_run_is_yellow():
    """The state the indicator exists for. Nothing is running, but VRAM is still
    occupied, which costs power silently."""
    state = indicator_state(None, loaded=["gemma-4-12b", "qwen3.5-9b"])
    assert state.level is IDLE
    assert "2" in state.detail


def test_nothing_loaded_and_no_run_is_red():
    state = indicator_state(None, loaded=[])
    assert state.level is FREE


def test_a_model_on_another_box_does_not_make_this_card_look_busy():
    """The caller passes *local* models only. A linked instance on another
    machine showed as '1 model loaded' beside '2.7/32GB' -- a warning about
    someone else's GPU, which is just a false alarm here."""
    assert indicator_state(None, loaded=[]).level is FREE


def test_a_stale_marker_is_not_treated_as_running():
    """A killed run leaves its marker behind. Showing green then would be the
    indicator telling the exact lie it was built to prevent."""
    stale = _Dead(run_id="r", pid=999999, started_at="t")
    assert indicator_state(stale, loaded=["m"]).level is IDLE
    assert indicator_state(stale, loaded=[]).level is FREE


def test_unknown_vram_never_reports_free():
    """`None` means we could not query LM Studio. Claiming the GPU is free would
    be a guess presented as a fact -- degrade to idle and say so."""
    state = indicator_state(None, loaded=None)
    assert state.level is IDLE
    assert "unknown" in state.detail.lower()


def test_a_live_run_is_green_even_when_vram_is_unknown():
    """An active run is authoritative on its own: it is generating regardless of
    whether we can enumerate VRAM."""
    assert indicator_state(_running(), loaded=None).level is IN_USE


def test_every_level_has_a_colour_and_a_label():
    """The label carries the meaning so the indicator does not depend on the
    viewer reading red as 'dormant' rather than 'broken'."""
    for status, loaded in ((_running(), ["m"]), (None, ["m"]), (None, [])):
        state = indicator_state(status, loaded=loaded)
        assert state.level.colour.startswith("#")
        assert state.level.label
        assert state.detail
