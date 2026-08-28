"""Crash-safe snapshots and keyed JSONL upserts.

Checkpoint and scorecard files are rewritten through a sibling temp file and
``os.replace``. A kill before the replace leaves the previous complete file
in place. JSONL readers skip blank and unparseable lines so a torn tail cannot
block resume or analysis.

This is durability, not a lock manager: concurrent writers of the same path
are still undefined.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


def atomic_write_text(path: str | Path, text: str) -> None:
    """Replace ``path`` with ``text`` only after the new bytes are on disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_jsonl_objects(path: str | Path) -> list[dict[str, Any]]:
    """Load JSON objects from a JSONL file, skipping blank and torn lines."""
    path = Path(path)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def write_jsonl_objects(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    atomic_write_text(path, body)


def upsert_jsonl(
    path: str | Path,
    rows: Iterable[dict[str, Any]],
    key_fn: Callable[[dict[str, Any]], Any],
) -> None:
    """Replace existing rows that share a key; append new keys. Atomic rewrite."""
    by_key: dict[Any, dict[str, Any]] = {}
    for existing in read_jsonl_objects(path):
        by_key[key_fn(existing)] = existing
    for row in rows:
        by_key[key_fn(row)] = row
    write_jsonl_objects(path, by_key.values())
