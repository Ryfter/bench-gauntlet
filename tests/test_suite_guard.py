"""The default suite must not operate a real LM Studio or open remote sockets."""
from __future__ import annotations

import socket
import subprocess

import pytest


def test_non_live_tests_cannot_invoke_lms():
    with pytest.raises(RuntimeError, match="lms"):
        subprocess.run(["lms", "ps"])


def test_non_live_tests_cannot_invoke_ollama_cli():
    with pytest.raises(RuntimeError, match="ollama"):
        subprocess.run(["ollama", "list"])


def test_non_live_tests_cannot_open_remote_sockets():
    with pytest.raises(RuntimeError, match="connect"):
        socket.create_connection(("203.0.113.10", 9), timeout=0.2)
