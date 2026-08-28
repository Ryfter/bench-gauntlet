"""Suite-wide guards for non-live tests.

Ordinary unit tests must not query, load, or unload real LM Studio models, and
must not open remote sockets. Live tests opt in with ``pytest.mark.live``.
"""
from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import pytest

_BLOCKED_CLIS = frozenset({"lms", "ollama"})
_LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _blocked_cli(args) -> str | None:
    if args is None:
        return None
    if isinstance(args, (bytes, str)):
        first = str(args).split()[0]
    elif isinstance(args, (list, tuple)) and args:
        first = str(args[0])
    else:
        return None
    name = Path(first).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name if name in _BLOCKED_CLIS else None


def _connect_host(address) -> str:
    if isinstance(address, tuple) and address:
        return str(address[0]).lower().strip("[]")
    return str(address).lower()


@pytest.fixture(autouse=True)
def _block_lms_and_remote_network(request, monkeypatch):
    if request.node.get_closest_marker("live"):
        return

    real_popen = subprocess.Popen
    real_run = subprocess.run
    real_connect = socket.socket.connect
    real_create_connection = socket.create_connection

    def guarded_popen(args=None, **kwargs):
        blocked = _blocked_cli(args if args is not None else kwargs.get("args"))
        if blocked is None:
            blocked = _blocked_cli(kwargs.get("executable"))
        if blocked:
            raise RuntimeError(
                f"non-live test must not invoke {blocked}; inject/mock VRAM operations"
            )
        if args is None:
            return real_popen(**kwargs)
        return real_popen(args, **kwargs)

    def guarded_run(*popenargs, **kwargs):
        args = popenargs[0] if popenargs else kwargs.get("args")
        blocked = _blocked_cli(args) or _blocked_cli(kwargs.get("executable"))
        if blocked:
            raise RuntimeError(
                f"non-live test must not invoke {blocked}; inject/mock VRAM operations"
            )
        return real_run(*popenargs, **kwargs)

    def guarded_connect(self, address):
        host = _connect_host(address)
        if host not in _LOCAL_HOSTS:
            raise RuntimeError(
                f"non-live test must not connect to {host}"
            )
        return real_connect(self, address)

    def guarded_create_connection(address, *args, **kwargs):
        host = _connect_host(address)
        if host not in _LOCAL_HOSTS:
            raise RuntimeError(
                f"non-live test must not connect to {host}"
            )
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", guarded_popen)
    monkeypatch.setattr(subprocess, "run", guarded_run)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
