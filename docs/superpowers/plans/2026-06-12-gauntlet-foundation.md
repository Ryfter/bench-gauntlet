# Gauntlet Foundation Implementation Plan (Plan 1 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Gauntlet foundation — typed contracts, private-config loading, the sole HTTP client, and metadata enrichment adapters — so later plans (scoring, runner) build on a tested base.

**Architecture:** A Python package where `client.py` is the *only* code that touches the network; everything else is pure functions over strings/dicts, unit-tested against static fixtures. Config that identifies the user's network loads from outside the repo by default. Covers design Phases 0–2.

**Tech Stack:** Python 3.12+ (works on 3.14), httpx, pydantic v2, PyYAML, jsonschema, Typer, pytest.

**Source of truth:** `docs/2026-06-12-gauntlet-build-design.md` (Sections A, A.5, B; Phases 0–2).

**Plan roadmap:** Plan 2 = scoring & scorecard (Phases 3–4); Plan 3 = runner/sequencer/CLI (Phases 5–7); Plan 4 = advanced (Phases 8–10). Written as we reach them.

---

## File Structure

- `pyproject.toml` — package metadata, deps, console script, pytest config
- `gauntlet/__init__.py` — version
- `gauntlet/errors.py` — typed exception/outcome taxonomy
- `gauntlet/config.py` — `Target`, `Box`, `ModelProfile`, `GauntletConfig`; resolution order + `load_config`
- `gauntlet/battery.py` — `Case`, `Battery`; `load_battery`, `load_batteries`; `applies_to`
- `gauntlet/models.py` — scorecard-side contracts: `CaseResult`, `Cell`, `ContextDepth`, `BaselineGap`, `Scorecard` (fields only; emission is Plan 2)
- `gauntlet/client.py` — `OpenAIClient` (chat + embeddings) over httpx
- `gauntlet/enrich/__init__.py` — `Enricher` protocol + `ModelMeta` + registry
- `gauntlet/enrich/lmstudio.py` — `/api/v1/models` adapter
- `gauntlet/enrich/ollama.py` — `/api/tags` adapter
- `gauntlet/cli.py` — Typer app with a `targets` command (others stubbed in later plans)
- `tests/...` — mirrors the package; `tests/fixtures/` holds captured real payloads
- `targets.example.yaml` — already exists; extended with `boxes:` in Task 1.2

---

## Task 0.1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `gauntlet/__init__.py`, `gauntlet/cli.py`, `tests/__init__.py`, `tests/test_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoke.py
import gauntlet


def test_version_exposed():
    assert isinstance(gauntlet.__version__, str)
    assert gauntlet.__version__.count(".") >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "gauntlet"
version = "0.1.0"
description = "A gauntlet of trials for local models"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "jsonschema>=4.21",
    "typer>=0.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
gauntlet = "gauntlet.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["gauntlet"]

[tool.pytest.ini_options]
markers = [
    "live: tests that hit a real OpenAI-compatible endpoint (opt-in: -m live)",
]
addopts = "-m 'not live'"
```

```python
# gauntlet/__init__.py
__version__ = "0.1.0"
```

```python
# gauntlet/cli.py
import typer

app = typer.Typer(help="A gauntlet of trials for local models.")


@app.command()
def version() -> None:
    """Print the Gauntlet version."""
    from gauntlet import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
```

```python
# tests/__init__.py
```

- [ ] **Step 4: Create the venv and install, then run the test**

Run:
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/test_smoke.py -v
```
Expected: PASS. Also run `.venv/Scripts/gauntlet version` → prints `0.1.0`.

(All later `pytest`/`gauntlet` invocations use `.venv/Scripts/python -m pytest` / `.venv/Scripts/gauntlet`.)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml gauntlet/ tests/
git commit -m "scaffold: gauntlet package, Typer CLI, pytest config"
```

---

## Task 0.2: Harden .gitignore for secrets

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add secret/config/venv ignores**

Append to `.gitignore` (keep existing `targets.yaml` and `scorecards/*` rules):

```gitignore
# secrets — never committed; env vars are the real channel
.env
.env.*

# editable-install / build artifacts
*.egg-info/
build/
dist/

# any local private config that strays into the tree
targets.local.yaml
```

- [ ] **Step 2: Verify nothing private is currently tracked**

Run: `git status --short` and `git ls-files | grep -E '^(targets\.yaml|\.env)' || echo "clean"`
Expected: `clean` (no private files tracked).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore .env, build artifacts, stray local config"
```

---

## Task 1.1: Error taxonomy

**Files:**
- Create: `gauntlet/errors.py`, `tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_errors.py
import pytest

from gauntlet import errors


def test_config_not_found_carries_path():
    err = errors.ConfigNotFound("/nope/targets.yaml")
    assert "/nope/targets.yaml" in str(err)
    assert isinstance(err, errors.GauntletError)


def test_bad_battery_names_the_file():
    err = errors.BadBattery("batteries/extract-json.yaml", "missing 'capability'")
    assert "extract-json.yaml" in str(err)
    assert "missing 'capability'" in str(err)
    assert isinstance(err, errors.GauntletError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_errors.py -v`
Expected: FAIL — `AttributeError: module 'gauntlet.errors' has no attribute 'ConfigNotFound'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/errors.py
"""Typed outcomes. Startup/config errors raise; per-cell runtime errors
(Unreachable, OOM, JudgeUnavailable, BoxBusy) are recorded, not raised —
they live here as marker classes the runner (Plan 3) converts to cell states."""
from __future__ import annotations


class GauntletError(Exception):
    """Base for all Gauntlet errors."""


class ConfigNotFound(GauntletError):
    def __init__(self, path: str) -> None:
        super().__init__(f"No Gauntlet config found at: {path}")
        self.path = str(path)


class ConfigInvalid(GauntletError):
    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"Invalid config {path}: {detail}")
        self.path = str(path)
        self.detail = detail


class BadBattery(GauntletError):
    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"Malformed battery {path}: {detail}")
        self.path = str(path)
        self.detail = detail


# Runtime cell-outcome markers (recorded by the runner, never abort a run).
class Unreachable(GauntletError):
    """Target endpoint could not be reached."""


class ModelLoadFailed(GauntletError):
    """Model failed to load / OOM."""


class JudgeUnavailable(GauntletError):
    """No eligible judge model available to score a case."""


class BoxBusy(GauntletError):
    """Box marked busy; cell deferred."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/errors.py tests/test_errors.py
git commit -m "feat: error taxonomy (config + runtime cell outcomes)"
```

---

## Task 1.2: Config models + keep_list glob

**Files:**
- Create: `gauntlet/config.py`, `tests/test_config_models.py`
- Modify: `targets.example.yaml` (add `boxes:` block)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_models.py
from gauntlet.config import GauntletConfig


def _cfg() -> GauntletConfig:
    return GauntletConfig.model_validate(
        {
            "targets": [
                {"name": "firefly-lmstudio", "base_url": "http://localhost:1234",
                 "api": "openai", "enrich": "lmstudio", "box": "firefly"},
            ],
            "boxes": [
                {"id": "firefly", "hardware": "RTX 5090 desktop", "vram_gb": 32,
                 "usage_class": "broad", "busy": False},
            ],
            "models": [
                {"target": "firefly-lmstudio", "id": "google/gemma-4-31b", "context": 8192},
            ],
            "keep_list": ["*heretic*", "*swahili*"],
        }
    )


def test_box_lookup_by_target_returns_hardware():
    cfg = _cfg()
    box = cfg.box_for_target("firefly-lmstudio")
    assert box is not None
    assert box.hardware == "RTX 5090 desktop"
    assert box.usage_class == "broad"


def test_keep_list_globs_match_case_insensitively():
    cfg = _cfg()
    assert cfg.is_kept("gemma-3-12b-it-heretic-v2") is True
    assert cfg.is_kept("Some-Swahili-Tutor") is True
    assert cfg.is_kept("google/gemma-4-31b") is False


def test_defaults_are_safe():
    box = GauntletConfig.model_validate(
        {"boxes": [{"id": "x", "hardware": "h", "vram_gb": 8}]}
    ).boxes[0]
    assert box.usage_class == "broad"
    assert box.busy is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_config_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/config.py
from __future__ import annotations

import fnmatch
from typing import Literal

from pydantic import BaseModel, Field


class Target(BaseModel):
    name: str
    base_url: str
    api: Literal["openai"] = "openai"
    enrich: str | None = None
    box: str | None = None


class Box(BaseModel):
    id: str
    hardware: str  # public label, e.g. "RTX 5090 desktop"
    vram_gb: float
    usage_class: Literal["tight", "broad"] = "broad"
    busy: bool = False


class ModelProfile(BaseModel):
    """A load profile: model @ context — the unit under test."""
    target: str
    id: str
    context: int


class GauntletConfig(BaseModel):
    targets: list[Target] = Field(default_factory=list)
    boxes: list[Box] = Field(default_factory=list)
    models: list[ModelProfile] = Field(default_factory=list)
    keep_list: list[str] = Field(default_factory=list)

    def target_by_name(self, name: str) -> Target | None:
        return next((t for t in self.targets if t.name == name), None)

    def box_by_id(self, box_id: str) -> Box | None:
        return next((b for b in self.boxes if b.id == box_id), None)

    def box_for_target(self, target_name: str) -> Box | None:
        target = self.target_by_name(target_name)
        if target is None or target.box is None:
            return None
        return self.box_by_id(target.box)

    def is_kept(self, model_id: str) -> bool:
        """True if a keep_list glob matches (case-insensitive)."""
        mid = model_id.lower()
        return any(fnmatch.fnmatch(mid, pat.lower()) for pat in self.keep_list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_config_models.py -v`
Expected: PASS

- [ ] **Step 5: Extend the public template with `boxes:`**

In `targets.example.yaml`, after the `targets:` block and before `models:`, insert:

```yaml
# Box inventory the `box:` field joins to. `hardware` is the ONLY box label
# that appears in a shared scorecard (hostnames stay private). `busy: true`
# defers that box's cells (e.g. while gaming).
boxes:
  - { id: firefly, hardware: "RTX 5090 desktop",      vram_gb: 32, usage_class: broad, busy: false }
  - { id: wraith2, hardware: "RTX 2070 Super laptop", vram_gb: 8,  usage_class: tight, busy: false }
```

- [ ] **Step 6: Commit**

```bash
git add gauntlet/config.py tests/test_config_models.py targets.example.yaml
git commit -m "feat: config models (Target/Box/ModelProfile) + keep_list glob; boxes in template"
```

---

## Task 1.3: Config resolution order + loader

**Files:**
- Modify: `gauntlet/config.py`
- Create: `tests/test_config_load.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_load.py
import pytest

from gauntlet import errors
from gauntlet.config import config_path, load_config


def test_explicit_flag_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("GAUNTLET_CONFIG", str(tmp_path / "env.yaml"))
    explicit = tmp_path / "explicit.yaml"
    assert config_path(str(explicit)) == explicit


def test_env_var_used_when_no_flag(tmp_path, monkeypatch):
    env = tmp_path / "env.yaml"
    monkeypatch.setenv("GAUNTLET_CONFIG", str(env))
    assert config_path(None) == env


def test_missing_config_raises_config_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("GAUNTLET_CONFIG", str(tmp_path / "absent.yaml"))
    with pytest.raises(errors.ConfigNotFound):
        load_config()


def test_load_parses_yaml(tmp_path, monkeypatch):
    cfg_file = tmp_path / "targets.yaml"
    cfg_file.write_text(
        "targets:\n"
        "  - { name: t1, base_url: 'http://x:1', enrich: ollama, box: b1 }\n"
        "boxes:\n"
        "  - { id: b1, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: tight }\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GAUNTLET_CONFIG", str(cfg_file))
    cfg = load_config()
    assert cfg.box_for_target("t1").hardware == "RTX 2070 Super laptop"


def test_malformed_yaml_raises_config_invalid(tmp_path, monkeypatch):
    cfg_file = tmp_path / "targets.yaml"
    cfg_file.write_text("targets: [ { name: t1 ", encoding="utf-8")  # broken
    monkeypatch.setenv("GAUNTLET_CONFIG", str(cfg_file))
    with pytest.raises(errors.ConfigInvalid):
        load_config()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_config_load.py -v`
Expected: FAIL — `ImportError: cannot import name 'config_path' from 'gauntlet.config'`

- [ ] **Step 3: Write minimal implementation**

Append to `gauntlet/config.py`:

```python
import os
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from gauntlet import errors


def _user_config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "gauntlet"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "gauntlet"


def config_path(explicit: str | None = None) -> Path:
    """Resolution order: --config flag > $GAUNTLET_CONFIG > user-config dir > ./targets.yaml."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("GAUNTLET_CONFIG")
    if env:
        return Path(env)
    user = _user_config_dir() / "targets.yaml"
    if user.exists():
        return user
    return Path("targets.yaml")


def load_config(explicit: str | None = None) -> GauntletConfig:
    path = config_path(explicit)
    if not path.exists():
        raise errors.ConfigNotFound(str(path))
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise errors.ConfigInvalid(str(path), f"YAML parse error: {exc}") from exc
    try:
        return GauntletConfig.model_validate(data)
    except ValidationError as exc:
        raise errors.ConfigInvalid(str(path), str(exc)) from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_config_load.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/config.py tests/test_config_load.py
git commit -m "feat: out-of-tree config resolution order + safe loader"
```

---

## Task 1.4: Battery + Case models and loaders

**Files:**
- Create: `gauntlet/battery.py`, `tests/test_battery.py`, `tests/fixtures/batteries/extract-json.yaml`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_battery.py
from pathlib import Path

import pytest

from gauntlet import errors
from gauntlet.battery import Battery, load_battery, load_batteries

FIX = Path(__file__).parent / "fixtures" / "batteries"


def test_load_valid_battery():
    bat = load_battery(FIX / "extract-json.yaml")
    assert bat.capability == "extract-json"
    assert bat.context_floor == 4096
    assert bat.cases[0].id == "invoice-01"
    assert bat.cases[0].scoring == "json-schema"


def test_applies_to_respects_context_floor():
    bat = Battery(capability="c", context_floor=4096, cases=[])
    assert bat.applies_to(context=8192) is True
    assert bat.applies_to(context=2048) is False


def test_missing_capability_raises_bad_battery(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("context_floor: 4096\ncases: []\n", encoding="utf-8")
    with pytest.raises(errors.BadBattery) as exc:
        load_battery(bad)
    assert "broken.yaml" in str(exc.value)


def test_load_batteries_skips_and_reports_bad_ones(tmp_path, capsys):
    good = tmp_path / "good.yaml"
    good.write_text("capability: g\ncontext_floor: 0\ncases: []\n", encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text("nonsense: true\n", encoding="utf-8")
    loaded = load_batteries(tmp_path)
    assert [b.capability for b in loaded] == ["g"]
    assert "bad.yaml" in capsys.readouterr().err
```

- [ ] **Step 2: Create the fixture, then run the test to verify it fails**

```yaml
# tests/fixtures/batteries/extract-json.yaml
capability: extract-json
context_floor: 4096
cases:
  - id: invoice-01
    prompt_file: cases/extract-json/invoice-01.txt
    scoring: json-schema
    schema_file: cases/extract-json/invoice-01.schema.json
  - id: messy-table-03
    prompt_file: cases/extract-json/messy-table-03.txt
    scoring: judge
    rubric: "Score 0-1: completeness, correctness, no invented data."
weights: { quality: 1.0 }
```

Run: `.venv/Scripts/python -m pytest tests/test_battery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.battery'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/battery.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from gauntlet import errors

Scoring = Literal["exact", "regex", "json-schema", "conventional-commit",
                  "compilable-code", "judge"]


class Case(BaseModel):
    id: str
    prompt_file: str | None = None
    scoring: Scoring
    schema_file: str | None = None
    rubric: str | None = None


class Battery(BaseModel):
    capability: str
    context_floor: int = 0
    cases: list[Case] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=lambda: {"quality": 1.0})

    def applies_to(self, context: int) -> bool:
        return context >= self.context_floor


def load_battery(path: str | Path) -> Battery:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise errors.BadBattery(str(path), f"YAML parse error: {exc}") from exc
    try:
        return Battery.model_validate(data)
    except ValidationError as exc:
        raise errors.BadBattery(str(path), str(exc)) from exc


def load_batteries(directory: str | Path) -> list[Battery]:
    """Load every *.yaml in `directory`. Malformed files are named loudly on
    stderr and skipped; the rest load (design G.5)."""
    directory = Path(directory)
    out: list[Battery] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            out.append(load_battery(path))
        except errors.BadBattery as exc:
            print(f"WARNING: skipping {exc}", file=sys.stderr)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_battery.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/battery.py tests/test_battery.py tests/fixtures/batteries/extract-json.yaml
git commit -m "feat: Battery/Case models + loaders (bad files skipped + reported)"
```

---

## Task 1.5: Scorecard-side contracts (data only)

**Files:**
- Create: `gauntlet/models.py`, `tests/test_models.py`

(Emission/`--share` is Plan 2; here we only lock the field shapes so the contract is stable for consumers.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from gauntlet.models import BaselineGap, CaseResult, Cell, ContextDepth, Scorecard


def test_cell_has_no_base_url_field():
    # Privacy invariant: the contract simply has no field for an endpoint/IP.
    assert "base_url" not in Cell.model_fields
    assert "target" in Cell.model_fields  # hostname label, private-mode only
    assert "box" in Cell.model_fields     # hardware label


def test_case_result_unscored_is_representable():
    r = CaseResult(case_id="x", method="judge", score=None, passed=False, detail="unscored")
    assert r.score is None


def test_scorecard_round_trips():
    sc = Scorecard(
        run={"id": "r1", "date": "2026-06-12", "gauntlet_version": "0.1.0"},
        cells=[
            Cell(model="gemma3:1b", target="wraith2-ollama", box="RTX 2070 Super laptop",
                 context=8192, capability="extract-json", quality=0.91, pass_rate=0.86,
                 latency_p50_s=2.1, tokens_per_s=38.0, judge=None, cases=14, errors=0),
        ],
        context_depth=[ContextDepth(model="gemma3:1b", advertised=131072, effective_90pct=49152)],
        baseline_gaps=[BaselineGap(capability="commit-msg", local_champion="tavernari",
                                   frontier="claude", gap=0.03)],
    )
    again = Scorecard.model_validate(sc.model_dump())
    assert again.cells[0].box == "RTX 2070 Super laptop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/models.py
from __future__ import annotations

from pydantic import BaseModel, Field


class RunMeta(BaseModel):
    id: str
    date: str
    gauntlet_version: str


class CaseResult(BaseModel):
    case_id: str
    method: str          # exact | regex | json-schema | conventional-commit | compilable-code | judge
    score: float | None  # None == unscored (e.g. judge unavailable) — never silently 0
    passed: bool
    detail: str = ""


class Cell(BaseModel):
    model: str
    target: str | None   # hostname label; dropped in --share mode (Plan 2)
    box: str             # hardware label, e.g. "RTX 2070 Super laptop"
    context: int
    capability: str
    quality: float | None
    pass_rate: float | None
    latency_p50_s: float | None = None
    tokens_per_s: float | None = None
    judge: str | None = None
    cases: int = 0
    errors: int = 0
    # NOTE: deliberately no base_url / IP field — privacy invariant.


class ContextDepth(BaseModel):
    model: str
    advertised: int
    effective_90pct: int


class BaselineGap(BaseModel):
    capability: str
    local_champion: str
    frontier: str
    gap: float


class Scorecard(BaseModel):
    run: RunMeta
    cells: list[Cell] = Field(default_factory=list)
    context_depth: list[ContextDepth] = Field(default_factory=list)
    baseline_gaps: list[BaselineGap] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/models.py tests/test_models.py
git commit -m "feat: scorecard contracts (Cell/Scorecard) with no-base_url privacy invariant"
```

---

## Task 2.1: OpenAIClient (chat + embeddings)

**Files:**
- Create: `gauntlet/client.py`, `tests/test_client.py`

Unit tests use `httpx.MockTransport` — this exercises *our* request building and
response parsing without a network or a fake model; it is not a simulation of the
model under test. A real call is covered by the live test in Task 2.4.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client.py
import httpx
import pytest

from gauntlet import errors
from gauntlet.client import ChatResult, OpenAIClient


def _client(handler) -> OpenAIClient:
    transport = httpx.MockTransport(handler)
    return OpenAIClient(base_url="http://box:1234", transport=transport)


def test_chat_sends_openai_payload_and_parses_text():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        import json
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"completion_tokens": 5},
        })

    res = _client(handler).chat(model="m1", prompt="hi", max_tokens=16)
    assert seen["url"] == "http://box:1234/v1/chat/completions"
    assert seen["body"]["model"] == "m1"
    assert seen["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert isinstance(res, ChatResult)
    assert res.text == "hello"
    assert res.completion_tokens == 5
    assert res.latency_s >= 0


def test_unreachable_raises_typed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(errors.Unreachable):
        _client(handler).chat(model="m1", prompt="hi")


def test_embeddings_parses_vectors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    vecs = _client(handler).embeddings(model="e1", inputs=["x"])
    assert vecs == [[0.1, 0.2, 0.3]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.client'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/client.py
from __future__ import annotations

import time

import httpx
from pydantic import BaseModel

from gauntlet import errors


class ChatResult(BaseModel):
    text: str
    completion_tokens: int | None = None
    latency_s: float = 0.0


class OpenAIClient:
    """The ONLY component that performs HTTP. Everything else is pure logic."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(
            base_url=self.base_url, headers=headers, timeout=timeout, transport=transport
        )

    def chat(self, model: str, prompt: str, max_tokens: int = 512,
             temperature: float = 0.0) -> ChatResult:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        start = time.monotonic()
        try:
            resp = self._http.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise errors.Unreachable(f"{self.base_url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise errors.ModelLoadFailed(f"{model}: HTTP {exc.response.status_code}") from exc
        latency = time.monotonic() - start
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return ChatResult(text=text, completion_tokens=usage.get("completion_tokens"),
                          latency_s=latency)

    def embeddings(self, model: str, inputs: list[str]) -> list[list[float]]:
        payload = {"model": model, "input": inputs}
        try:
            resp = self._http.post("/v1/embeddings", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise errors.Unreachable(f"{self.base_url}: {exc}") from exc
        return [row["embedding"] for row in resp.json()["data"]]

    def close(self) -> None:
        self._http.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/client.py tests/test_client.py
git commit -m "feat: OpenAIClient (chat + embeddings) — sole HTTP boundary, typed errors"
```

---

## Task 2.2: Enricher protocol + LM Studio adapter

**Files:**
- Create: `gauntlet/enrich/__init__.py`, `gauntlet/enrich/lmstudio.py`, `tests/fixtures/lmstudio_models.json`, `tests/test_enrich_lmstudio.py`

- [ ] **Step 1: Capture the real fixture**

Save this real `/api/v1/models` sample (trimmed to two models) as `tests/fixtures/lmstudio_models.json`:

```json
{
  "models": [
    {
      "type": "llm",
      "key": "gemma-3-12b-it-heretic",
      "display_name": "Gemma 3 12B Instruct Heretic",
      "architecture": "gemma3",
      "quantization": { "name": "Q8_0", "bits_per_weight": 8 },
      "size_bytes": 14186554848,
      "params_string": "12B",
      "loaded_instances": [],
      "max_context_length": 131072,
      "format": "gguf",
      "capabilities": { "vision": true, "trained_for_tool_use": false }
    },
    {
      "type": "llm",
      "key": "google/gemma-4-31b",
      "display_name": "Gemma 4 31B",
      "architecture": "gemma3",
      "quantization": { "name": "Q4_K_M", "bits_per_weight": 4 },
      "size_bytes": 18500000000,
      "params_string": "31B",
      "loaded_instances": [],
      "max_context_length": 32768,
      "format": "gguf",
      "capabilities": { "vision": false, "trained_for_tool_use": true }
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_enrich_lmstudio.py
import json
from pathlib import Path

from gauntlet.enrich import ModelMeta
from gauntlet.enrich.lmstudio import parse_lmstudio

FIX = Path(__file__).parent / "fixtures" / "lmstudio_models.json"


def test_parse_lmstudio_extracts_metadata():
    payload = json.loads(FIX.read_text(encoding="utf-8"))
    metas = parse_lmstudio(payload)
    by_id = {m.id: m for m in metas}

    assert isinstance(by_id["google/gemma-4-31b"], ModelMeta)
    g4 = by_id["google/gemma-4-31b"]
    assert g4.max_context == 32768
    assert g4.quant == "Q4_K_M"
    assert g4.size_bytes == 18500000000
    assert g4.params == "31B"
    assert g4.vision is False
    assert g4.tool_use is True
    assert g4.loaded is False

    g3 = by_id["gemma-3-12b-it-heretic"]
    assert g3.vision is True
    assert g3.max_context == 131072
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_enrich_lmstudio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.enrich'`

- [ ] **Step 4: Write minimal implementation**

```python
# gauntlet/enrich/__init__.py
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class ModelMeta(BaseModel):
    id: str
    max_context: int | None = None
    quant: str | None = None
    size_bytes: int | None = None
    params: str | None = None
    vision: bool | None = None
    tool_use: bool | None = None
    loaded: bool = False


class Enricher(Protocol):
    """Adapters turn a server's native metadata endpoint into ModelMeta.
    Metadata-only — never loads a model, safe to call anytime."""

    def fetch(self, base_url: str) -> list[ModelMeta]: ...
```

```python
# gauntlet/enrich/lmstudio.py
from __future__ import annotations

import httpx

from gauntlet.enrich import ModelMeta


def parse_lmstudio(payload: dict) -> list[ModelMeta]:
    out: list[ModelMeta] = []
    for m in payload.get("models", []):
        quant = (m.get("quantization") or {}).get("name")
        caps = m.get("capabilities") or {}
        out.append(
            ModelMeta(
                id=m["key"],
                max_context=m.get("max_context_length"),
                quant=quant,
                size_bytes=m.get("size_bytes"),
                params=m.get("params_string"),
                vision=caps.get("vision"),
                tool_use=caps.get("trained_for_tool_use"),
                loaded=bool(m.get("loaded_instances")),
            )
        )
    return out


def fetch(base_url: str, transport: httpx.BaseTransport | None = None) -> list[ModelMeta]:
    url = base_url.rstrip("/") + "/api/v1/models"
    with httpx.Client(timeout=10.0, transport=transport) as c:
        resp = c.get(url)
        resp.raise_for_status()
        return parse_lmstudio(resp.json())
```

- [ ] **Step 5: Run test to verify it passes, then commit**

Run: `.venv/Scripts/python -m pytest tests/test_enrich_lmstudio.py -v`
Expected: PASS

```bash
git add gauntlet/enrich/__init__.py gauntlet/enrich/lmstudio.py tests/fixtures/lmstudio_models.json tests/test_enrich_lmstudio.py
git commit -m "feat: Enricher protocol + LM Studio /api/v1/models adapter"
```

---

## Task 2.3: Ollama enrichment adapter

**Files:**
- Create: `gauntlet/enrich/ollama.py`, `tests/fixtures/ollama_tags.json`, `tests/test_enrich_ollama.py`

- [ ] **Step 1: Capture the real fixture**

Save as `tests/fixtures/ollama_tags.json` (real `/api/tags` shape):

```json
{
  "models": [
    {
      "name": "dolphin3:8b",
      "model": "dolphin3:8b",
      "size": 4920757726,
      "details": {
        "family": "llama",
        "parameter_size": "8.0B",
        "quantization_level": "Q4_K_M"
      }
    },
    {
      "name": "gemma3:1b",
      "model": "gemma3:1b",
      "size": 815319791,
      "details": {
        "family": "gemma3",
        "parameter_size": "999.89M",
        "quantization_level": "Q4_K_M"
      }
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_enrich_ollama.py
import json
from pathlib import Path

from gauntlet.enrich.ollama import parse_ollama

FIX = Path(__file__).parent / "fixtures" / "ollama_tags.json"


def test_parse_ollama_extracts_metadata():
    payload = json.loads(FIX.read_text(encoding="utf-8"))
    by_id = {m.id: m for m in parse_ollama(payload)}

    g = by_id["gemma3:1b"]
    assert g.size_bytes == 815319791
    assert g.quant == "Q4_K_M"
    assert g.params == "999.89M"
    # Ollama /api/tags does not advertise context or capabilities -> None.
    assert g.max_context is None
    assert g.vision is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_enrich_ollama.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.enrich.ollama'`

- [ ] **Step 4: Write minimal implementation**

```python
# gauntlet/enrich/ollama.py
from __future__ import annotations

import httpx

from gauntlet.enrich import ModelMeta


def parse_ollama(payload: dict) -> list[ModelMeta]:
    out: list[ModelMeta] = []
    for m in payload.get("models", []):
        details = m.get("details") or {}
        out.append(
            ModelMeta(
                id=m["name"],
                max_context=None,         # not exposed by /api/tags
                quant=details.get("quantization_level"),
                size_bytes=m.get("size"),
                params=details.get("parameter_size"),
                vision=None,
                tool_use=None,
                loaded=False,
            )
        )
    return out


def fetch(base_url: str, transport: httpx.BaseTransport | None = None) -> list[ModelMeta]:
    url = base_url.rstrip("/") + "/api/tags"
    with httpx.Client(timeout=10.0, transport=transport) as c:
        resp = c.get(url)
        resp.raise_for_status()
        return parse_ollama(resp.json())
```

- [ ] **Step 5: Run test to verify it passes, then commit**

Run: `.venv/Scripts/python -m pytest tests/test_enrich_ollama.py -v`
Expected: PASS

```bash
git add gauntlet/enrich/ollama.py tests/fixtures/ollama_tags.json tests/test_enrich_ollama.py
git commit -m "feat: Ollama /api/tags enrichment adapter"
```

---

## Task 2.4: `gauntlet targets` command + live metadata test

**Files:**
- Modify: `gauntlet/cli.py`, `gauntlet/enrich/__init__.py`
- Create: `tests/test_cli_targets.py`, `tests/live/test_live_enrich.py`, `tests/live/__init__.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_targets.py
from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()


def test_targets_lists_models(tmp_path, monkeypatch):
    cfg = tmp_path / "targets.yaml"
    cfg.write_text(
        "targets:\n"
        "  - { name: wraith2-ollama, base_url: 'http://h:11434', enrich: ollama, box: wraith2 }\n"
        "boxes:\n"
        "  - { id: wraith2, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: tight }\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GAUNTLET_CONFIG", str(cfg))

    # Patch the enrich registry so no network is touched in this unit test.
    from gauntlet import enrich
    from gauntlet.enrich import ModelMeta
    monkeypatch.setitem(
        enrich.REGISTRY, "ollama",
        lambda base_url, transport=None: [ModelMeta(id="gemma3:1b", size_bytes=815319791)],
    )

    result = runner.invoke(app, ["targets"])
    assert result.exit_code == 0
    assert "wraith2-ollama" in result.stdout
    assert "gemma3:1b" in result.stdout
    assert "RTX 2070 Super laptop" in result.stdout
```

```python
# tests/live/__init__.py
```

```python
# tests/live/test_live_enrich.py
"""Opt-in: hits a REAL endpoint, metadata-only (no model load, VRAM-safe).
Run with: pytest -m live  (set GAUNTLET_LIVE_OLLAMA to a reachable base_url)."""
import os

import pytest

pytestmark = pytest.mark.live


def test_live_ollama_tags():
    base = os.environ.get("GAUNTLET_LIVE_OLLAMA")
    if not base:
        pytest.skip("set GAUNTLET_LIVE_OLLAMA to a reachable Ollama base_url")
    from gauntlet.enrich.ollama import fetch
    metas = fetch(base)
    assert metas, "expected at least one installed model"
    assert all(m.id for m in metas)
```

- [ ] **Step 2: Run unit test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_cli_targets.py -v`
Expected: FAIL — `KeyError: 'REGISTRY'` / targets command missing.

- [ ] **Step 3: Add the registry and the command**

Append to `gauntlet/enrich/__init__.py`:

```python
from gauntlet.enrich import lmstudio, ollama  # noqa: E402  (registry wiring)

# name -> fetch(base_url, transport=None) -> list[ModelMeta]
REGISTRY = {
    "lmstudio": lmstudio.fetch,
    "ollama": ollama.fetch,
}
```

Append to `gauntlet/cli.py`:

```python
@app.command()
def targets(config: str = typer.Option(None, "--config", "-c", help="Path to targets.yaml")) -> None:
    """List configured targets and the models each exposes (metadata only — no model loads)."""
    from gauntlet import enrich
    from gauntlet.config import load_config

    cfg = load_config(config)
    for t in cfg.targets:
        box = cfg.box_for_target(t.name)
        label = box.hardware if box else "(no box)"
        typer.echo(f"\n{t.name}  [{label}]  {t.base_url}")
        fetch = enrich.REGISTRY.get(t.enrich or "")
        if fetch is None:
            typer.echo("  (no enrichment adapter; OpenAI /v1/models only)")
            continue
        try:
            for m in fetch(t.base_url):
                ctx = f"ctx={m.max_context}" if m.max_context else "ctx=?"
                size = f"{m.size_bytes/1e9:.1f}GB" if m.size_bytes else "?GB"
                typer.echo(f"  - {m.id:40s} {m.quant or '?':8s} {size:8s} {ctx}")
        except Exception as exc:  # unreachable target must not crash the listing
            typer.echo(f"  ! unreachable: {exc}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_cli_targets.py -v`
Expected: PASS
Run (live, opt-in, against wraith2): `GAUNTLET_LIVE_OLLAMA=http://<wraith2-host>:11434 .venv/Scripts/python -m pytest tests/live -m live -v`
Expected: PASS (lists wraith2's real models — metadata only, no VRAM use).

- [ ] **Step 5: Commit**

```bash
git add gauntlet/cli.py gauntlet/enrich/__init__.py tests/test_cli_targets.py tests/live/
git commit -m "feat: gauntlet targets command + enrich registry; opt-in live metadata test"
```

---

## Task 2.5: Full-suite green + README dev note

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the entire default suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: ALL PASS, live tests deselected (the `addopts = -m 'not live'` default).

- [ ] **Step 2: Add a short "Developing" section to README**

Append to `README.md`:

```markdown
## Developing

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest            # default suite (no network)
.venv/Scripts/gauntlet targets            # list models per target (metadata only)
```

Live tests are opt-in and metadata-only against a real endpoint:
`GAUNTLET_LIVE_OLLAMA=http://<host>:11434 .venv/Scripts/python -m pytest -m live`.
Never point inference tests at a box someone is gaming on.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: developing section (venv, tests, live metadata)"
```

---

## Self-Review (completed during authoring)

- **Spec coverage (Phases 0–2):** scaffold ✓ (0.1), gitignore hardening ✓ (0.2), contracts+config ✓ (1.1–1.5), client ✓ (2.1), enrichment lmstudio+ollama ✓ (2.2–2.4), out-of-tree config resolution ✓ (1.3), privacy invariant (no base_url field) ✓ (1.5), keep_list glob ✓ (1.2), context_floor applicability ✓ (1.4), busy/usage_class fields present on `Box` ✓ (1.2, consumed by Plan 3 sequencer).
- **Deferred to later plans (intentional, not gaps):** scorecard emission + `--share` + leak assertion → Plan 2; scoring dispatch → Plan 2; sequencer/runner/resume → Plan 3; `run`/`baseline`/`report` commands → Plans 2–4.
- **Placeholder scan:** none — every step carries real code/commands.
- **Type consistency:** `ModelMeta` fields (`id`, `max_context`, `quant`, `size_bytes`, `params`, `vision`, `tool_use`, `loaded`) identical across `lmstudio.py`, `ollama.py`, and tests; `Cell` field names match `models.py` across `test_models.py`; `enrich.REGISTRY` signature `fetch(base_url, transport=None)` consistent in adapters, registry, CLI, and the patched test double.
```
