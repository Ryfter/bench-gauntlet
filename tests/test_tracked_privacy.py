"""Structural privacy checks for files that can enter the public tree."""
from __future__ import annotations

import hashlib
import ipaddress
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
IPV4_RE = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]+")
ALLOWED_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("203.0.113.0/24"),
)

# Hashes keep the actual private identifiers out of the guard that bans them.
FORBIDDEN_TOKEN_HASHES = frozenset({
    "afac327e73694e68c02f5c62f3bc0bcf0f239744ff12921e781487a0f9b3d5d0",
    "e237e6b606fec77f3641a86cb37c7d990798306b90141b288221dafdc8d9d33d",
    "48e1112588be163ac313293a056a6c9ab6070b35c74272f54e7e0e3b57cee8fb",
})


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True,
        capture_output=True,
    )
    return [REPO_ROOT / p.decode() for p in result.stdout.split(b"\0") if p]


def test_tracked_tree_contains_no_private_network_or_device_identifiers():
    violations: list[str] = []
    for path in _tracked_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in IPV4_RE.finditer(text):
            address = ipaddress.ip_address(match.group())
            if not any(address in network for network in ALLOWED_NETWORKS):
                violations.append(f"{path.relative_to(REPO_ROOT)}: disallowed IPv4 literal")
        searchable = f"{path.relative_to(REPO_ROOT)}\n{text}".lower()
        for token in TOKEN_RE.findall(searchable):
            digest = hashlib.sha256(token.encode()).hexdigest()
            if digest in FORBIDDEN_TOKEN_HASHES:
                violations.append(f"{path.relative_to(REPO_ROOT)}: private device token")
    assert not violations, "\n".join(sorted(set(violations)))
