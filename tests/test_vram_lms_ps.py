"""Parsing `lms ps` output with and without the DEVICE column."""
from __future__ import annotations

import pytest

from gauntlet import vram
from gauntlet.vram import (
    is_local_device,
    local_loaded_models,
    parse_lms_ps,
    parse_lms_ps_rows,
)

# Legacy output: DEVICE column present but value is the bare ``Local`` token.
_PS_LOCAL = """
IDENTIFIER                MODEL                     STATUS    SIZE       CONTEXT   PARALLEL   DEVICE          TTL
gemma-3-12b-it-heretic    gemma-3-12b-it-heretic    IDLE      14.19 GB   24000     4          Local
qwen/qwen3.5-9b           qwen/qwen3.5-9b           IDLE      10.45 GB   24000     4          Local           58m / 1h
"""

# Linked-instance output: DEVICE names the LMS host (Firefly vs work PC).
_PS_LINKED = """
IDENTIFIER                MODEL                     STATUS    SIZE       CONTEXT   PARALLEL   DEVICE          TTL
google/gemma-4-31b        google/gemma-4-31b        IDLE      62.00 GB   8192      1          Firefly
google--gemma-3-12b@q8_0  google--gemma-3-12b@q8_0  IDLE      14.19 GB   24000     4          ITSCM-KRANK2    58m / 1h
"""


def test_parse_lms_ps_rows_legacy_local_format():
    assert parse_lms_ps_rows(_PS_LOCAL) == [
        ("gemma-3-12b-it-heretic", "Local"),
        ("qwen/qwen3.5-9b", "Local"),
    ]


def test_parse_lms_ps_rows_linked_device_names():
    assert parse_lms_ps_rows(_PS_LINKED) == [
        ("google/gemma-4-31b", "Firefly"),
        ("google--gemma-3-12b@q8_0", "ITSCM-KRANK2"),
    ]


def test_parse_lms_ps_still_returns_identifiers_only():
    assert parse_lms_ps(_PS_LINKED) == [
        "google/gemma-4-31b",
        "google--gemma-3-12b@q8_0",
    ]


def test_is_local_device_defaults_to_local_and_firefly():
    assert is_local_device("Local")
    assert is_local_device("Firefly")
    assert not is_local_device("ITSCM-KRANK2")
    assert not is_local_device("ITSCM-WORK")


def test_is_local_device_respects_gauntlet_lms_device(monkeypatch):
    monkeypatch.setenv("GAUNTLET_LMS_DEVICE", "Firefly")
    assert is_local_device("Firefly")
    assert not is_local_device("Local")
    assert not is_local_device("ITSCM-KRANK2")


def test_local_loaded_models_excludes_remote_itscm(monkeypatch):
    monkeypatch.setattr(vram, "_lms_ps_output", lambda: _PS_LINKED)
    assert local_loaded_models() == ["google/gemma-4-31b"]


def test_local_loaded_models_includes_all_local_rows(monkeypatch):
    monkeypatch.setattr(vram, "_lms_ps_output", lambda: _PS_LOCAL)
    assert local_loaded_models() == [
        "gemma-3-12b-it-heretic",
        "qwen/qwen3.5-9b",
    ]


def test_local_loaded_models_with_env_override(monkeypatch):
    monkeypatch.setenv("GAUNTLET_LMS_DEVICE", "ITSCM-KRANK2")
    monkeypatch.setattr(vram, "_lms_ps_output", lambda: _PS_LINKED)
    # ITSCM-* is never local for unload purposes even when env matches.
    assert local_loaded_models() == []


def test_loaded_models_by_device(monkeypatch):
    monkeypatch.setattr(vram, "_lms_ps_output", lambda: _PS_LINKED)
    assert vram.loaded_models_by_device() == parse_lms_ps_rows(_PS_LINKED)


def test_parse_lms_ps_rows_without_device_column_falls_back_to_local_token():
    """Pre-DEVICE-header output: locality inferred from a bare ``Local`` token."""
    old = """
IDENTIFIER                MODEL                     STATUS    SIZE
gemma-3-12b-it-heretic    gemma-3-12b-it-heretic    IDLE      14.19 GB   Local
remote-model              remote-model              IDLE      10.00 GB   24000
"""
    assert parse_lms_ps_rows(old) == [
        ("gemma-3-12b-it-heretic", "Local"),
        ("remote-model", ""),
    ]
