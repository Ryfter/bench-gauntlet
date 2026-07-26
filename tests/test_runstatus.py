"""The run indicator, and deciding what to evict afterwards.

Kevin runs Gauntlet on his desktop, not a headless box. Two consequences:
a run must be *visible* -- he should never have to ask whether the machine is
busy because of us -- and the GPU must be handed back when we are done with it,
because a loaded-but-idle model is wasted power.
"""
from __future__ import annotations

import json

from gauntlet import vram
from gauntlet.runstatus import RunStatus, clear_status, read_status, write_status
from gauntlet.vram import models_to_unload, parse_lms_ps


# --- the indicator -------------------------------------------------------------

def test_status_round_trips(tmp_path):
    path = tmp_path / ".running.json"
    write_status(path, RunStatus(run_id="r1", pid=42, started_at="2026-07-26T11:08:00",
                                cells_total=63))
    got = read_status(path)
    assert got is not None
    assert (got.run_id, got.pid, got.cells_total) == ("r1", 42, 63)


def test_no_status_file_means_nothing_is_running(tmp_path):
    assert read_status(tmp_path / "absent.json") is None


def test_clear_status_is_idempotent(tmp_path):
    """Called from a `finally`, so it must tolerate the file already being gone
    -- an error while cleaning up would mask the error that actually mattered."""
    path = tmp_path / ".running.json"
    write_status(path, RunStatus(run_id="r", pid=1, started_at="t"))
    clear_status(path)
    clear_status(path)
    assert not path.exists()


def test_a_corrupt_status_file_reads_as_not_running(tmp_path):
    """A half-written file from a killed run must not crash `gauntlet status`.
    The whole point of the command is to work when things have gone wrong."""
    path = tmp_path / ".running.json"
    path.write_text("{not json", encoding="utf-8")
    assert read_status(path) is None


def test_status_carries_no_endpoint(tmp_path):
    """Privacy invariant: nothing Gauntlet writes may contain a host or IP. The
    status file names the model and the run, never where it is being served."""
    path = tmp_path / ".running.json"
    write_status(path, RunStatus(run_id="r", pid=1, started_at="t",
                                 model="google/gemma-4-12b", capability="code-gen"))
    raw = path.read_text(encoding="utf-8")
    assert "http" not in raw
    assert set(json.loads(raw)) == {
        "run_id", "pid", "started_at", "updated_at", "model", "capability",
        "cells_done", "cells_total",
    }


def test_progress_fraction_is_none_without_a_total():
    assert RunStatus(run_id="r", pid=1, started_at="t").progress is None
    assert RunStatus(run_id="r", pid=1, started_at="t",
                     cells_done=3, cells_total=12).progress == 0.25


# --- what to unload ------------------------------------------------------------

_PS = """
IDENTIFIER                MODEL                     STATUS    SIZE       CONTEXT   PARALLEL   DEVICE          TTL
gemma-3-12b-it-heretic    gemma-3-12b-it-heretic    IDLE      14.19 GB   24000     4          Local
qwen/qwen3.5-9b           qwen/qwen3.5-9b           IDLE      10.45 GB   24000     4          Local           58m / 1h
"""


def test_parse_lms_ps_reads_the_loaded_identifiers():
    assert parse_lms_ps(_PS) == ["gemma-3-12b-it-heretic", "qwen/qwen3.5-9b"]


def test_parse_lms_ps_handles_nothing_loaded():
    assert parse_lms_ps("\nIDENTIFIER   MODEL   STATUS\n") == []
    assert parse_lms_ps("") == []


def test_only_models_we_caused_to_load_are_unloaded():
    """The snapshot-diff rule. A model already resident when we started is
    someone else's -- evicting it would be reaching into Kevin's own session."""
    assert models_to_unload(
        before=["gemma-3-12b-it-heretic"],
        ran=["qwen/qwen3.5-9b", "gemma-3-12b-it-heretic"],
    ) == ["qwen/qwen3.5-9b"]


def test_a_model_we_ran_that_was_already_loaded_is_left_alone():
    assert models_to_unload(before=["m"], ran=["m"]) == []


def test_models_we_did_not_run_are_never_touched():
    """Even a model we did not load and did not run stays put. We only ever
    clean up after ourselves."""
    assert models_to_unload(before=[], ran=["a"]) == ["a"]
    assert models_to_unload(before=["b"], ran=["a"]) == ["a"]


def test_the_unload_list_is_deduplicated_and_ordered():
    assert models_to_unload(before=[], ran=["b", "a", "b"]) == ["a", "b"]


def test_an_unknown_snapshot_unloads_nothing(monkeypatch):
    """`None` means we never learned what was already loaded. Leaving VRAM
    occupied wastes power; evicting Kevin's model mid-session breaks his work.
    The second is worse, so an unknown snapshot must do nothing."""
    called: list[str] = []
    monkeypatch.setattr(vram, "unload", lambda m: called.append(m) or True)
    assert vram.release_after_run(None, ["a", "b"]) == []
    assert called == []


def test_an_empty_snapshot_does_release_what_we_ran(monkeypatch):
    """The counterpart: `[]` is real knowledge that the machine was clear, so
    everything we loaded is ours to free."""
    monkeypatch.setattr(vram, "unload", lambda m: True)
    assert vram.release_after_run([], ["b", "a"]) == ["a", "b"]


def test_a_failed_unload_is_not_reported_as_released(monkeypatch):
    monkeypatch.setattr(vram, "unload", lambda m: m != "stuck")
    assert vram.release_after_run([], ["stuck", "ok"]) == ["ok"]
