from __future__ import annotations

import ast
from pathlib import Path


def test_only_openai_client_module_imports_http_libraries():
    package = Path(__file__).resolve().parents[1] / "gauntlet"
    violations = []
    for path in package.rglob("*.py"):
        if path.name == "client.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            if set(names) & {"httpx", "requests", "urllib3", "aiohttp"}:
                violations.append(str(path.relative_to(package.parent)))
    assert not violations, f"HTTP imports outside gauntlet/client.py: {violations}"
