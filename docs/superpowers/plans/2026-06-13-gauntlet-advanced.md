# Gauntlet Advanced Implementation Plan (Plan 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the build — the two *special* evaluations (context-depth needle-curve, embeddings retrieval), the opt-in frontier baseline, seeded real battery/case content, and the documentation that ties it all together.

**Architecture:** Each special eval is split into a **pure core** (string/vector math, fully TDD'd with no network) and a thin **live runner** driven through the existing `OpenAIClient`. The special evals fill the scorecard contract fields the schema already reserves: `context_depth[]` and `baseline_gaps[]`, plus an `embed` capability `Cell`. New CLI subcommands — `gauntlet depth | embed | baseline` — each write a scorecard, with an optional `--into <existing.json>` to merge a section into a prior run's scorecard. The frontier baseline is **env-key gated**: with no key it prints guidance and exits 0 (never crashes, never runs by default — it costs money).

**Tech Stack:** Python 3.12+, httpx (via `OpenAIClient`), pydantic v2, Typer, PyYAML, jsonschema. Pure-logic TDD for every core; live behavior driven through `httpx.MockTransport` in tests and exercised for real only on box-b (`-m live`) — **never box-a while gaming.**

---

## Phasing & boundaries

- **Phase 8 (Tasks 4.1–4.4):** special batteries — `gauntlet/batteries/context_depth.py` and `gauntlet/batteries/embed.py`. Pure cores + live runners + `gauntlet depth`/`embed` commands.
- **Phase 9 (Tasks 4.5–4.6):** `gauntlet/baseline.py` (pure `compute_gaps`) + `gauntlet baseline` command (env-key gated).
- **Phase 10 (Task 4.7):** seed real `batteries/*.yaml` + `cases/*` (a representative starter set with a documented authoring pattern) + a validation test.
- **Docs (Task 4.8):** README command reference, `batteries/README.md` authoring guide, design-doc status, memory/handoff.

**Invariants carried forward:** `OpenAIClient` is the only thing that does HTTP; every scorecard write goes through `scorecard.write_json` (leak guard + `--share`); the Cell schema still has no base_url field; live tests are `-m live` and never name box-a; nothing aborts a run; unscored is never silently 0.

---

## File Structure

- Create: `gauntlet/batteries/__init__.py` — package marker for the special-runner subpackage.
- Create: `gauntlet/batteries/context_depth.py` — needle-at-depth: pure core (`approx_tokens`, `build_haystack`, `score_retrieval`, `effective_context`) + live `run_context_depth`.
- Create: `gauntlet/batteries/embed.py` — retrieval eval: pure core (`cosine`, `rank_indices`, `recall_at_k`) + live `run_embed_cell`.
- Create: `gauntlet/baseline.py` — pure `compute_gaps`.
- Modify: `gauntlet/scorecard.py` — add `merge_into_scorecard` helper.
- Modify: `gauntlet/cli.py` — add `depth`, `embed`, `baseline` commands.
- Create: `batteries/*.yaml` + `cases/**` — seeded real content.
- Create: `batteries/README.md` — authoring guide.
- Modify: `README.md` — command reference.
- Test: `tests/test_context_depth.py`, `tests/test_embed.py`, `tests/test_baseline.py`, `tests/test_scorecard_merge.py`, `tests/test_cli_advanced.py`, `tests/test_seed_batteries.py`, `tests/live/test_live_advanced.py`.

---

## Task 4.1: Context-depth pure core

**Files:**
- Create: `gauntlet/batteries/__init__.py`, `gauntlet/batteries/context_depth.py`
- Test: `tests/test_context_depth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_depth.py
from gauntlet.batteries.context_depth import (
    DEFAULT_ANSWER,
    approx_tokens,
    build_haystack,
    effective_context,
    score_retrieval,
)


def test_approx_tokens_scales_with_length():
    assert approx_tokens("") >= 1
    assert approx_tokens("a" * 400) == 100   # ~4 chars/token


def test_build_haystack_contains_needle_question_and_target_length():
    prompt = build_haystack(context_tokens=500, depth_fraction=0.5)
    assert DEFAULT_ANSWER in prompt          # the needle answer is embedded
    assert "passcode" in prompt.lower()      # the retrieval question is appended
    # filled to roughly the requested size (within 25%)
    assert 0.75 * 500 <= approx_tokens(prompt) <= 1.5 * 500


def test_build_haystack_depth_places_needle():
    early = build_haystack(context_tokens=400, depth_fraction=0.0)
    late = build_haystack(context_tokens=400, depth_fraction=1.0)
    assert early.index(DEFAULT_ANSWER) < late.index(DEFAULT_ANSWER)


def test_score_retrieval_is_case_insensitive_containment():
    assert score_retrieval("The passcode is cerulean-otter-42.", DEFAULT_ANSWER) is True
    assert score_retrieval("I don't know.", DEFAULT_ANSWER) is False


def test_effective_context_largest_length_at_or_above_threshold():
    # accuracy holds >=0.9 through 8192, collapses after
    samples = [(2048, 1.0), (4096, 0.95), (8192, 0.9), (16384, 0.4), (32768, 0.1)]
    assert effective_context(samples, threshold=0.9) == 8192


def test_effective_context_zero_when_never_meets_threshold():
    assert effective_context([(2048, 0.5), (4096, 0.2)], threshold=0.9) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_context_depth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.batteries'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/batteries/__init__.py
"""Special battery runners — evals that don't fit the per-case score_case flow
(needle-at-depth context curves, embeddings retrieval). Each module exposes a
pure core (TDD'd, no network) plus a thin live runner over OpenAIClient."""
```

```python
# gauntlet/batteries/context_depth.py
"""Needle-at-depth: turn a model's *advertised* context into an *effective* one.

A unique 'needle' fact is buried at a given depth inside filler text sized to a
target context length; the model is asked to retrieve it. Sweeping lengths yields
an accuracy curve, and `effective_context` reduces that curve to the largest length
where retrieval still holds at/above the threshold (the scorecard's effective_90pct).

The core (approx_tokens/build_haystack/score_retrieval/effective_context) is pure
and unit-tested; `run_context_depth` is the only part that touches the network."""
from __future__ import annotations

from gauntlet.models import ContextDepth

DEFAULT_ANSWER = "CERULEAN-OTTER-42"
DEFAULT_NEEDLE = f"Important: the secret passcode for the vault is {DEFAULT_ANSWER}. Remember it."
DEFAULT_QUESTION = ("\n\nQuestion: What is the secret passcode for the vault? "
                    "Answer with ONLY the passcode.")
_FILLER = ("The archivists catalogued another uneventful afternoon in the great "
           "library, shelving ledgers no one would ever read. ")

# ~4 characters per token is the standard coarse heuristic for English text.
_CHARS_PER_TOKEN = 4


def approx_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def build_haystack(
    context_tokens: int,
    depth_fraction: float,
    *,
    needle: str = DEFAULT_NEEDLE,
    question: str = DEFAULT_QUESTION,
    filler: str = _FILLER,
) -> str:
    """Filler sized to ~context_tokens with `needle` inserted at `depth_fraction`
    (0.0 = start, 1.0 = end), then the retrieval `question` appended."""
    target_chars = context_tokens * _CHARS_PER_TOKEN
    reps = max(1, target_chars // len(filler))
    body = filler * reps
    cut = int(len(body) * max(0.0, min(1.0, depth_fraction)))
    haystack = body[:cut] + needle + body[cut:]
    return haystack + question


def score_retrieval(output: str, answer: str = DEFAULT_ANSWER) -> bool:
    return answer.lower() in output.lower()


def effective_context(samples: list[tuple[int, float]], threshold: float = 0.9) -> int:
    """Largest context length whose accuracy is >= threshold; 0 if none qualify."""
    qualifying = [length for length, acc in samples if acc >= threshold]
    return max(qualifying) if qualifying else 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_context_depth.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/batteries/__init__.py gauntlet/batteries/context_depth.py tests/test_context_depth.py
git commit -m "feat: context-depth pure core (build_haystack, score_retrieval, effective_context)"
```

---

## Task 4.2: Context-depth live runner + scorecard merge + `gauntlet depth`

**Files:**
- Modify: `gauntlet/batteries/context_depth.py`
- Modify: `gauntlet/scorecard.py`
- Modify: `gauntlet/cli.py`
- Test: `tests/test_context_depth.py`, `tests/test_scorecard_merge.py`, `tests/test_cli_advanced.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_context_depth.py
import httpx

from gauntlet.batteries.context_depth import DEFAULT_ANSWER, run_context_depth
from gauntlet.client import OpenAIClient


def test_run_context_depth_finds_cutoff(tmp_path=None):
    # Simulate degradation: the model returns the needle only when the prompt is
    # short (<= 6000 chars). Longer haystacks "lose" it -> accuracy collapses.
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        text = DEFAULT_ANSWER if len(body) <= 6000 else "I could not find it."
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}],
                                         "usage": {"completion_tokens": 5}})
    client = OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))
    cd = run_context_depth(client, model="gemma3:1b", advertised=8192,
                           lengths=[500, 1000, 4000], depths=[0.0, 0.5, 1.0])
    assert cd.model == "gemma3:1b"
    assert cd.advertised == 8192
    # 500 & 1000-token prompts stay under 6000 chars (100% retrieval); 4000 tokens
    # (~16000 chars) collapses -> effective_90pct is the largest passing length.
    assert cd.effective_90pct == 1000
```

```python
# tests/test_scorecard_merge.py
import json

from gauntlet.models import ContextDepth, RunMeta, Scorecard
from gauntlet.scorecard import merge_into_scorecard, write_json


def test_merge_into_scorecard_adds_context_depth(tmp_path):
    sc = Scorecard(run=RunMeta(id="r1", date="2026-06-13", gauntlet_version="0.1.0"))
    path = tmp_path / "card.json"
    write_json(sc, path)
    merge_into_scorecard(path, context_depth=[ContextDepth(model="m", advertised=8192,
                                                           effective_90pct=4096)])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["context_depth"][0]["effective_90pct"] == 4096
    assert data["run"]["id"] == "r1"      # existing content preserved
```

```python
# tests/test_cli_advanced.py
import json

from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()


def _config(tmp_path, port=65000):
    cfg = tmp_path / "targets.yaml"
    cfg.write_text(
        "targets:\n"
        f"  - {{name: box-b, base_url: 'http://127.0.0.1:{port}', box: box-b}}\n"
        "boxes:\n"
        "  - {id: box-b, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: broad}\n"
        "models:\n"
        "  - {target: box-b, id: 'gemma3:1b', context: 4096}\n",
        encoding="utf-8",
    )
    return cfg


def test_depth_command_unreachable_writes_zero_curve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _config(tmp_path)
    out = tmp_path / "depth.json"
    result = runner.invoke(app, ["depth", "--config", str(cfg), "--target", "box-b",
                                 "--model", "gemma3:1b", "--max-context", "2048",
                                 "--out", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    # unreachable -> no retrieval -> effective_90pct 0, but the command still emits.
    assert data["context_depth"][0]["effective_90pct"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_context_depth.py::test_run_context_depth_finds_cutoff tests/test_scorecard_merge.py tests/test_cli_advanced.py -v`
Expected: FAIL — `cannot import name 'run_context_depth'` / `merge_into_scorecard` / no `depth` command.

- [ ] **Step 3: Write the implementations**

```python
# add to gauntlet/batteries/context_depth.py
from gauntlet import errors


def run_context_depth(
    client,
    model: str,
    advertised: int,
    lengths: list[int],
    depths: list[float] | None = None,
) -> ContextDepth:
    """Sweep context lengths × needle depths, retrieve, and reduce to effective_90pct.
    A length's accuracy is the mean over depths. Transport failures count as misses
    (accuracy contribution 0) so the run never aborts."""
    depths = depths or [0.1, 0.5, 0.9]
    samples: list[tuple[int, float]] = []
    for length in lengths:
        hits = 0
        for depth in depths:
            prompt = build_haystack(length, depth)
            try:
                reply = client.chat(model=model, prompt=prompt, max_tokens=32)
            except errors.GauntletError:
                continue
            if score_retrieval(reply.text):
                hits += 1
        samples.append((length, hits / len(depths)))
    return ContextDepth(model=model, advertised=advertised,
                        effective_90pct=effective_context(samples))
```

```python
# add to gauntlet/scorecard.py
from gauntlet.models import BaselineGap, ContextDepth  # extend existing model import line


def merge_into_scorecard(
    path: str | Path,
    *,
    cells: list[Cell] | None = None,
    context_depth: list[ContextDepth] | None = None,
    baseline_gaps: list[BaselineGap] | None = None,
    share: bool = False,
) -> None:
    """Load an existing scorecard JSON, append the given sections, and rewrite it
    (through the same leak guard). Lets `depth`/`embed`/`baseline` enrich a prior run."""
    sc = Scorecard.model_validate_json(Path(path).read_text(encoding="utf-8"))
    if cells:
        sc.cells.extend(cells)
    if context_depth:
        sc.context_depth.extend(context_depth)
    if baseline_gaps:
        sc.baseline_gaps.extend(baseline_gaps)
    write_json(sc, path, share=share)
```

> NOTE: `gauntlet/scorecard.py` already imports `from gauntlet.models import CaseResult, Cell, Scorecard`. Change that line to also import `BaselineGap, ContextDepth` rather than adding a duplicate import.

```python
# add to gauntlet/cli.py (new command)
@app.command()
def depth(
    config: str = typer.Option(None, "--config", "-c", help="Path to targets.yaml"),
    target: str = typer.Option(..., "--target", help="Target name from config"),
    model: str = typer.Option(..., "--model", help="Model id to probe"),
    max_context: int = typer.Option(8192, "--max-context", help="Largest context length to probe"),
    out: str = typer.Option(None, "--out", help="Write/merge the scorecard JSON here"),
    into: str = typer.Option(None, "--into", help="Merge the curve into an existing scorecard JSON"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels when writing"),
) -> None:
    """Measure effective context via needle-at-depth retrieval (special battery)."""
    import os
    from datetime import datetime, timezone
    from pathlib import Path

    from gauntlet import __version__
    from gauntlet.batteries.context_depth import run_context_depth
    from gauntlet.client import OpenAIClient
    from gauntlet.config import load_config
    from gauntlet.models import RunMeta, Scorecard
    from gauntlet.scorecard import merge_into_scorecard, render_markdown, write_json

    cfg = load_config(config)
    tgt = cfg.target_by_name(target)
    if tgt is None:
        typer.echo(f"No target named {target!r} in config.")
        raise typer.Exit(code=1)

    # Geometric-ish sweep up to max_context: 512, 1024, ... <= max_context.
    lengths, n = [], 512
    while n <= max_context:
        lengths.append(n)
        n *= 2
    lengths = lengths or [max_context]

    client = OpenAIClient(base_url=tgt.base_url, api_key=os.environ.get("GAUNTLET_API_KEY"))
    try:
        cd = run_context_depth(client, model=model, advertised=max_context, lengths=lengths)
    finally:
        client.close()

    typer.echo(f"{model}: advertised {max_context} -> effective_90pct {cd.effective_90pct}")
    if into:
        merge_into_scorecard(into, context_depth=[cd], share=share)
        typer.echo(f"Merged into {into}")
    if out:
        meta = RunMeta(id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                       date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                       gauntlet_version=__version__)
        write_json(Scorecard(run=meta, context_depth=[cd]), out, share=share)
        typer.echo(f"Scorecard written to {out}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_context_depth.py tests/test_scorecard_merge.py tests/test_cli_advanced.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/batteries/context_depth.py gauntlet/scorecard.py gauntlet/cli.py tests/test_context_depth.py tests/test_scorecard_merge.py tests/test_cli_advanced.py
git commit -m "feat: context-depth live runner, scorecard merge, gauntlet depth command"
```

---

## Task 4.3: Embeddings retrieval — pure core

**Files:**
- Create: `gauntlet/batteries/embed.py`
- Test: `tests/test_embed.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embed.py
from gauntlet.batteries.embed import cosine, rank_indices, recall_at_k


def test_cosine_identical_and_orthogonal():
    assert abs(cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    assert abs(cosine([1.0, 0.0], [0.0, 1.0]) - 0.0) < 1e-9


def test_cosine_zero_vector_is_zero():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_rank_indices_orders_by_similarity():
    query = [1.0, 0.0]
    docs = [[0.0, 1.0], [0.9, 0.1], [1.0, 0.0]]
    assert rank_indices(query, docs) == [2, 1, 0]


def test_recall_at_k_counts_relevant_in_top_k():
    rankings = [[2, 1, 0], [0, 2, 1]]   # per-query ranked doc indices
    relevant = [2, 1]                   # query 0 -> doc 2 (rank 0 hit); query 1 -> doc 1 (rank 2 miss@1)
    assert recall_at_k(rankings, relevant, k=1) == 0.5
    assert recall_at_k(rankings, relevant, k=3) == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_embed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.batteries.embed'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/batteries/embed.py
"""Embeddings retrieval eval. Embed a small corpus + queries, rank docs by cosine
similarity per query, and score recall@k. Pure math is unit-tested; run_embed_cell
is the only network-touching part."""
from __future__ import annotations

import math

from gauntlet.models import Cell


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def rank_indices(query_vec: list[float], doc_vecs: list[list[float]]) -> list[int]:
    """Doc indices ordered by descending cosine similarity to the query."""
    scored = sorted(range(len(doc_vecs)),
                    key=lambda i: cosine(query_vec, doc_vecs[i]), reverse=True)
    return scored


def recall_at_k(rankings: list[list[int]], relevant: list[int], k: int = 1) -> float:
    """Fraction of queries whose relevant doc appears in the top-k ranked docs."""
    if not rankings:
        return 0.0
    hits = sum(1 for ranked, rel in zip(rankings, relevant) if rel in ranked[:k])
    return hits / len(rankings)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_embed.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/batteries/embed.py tests/test_embed.py
git commit -m "feat: embeddings retrieval pure core (cosine, rank_indices, recall_at_k)"
```

---

## Task 4.4: Embeddings live runner + `gauntlet embed`

**Files:**
- Modify: `gauntlet/batteries/embed.py`
- Modify: `gauntlet/cli.py`
- Test: `tests/test_embed.py`, `tests/test_cli_advanced.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_embed.py
import httpx

from gauntlet.batteries.embed import run_embed_cell
from gauntlet.client import OpenAIClient


def _embed_client(vectors):
    # Returns the next len(inputs) vectors from a fixed map keyed by input text.
    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        payload = _json.loads(request.content.decode())
        data = [{"embedding": vectors[text]} for text in payload["input"]]
        return httpx.Response(200, json={"data": data})
    return OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))


def test_run_embed_cell_scores_recall():
    vectors = {
        "doc about cats": [1.0, 0.0, 0.0],
        "doc about dogs": [0.0, 1.0, 0.0],
        "doc about cars": [0.0, 0.0, 1.0],
        "feline pet": [0.9, 0.1, 0.0],     # closest to cats
        "automobile": [0.0, 0.1, 0.9],     # closest to cars
    }
    corpus = ["doc about cats", "doc about dogs", "doc about cars"]
    queries = ["feline pet", "automobile"]
    relevant = [0, 2]                      # cats=0, cars=2
    client = _embed_client(vectors)
    cell = run_embed_cell(client, model="nomic-embed", target="box-b",
                          box="RTX 2070 Super laptop", context=2048,
                          corpus=corpus, queries=queries, relevant=relevant)
    assert cell.capability == "embed"
    assert cell.quality == 1.0            # both queries retrieve the right doc @k=1
    assert cell.cases == 2
```

```python
# append to tests/test_cli_advanced.py
def test_embed_command_missing_corpus_exits_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _config(tmp_path)
    result = runner.invoke(app, ["embed", "--config", str(cfg), "--target", "box-b",
                                 "--model", "nomic-embed", "--corpus", str(tmp_path / "nope.yaml")])
    assert result.exit_code != 0
    assert "corpus" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_embed.py::test_run_embed_cell_scores_recall "tests/test_cli_advanced.py::test_embed_command_missing_corpus_exits_cleanly" -v`
Expected: FAIL — `cannot import name 'run_embed_cell'` / no `embed` command.

- [ ] **Step 3: Write the implementations**

```python
# add to gauntlet/batteries/embed.py
from gauntlet import errors


def run_embed_cell(
    client,
    model: str,
    target: str | None,
    box: str,
    context: int,
    corpus: list[str],
    queries: list[str],
    relevant: list[int],
    k: int = 1,
) -> Cell:
    """Embed corpus + queries, rank, score recall@k into an `embed` Cell. A transport
    failure yields an errored cell with quality None (never silently 0)."""
    try:
        doc_vecs = client.embeddings(model=model, inputs=corpus)
        q_vecs = client.embeddings(model=model, inputs=queries)
    except errors.GauntletError:
        return Cell(model=model, target=target, box=box, context=context,
                    capability="embed", quality=None, pass_rate=None,
                    cases=len(queries), errors=1)
    rankings = [rank_indices(q, doc_vecs) for q in q_vecs]
    recall = recall_at_k(rankings, relevant, k=k)
    return Cell(model=model, target=target, box=box, context=context,
                capability="embed", quality=recall, pass_rate=recall,
                cases=len(queries), errors=0)
```

```python
# add to gauntlet/cli.py (new command)
@app.command()
def embed(
    config: str = typer.Option(None, "--config", "-c", help="Path to targets.yaml"),
    target: str = typer.Option(..., "--target", help="Target name from config"),
    model: str = typer.Option(..., "--model", help="Embedding model id"),
    corpus: str = typer.Option("cases/embed/corpus.yaml", "--corpus",
                               help="YAML with keys: corpus[], queries[], relevant[]"),
    k: int = typer.Option(1, "--k", help="recall@k"),
    out: str = typer.Option(None, "--out", help="Write the scorecard JSON here"),
    into: str = typer.Option(None, "--into", help="Merge the embed cell into an existing scorecard"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels when writing"),
) -> None:
    """Evaluate an embedding model by retrieval recall@k over a small corpus."""
    import os
    from datetime import datetime, timezone
    from pathlib import Path

    import yaml

    from gauntlet import __version__
    from gauntlet.batteries.embed import run_embed_cell
    from gauntlet.client import OpenAIClient
    from gauntlet.config import load_config
    from gauntlet.models import RunMeta, Scorecard
    from gauntlet.scorecard import merge_into_scorecard, write_json

    cpath = Path(corpus)
    if not cpath.exists():
        typer.echo(f"Embed corpus file not found: {corpus}")
        raise typer.Exit(code=1)
    spec = yaml.safe_load(cpath.read_text(encoding="utf-8"))

    cfg = load_config(config)
    tgt = cfg.target_by_name(target)
    if tgt is None:
        typer.echo(f"No target named {target!r} in config.")
        raise typer.Exit(code=1)
    box = cfg.box_for_target(target)

    client = OpenAIClient(base_url=tgt.base_url, api_key=os.environ.get("GAUNTLET_API_KEY"))
    try:
        cell = run_embed_cell(client, model=model, target=target,
                              box=box.hardware if box else "(no box)", context=0,
                              corpus=spec["corpus"], queries=spec["queries"],
                              relevant=spec["relevant"], k=k)
    finally:
        client.close()

    typer.echo(f"{model}: embed recall@{k} = {cell.quality}")
    if into:
        merge_into_scorecard(into, cells=[cell], share=share)
        typer.echo(f"Merged into {into}")
    if out:
        meta = RunMeta(id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                       date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                       gauntlet_version=__version__)
        write_json(Scorecard(run=meta, cells=[cell]), out, share=share)
        typer.echo(f"Scorecard written to {out}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_embed.py tests/test_cli_advanced.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/batteries/embed.py gauntlet/cli.py tests/test_embed.py tests/test_cli_advanced.py
git commit -m "feat: embeddings live runner + gauntlet embed command"
```

---

## Task 4.5: Frontier baseline — pure `compute_gaps`

**Files:**
- Create: `gauntlet/baseline.py`
- Test: `tests/test_baseline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_baseline.py
from gauntlet.models import Cell
from gauntlet.baseline import compute_gaps


def _cell(model, capability, quality):
    return Cell(model=model, target="t", box="b", context=4096,
                capability=capability, quality=quality, pass_rate=quality, cases=5)


def test_compute_gaps_picks_local_champion_per_capability():
    local = [
        _cell("small-a", "commit-msg", 0.80),
        _cell("small-b", "commit-msg", 0.88),   # champion for commit-msg
        _cell("small-c", "extract-json", 0.50),
    ]
    frontier = [
        _cell("claude", "commit-msg", 0.91),
        _cell("claude", "extract-json", 0.95),
    ]
    gaps = {g.capability: g for g in compute_gaps(local, frontier)}
    assert gaps["commit-msg"].local_champion == "small-b"
    assert abs(gaps["commit-msg"].gap - 0.03) < 1e-9      # 0.91 - 0.88
    assert gaps["extract-json"].local_champion == "small-c"
    assert abs(gaps["extract-json"].gap - 0.45) < 1e-9


def test_compute_gaps_ignores_capabilities_without_frontier():
    local = [_cell("small-a", "ocr", 0.4)]
    frontier = [_cell("claude", "commit-msg", 0.9)]
    assert compute_gaps(local, frontier) == []


def test_compute_gaps_skips_unscored_local_cells():
    local = [_cell("scored", "commit-msg", 0.7),
             Cell(model="unscored", target="t", box="b", context=4096,
                  capability="commit-msg", quality=None, pass_rate=None, cases=5)]
    frontier = [_cell("claude", "commit-msg", 0.9)]
    gaps = compute_gaps(local, frontier)
    assert len(gaps) == 1
    assert gaps[0].local_champion == "scored"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_baseline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.baseline'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/baseline.py
"""Frontier baseline gap analysis (pure). Given local cells and frontier cells,
report per capability: the local champion (highest scored quality) and the gap to
the frontier model. Capabilities the frontier didn't cover are skipped; unscored
local cells (quality None) are ignored — a baseline must not overstate confidence."""
from __future__ import annotations

from gauntlet.models import BaselineGap, Cell


def compute_gaps(local: list[Cell], frontier: list[Cell]) -> list[BaselineGap]:
    frontier_by_cap = {c.capability: c for c in frontier if c.quality is not None}
    gaps: list[BaselineGap] = []
    for capability, fcell in frontier_by_cap.items():
        candidates = [c for c in local
                      if c.capability == capability and c.quality is not None]
        if not candidates:
            continue
        champion = max(candidates, key=lambda c: c.quality)
        gaps.append(BaselineGap(
            capability=capability,
            local_champion=champion.model,
            frontier=fcell.model,
            gap=fcell.quality - champion.quality,
        ))
    return gaps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_baseline.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/baseline.py tests/test_baseline.py
git commit -m "feat: frontier baseline compute_gaps (local champion vs frontier, skip unscored)"
```

---

## Task 4.6: `gauntlet baseline` command (env-key gated)

**Files:**
- Modify: `gauntlet/cli.py`
- Test: `tests/test_cli_advanced.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_cli_advanced.py
import os


def _battery_dir(tmp_path):
    bdir = tmp_path / "batteries"
    bdir.mkdir(exist_ok=True)
    (tmp_path / "p.txt").write_text("write a conventional commit", encoding="utf-8")
    (bdir / "commit.yaml").write_text(
        "capability: commit-msg\ncontext_floor: 0\n"
        "cases:\n  - {id: c1, scoring: conventional-commit, prompt_file: p.txt}\n",
        encoding="utf-8")
    return bdir


def test_baseline_without_key_is_skipped_not_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GAUNTLET_FRONTIER_API_KEY", raising=False)
    bdir = _battery_dir(tmp_path)
    result = runner.invoke(app, ["baseline", "--capability", "commit-msg", "--sample", "1",
                                 "--batteries", str(bdir), "--prompts", str(tmp_path),
                                 "--frontier-url", "http://127.0.0.1:65000/v1",
                                 "--frontier-model", "frontier-x"])
    assert result.exit_code == 0
    assert "GAUNTLET_FRONTIER_API_KEY" in result.output      # clear guidance


def test_baseline_with_key_runs_and_writes_gaps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAUNTLET_FRONTIER_API_KEY", "sk-test")
    bdir = _battery_dir(tmp_path)
    # a local scorecard with one commit-msg cell to compare against
    local = tmp_path / "local.json"
    local.write_text(json.dumps({
        "run": {"id": "r", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
        "cells": [{"model": "small-a", "target": "t", "box": "b", "context": 4096,
                   "capability": "commit-msg", "quality": 0.7, "pass_rate": 0.7,
                   "cases": 1, "errors": 0}],
        "context_depth": [], "baseline_gaps": [],
    }), encoding="utf-8")
    out = tmp_path / "with_gaps.json"

    # Patch the frontier client factory to a MockTransport returning a good commit.
    import httpx

    import gauntlet.cli as cli_mod

    def fake_client(base_url, api_key=None):
        def handler(request):
            return httpx.Response(200, json={"choices": [{"message": {"content": "feat: add x"}}],
                                             "usage": {"completion_tokens": 4}})
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(cli_mod, "_frontier_client", fake_client, raising=False)

    result = runner.invoke(app, ["baseline", "--capability", "commit-msg", "--sample", "1",
                                 "--batteries", str(bdir), "--prompts", str(tmp_path),
                                 "--frontier-url", "http://f/v1", "--frontier-model", "frontier-x",
                                 "--local", str(local), "--into", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["baseline_gaps"][0]["capability"] == "commit-msg"
    assert data["baseline_gaps"][0]["local_champion"] == "small-a"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_cli_advanced.py -k baseline -v`
Expected: FAIL — no `baseline` command.

- [ ] **Step 3: Write the implementation**

```python
# add to gauntlet/cli.py — a patchable client factory + the command

def _frontier_client(base_url: str, api_key: str | None = None):
    """Frontier endpoint client. Separated so tests can patch it with a MockTransport."""
    from gauntlet.client import OpenAIClient
    return OpenAIClient(base_url=base_url, api_key=api_key)


@app.command()
def baseline(
    capability: str = typer.Option(..., "--capability", help="Capability to baseline (battery capability)"),
    sample: int = typer.Option(3, "--sample", help="Number of cases to sample from the battery"),
    batteries: str = typer.Option("batteries", "--batteries", help="Directory of battery YAML files"),
    prompts: str = typer.Option(".", "--prompts", help="Base dir for case prompt/schema files"),
    frontier_url: str = typer.Option(..., "--frontier-url", help="Frontier OpenAI-compatible base URL"),
    frontier_model: str = typer.Option(..., "--frontier-model", help="Frontier model id"),
    local: str = typer.Option(None, "--local", help="Local scorecard JSON to compare against"),
    into: str = typer.Option(None, "--into", help="Write baseline_gaps into this scorecard JSON"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels when writing"),
) -> None:
    """Opt-in frontier comparison. Costs money — gated behind GAUNTLET_FRONTIER_API_KEY;
    with no key set it prints guidance and exits without calling anything."""
    import os
    from pathlib import Path

    from gauntlet.baseline import compute_gaps
    from gauntlet.battery import load_batteries
    from gauntlet.models import Scorecard
    from gauntlet.runner import run_cell
    from gauntlet.scorecard import merge_into_scorecard

    key = os.environ.get("GAUNTLET_FRONTIER_API_KEY")
    if not key:
        typer.echo("Frontier baseline is opt-in and costs money. Set GAUNTLET_FRONTIER_API_KEY "
                   "to enable it. Skipped.")
        raise typer.Exit(code=0)

    bats = {b.capability: b for b in load_batteries(batteries)}
    battery = bats.get(capability)
    if battery is None:
        typer.echo(f"No battery for capability {capability!r} in {batteries}/.")
        raise typer.Exit(code=1)

    # Sample N cases into a sub-battery.
    sampled = battery.model_copy(update={"cases": battery.cases[:max(1, sample)]})

    client = _frontier_client(frontier_url, api_key=key)
    try:
        fcell = run_cell(client, model=frontier_model, target=None, box="frontier",
                         context=0, battery=sampled, base_dir=prompts)
    finally:
        client.close()
    typer.echo(f"frontier {frontier_model}: {capability} quality = {fcell.quality}")

    local_cells = []
    if local:
        sc = Scorecard.model_validate_json(Path(local).read_text(encoding="utf-8"))
        local_cells = sc.cells
    gaps = compute_gaps(local_cells, [fcell])
    for g in gaps:
        typer.echo(f"  gap[{g.capability}] champion={g.local_champion} vs {g.frontier}: {g.gap:+.3f}")

    if into:
        merge_into_scorecard(into, cells=[fcell], baseline_gaps=gaps, share=share)
        typer.echo(f"Merged baseline into {into}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_cli_advanced.py -k baseline -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/cli.py tests/test_cli_advanced.py
git commit -m "feat: gauntlet baseline command (env-key gated frontier comparison, baseline_gaps)"
```

---

## Task 4.7: Seed real batteries + cases (representative starter set)

**Files:**
- Create: `batteries/commit-msg.yaml`, `batteries/extract-json.yaml`, `batteries/code-gen.yaml`, `batteries/summarize-short.yaml`
- Create: `cases/commit-msg/diff-01.txt`, `cases/extract-json/invoice-01.txt`, `cases/extract-json/invoice-01.schema.json`, `cases/code-gen/fizzbuzz.txt`, `cases/summarize-short/article-01.txt`, `cases/embed/corpus.yaml`
- Test: `tests/test_seed_batteries.py`

> This task seeds a **representative starter set** that exercises every deterministic scorer plus a judge case and the embed corpus — enough for a genuine first scorecard. The remaining capabilities from the taxonomy (summarize-long, synthesize, write-* registers, code-transform, ocr) follow the same authoring pattern documented in `batteries/README.md` (Task 4.8) and are added incrementally.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_batteries.py
from pathlib import Path

import yaml

from gauntlet.battery import load_batteries

ROOT = Path(__file__).resolve().parents[1]


def test_seeded_batteries_load_clean():
    bats = {b.capability: b for b in load_batteries(ROOT / "batteries")}
    # every seeded capability parses
    assert {"commit-msg", "extract-json", "code-gen", "summarize-short"} <= set(bats)
    # each battery has at least one case
    assert all(b.cases for b in bats.values())


def test_seeded_case_prompt_files_exist():
    bats = load_batteries(ROOT / "batteries")
    for b in bats:
        for case in b.cases:
            if case.prompt_file:
                assert (ROOT / case.prompt_file).exists(), case.prompt_file
            if case.schema_file:
                assert (ROOT / case.schema_file).exists(), case.schema_file


def test_embed_corpus_is_well_formed():
    spec = yaml.safe_load((ROOT / "cases/embed/corpus.yaml").read_text(encoding="utf-8"))
    assert len(spec["queries"]) == len(spec["relevant"])
    assert all(0 <= i < len(spec["corpus"]) for i in spec["relevant"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_seed_batteries.py -v`
Expected: FAIL — batteries dir / files don't exist yet.

- [ ] **Step 3: Create the seeded content**

`batteries/commit-msg.yaml`:
```yaml
capability: commit-msg
context_floor: 0
cases:
  - id: diff-01
    prompt_file: cases/commit-msg/diff-01.txt
    scoring: conventional-commit
weights: { quality: 1.0 }
```

`cases/commit-msg/diff-01.txt`:
```
Write a single Conventional Commits subject line (type(scope): summary) for this diff. Output ONLY the line.

diff --git a/auth.py b/auth.py
@@
-    return verify(token)
+    if token is None:
+        raise ValueError("missing token")
+    return verify(token)
```

`batteries/extract-json.yaml`:
```yaml
capability: extract-json
context_floor: 0
cases:
  - id: invoice-01
    prompt_file: cases/extract-json/invoice-01.txt
    scoring: json-schema
    schema_file: cases/extract-json/invoice-01.schema.json
weights: { quality: 1.0 }
```

`cases/extract-json/invoice-01.txt`:
```
Extract the invoice as JSON with keys invoice_no (string) and total (number). Output ONLY JSON.

INVOICE A-1007
Consulting services .... $ 4250.00
Total due: $4250.00
```

`cases/extract-json/invoice-01.schema.json`:
```json
{
  "type": "object",
  "required": ["invoice_no", "total"],
  "properties": {
    "invoice_no": { "type": "string" },
    "total": { "type": "number" }
  }
}
```

`batteries/code-gen.yaml`:
```yaml
capability: code-gen
context_floor: 0
cases:
  - id: fizzbuzz
    prompt_file: cases/code-gen/fizzbuzz.txt
    scoring: compilable-code
weights: { quality: 1.0 }
```

`cases/code-gen/fizzbuzz.txt`:
```
Write a Python function fizzbuzz(n) that returns the FizzBuzz string for n. Output ONLY a Python code block.
```

`batteries/summarize-short.yaml`:
```yaml
capability: summarize-short
context_floor: 0
cases:
  - id: article-01
    prompt_file: cases/summarize-short/article-01.txt
    scoring: judge
    rubric: "Score 0-1: is this a faithful one-sentence summary that names the main subject and the key fact, with no invented details?"
weights: { quality: 1.0 }
```

`cases/summarize-short/article-01.txt`:
```
Summarize the following in ONE sentence.

The city council voted 6-1 on Tuesday to fund a new pedestrian bridge over the river, with construction expected to begin next spring and finish within eighteen months.
```

`cases/embed/corpus.yaml`:
```yaml
corpus:
  - "A cat is a small domesticated feline kept as a pet."
  - "A dog is a loyal domesticated canine and common companion animal."
  - "An automobile is a wheeled motor vehicle used for transportation."
queries:
  - "feline house pet"
  - "car for getting around"
relevant: [0, 2]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_seed_batteries.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add batteries/ cases/ tests/test_seed_batteries.py
git commit -m "feat: seed representative batteries + cases (commit-msg, extract-json, code-gen, summarize-short, embed corpus)"
```

---

## Task 4.8: Documentation

**Files:**
- Create: `batteries/README.md`
- Modify: `README.md`
- Modify: `docs/2026-06-12-gauntlet-build-design.md` (status note)

- [ ] **Step 1: Write the battery authoring guide**

Create `batteries/README.md`:
```markdown
# Batteries — authoring guide

A **battery** is one capability's test suite: a `batteries/<capability>.yaml` file
plus its prompt/schema files under `cases/<capability>/`. `gauntlet run` loads
every `batteries/*.yaml`; a battery runs against a load profile only when the
profile's context >= the battery's `context_floor`.

## Schema

```yaml
capability: extract-json        # unique capability name (the scorecard groups by this)
context_floor: 4096             # profiles below this context skip this battery
cases:
  - id: invoice-01              # unique within the battery
    prompt_file: cases/extract-json/invoice-01.txt   # the user prompt (relative to --prompts)
    scoring: json-schema        # see scorers below
    schema_file: cases/extract-json/invoice-01.schema.json   # json-schema only
  - id: messy-03
    prompt_file: cases/extract-json/messy-03.txt
    scoring: judge              # LLM-graded
    rubric: "Score 0-1: completeness and correctness, no invented fields."
weights: { quality: 1.0 }
```

## Scorers (deterministic preferred)

| `scoring` | needs | passes when |
|---|---|---|
| `exact` | `expect` | output equals `expect` (trimmed, fences stripped) |
| `regex` | `pattern` | `pattern` found in output |
| `json-schema` | `schema_file` | output parses and validates against the schema |
| `conventional-commit` | — | output is a valid Conventional Commits subject |
| `compilable-code` | — | output is a syntactically compilable code block |
| `judge` | `rubric` | a different-family judge model scores it >= 0.5 |

Prefer deterministic scorers; reserve `judge` for open-ended quality. A judge never
grades its own model family, and an unjudgeable case is recorded `unscored` (never 0).

## Special batteries (own commands, not `gauntlet run`)

- **context-depth:** `gauntlet depth --target T --model M --max-context N` —
  needle-at-depth retrieval, fills `context_depth[]`.
- **embed:** `gauntlet embed --target T --model M --corpus cases/embed/corpus.yaml` —
  retrieval recall@k, emits an `embed` cell.
```

- [ ] **Step 2: Update `README.md` with a command reference**

Add a `## Commands` section to `README.md` documenting:
```markdown
## Commands

| command | what it does |
|---|---|
| `gauntlet targets` | list configured targets + models (metadata only, no model loads) |
| `gauntlet run` | sequence the work matrix and run batteries against live targets; resumable |
| `gauntlet depth` | measure effective context via needle-at-depth (special battery) |
| `gauntlet embed` | evaluate an embedding model by retrieval recall@k |
| `gauntlet baseline` | opt-in frontier comparison (gated by `GAUNTLET_FRONTIER_API_KEY`) |
| `gauntlet report` | render a scorecard JSON to Markdown (with `--share` to sanitize) |

### Overnight run (example)

```bash
gauntlet run --config <private targets.yaml> --out scorecards/$(date +%F).json
gauntlet depth  --target box-b --model gemma3:1b --max-context 8192 --into scorecards/$(date +%F).json
gauntlet embed  --target box-b --model nomic-embed --into scorecards/$(date +%F).json
gauntlet report scorecards/$(date +%F).json --share
```

**Resource safety:** real inference must target a headless box. Do not run inference
against a box you are gaming on — mark it `busy: true` in config to defer its cells.
```

- [ ] **Step 3: Add a status note to the build design doc**

Add near the top of `docs/2026-06-12-gauntlet-build-design.md` (under the title):
```markdown
> **Build status (2026-06-13):** Plans 1–4 implemented. Phases 0–10 complete —
> foundation, scoring, scorecard, runner+resume, special batteries (context-depth,
> embed), frontier baseline, and seeded starter batteries. See
> `docs/superpowers/plans/` for the per-plan task breakdowns.
```

- [ ] **Step 4: Verify docs render and links are valid**

Run: `.venv/Scripts/python -m pytest`  (full suite still green; docs are prose, no test)
Then visually confirm `README.md` and `batteries/README.md` render as intended.

- [ ] **Step 5: Commit**

```bash
git add README.md batteries/README.md docs/2026-06-12-gauntlet-build-design.md
git commit -m "docs: command reference, battery authoring guide, build-status note (Plans 1-4 complete)"
```

---

## Manual live verification (optional, box-b only)

```bash
# PowerShell — box-b endpoints only; NEVER box-a while gaming.
$env:GAUNTLET_LIVE_BASE_URL = "http://<box-b>:11434"
.venv/Scripts/python -m pytest tests/live -m live -v
# and a real special-battery smoke:
.venv/Scripts/python -m gauntlet.cli depth --config <private> --target box-b --model gemma3:1b --max-context 8192
```

---

## Self-review notes (coverage vs design phases 8–10)

- **Phase 8 (Special batteries):** context-depth needle→effective-context curve (4.1 pure core + 4.2 runner/command), embeddings retrieval recall@k (4.3 pure core + 4.4 runner/command). Both fill their scorecard sections via `merge_into_scorecard`. ✅
- **Phase 9 (Frontier baseline):** `compute_gaps` local-champion-vs-frontier, skipping unscored (4.5); `gauntlet baseline --capability X --sample N`, env-key gated with a clean skip path + mocked-key run filling `baseline_gaps` (4.6). ✅
- **Phase 10 (Seed batteries/cases):** representative starter set across every deterministic scorer + a judge case + embed corpus, with a documented authoring pattern for the rest (4.7). ✅
- **Docs:** command reference, authoring guide, build-status note (4.8). ✅
- **Invariants:** all scorecard writes go through `write_json`/`merge_into_scorecard` (leak guard + `--share`); special-eval live behavior is MockTransport-tested and the real path is `-m live`/box-b-only; baseline never runs without an explicit key; unscored stays unscored (embed/baseline both honor it). ✅
```

