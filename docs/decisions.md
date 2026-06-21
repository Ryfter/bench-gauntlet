# Decisions

In-repo decision log (this project keeps its reasoning with the code, not in an
external knowledge base). The original product decisions live in
[`2026-06-11-gauntlet-design.md`](2026-06-11-gauntlet-design.md) (the 8 decisions)
and the architecture in [`2026-06-12-gauntlet-build-design.md`](2026-06-12-gauntlet-build-design.md).
This file records cross-cutting and post-build decisions.

---

## D-2026-06-13a — Gauntlet is standalone; no external knowledge-base dependency
**Decision:** Gauntlet has no build/runtime/process dependency on any other repo.
All design, decisions, and lessons live in this repo. The repo's `CLAUDE.md` was
rewritten from a pointer at an external coding knowledge base into a self-contained
agent guide.

**Why:** Gauntlet is meant to be a public, standalone app that autonomously
benchmarks local LLMs. Its scores are fed back into [Baton](https://github.com/Ryfter/baton)
to guide picking local LLMs as tools — but that is a *consumer* relationship, not a
dependency. Hanging an external-KB dependency on it would couple a clean standalone
tool to private tooling and leak a private local path into the public tree.

**Consequences:** New architecture/coding decisions are recorded here under
`docs/`. Nothing references or writes to an external KB.

---

## D-2026-06-13b — Special evals are dedicated subcommands, not auto-dispatched in `gauntlet run`
**Decision:** Context-depth and embeddings retrieval are run by their own CLI
subcommands (`gauntlet depth`, `gauntlet embed`), and the frontier baseline by
`gauntlet baseline` — not folded into `gauntlet run`'s per-case loop. Each fills its
own scorecard section (`context_depth[]`, an `embed` cell, `baseline_gaps[]`), and
`scorecard.merge_into_scorecard` lets a special command enrich a prior run's
scorecard.

**Why:** These evals don't fit the `Case` → `score_case(output)` flow that `run`
is built on. Context-depth sweeps synthetic prompts across lengths/depths and
reduces a curve; embeddings rank a corpus by cosine similarity; the baseline calls a
paid external endpoint. Modelling each as a "special battery" with a pure core +
thin live runner keeps `runner.py` simple, keeps every core unit-testable without a
network, and keeps the paid/opt-in path (baseline) explicitly separate from the
default run.

**Consequences:** An overnight flow is `run` then the special commands, each
merging into the same scorecard JSON (see README "Overnight run"). The frontier
baseline is gated behind `GAUNTLET_FRONTIER_API_KEY` and never runs by default.

---

## D-2026-06-15a — Judge exclusion flag (`judge: false` on ModelProfile)
**Decision:** Added a `judge: false` flag to `ModelProfile`. Any model with this flag
is excluded from the judge candidate pool in `_judge_pool_for()`, even if it is
otherwise eligible (correct family, available on the target).

**Why:** Some models produce judge verdicts that are systematically garbled — malformed
JSON, wrong keys, non-numeric scores — poisoning the pool and causing `score_with_judge()`
to record spurious `unscored` results. Removing such models from the test roster is too
blunt (their generation quality is still worth benchmarking). The flag lets them be
benchmarked as subjects while being excluded as judges. `tavernari/git-commit-message`
was the first model that triggered this.

**Consequences:** `_judge_pool_for` filters on `p.judge` (defaults `True`). The field
is documented in `config.py`. Test suite updated.

---

## D-2026-06-21a — Think-tag stripping before all scoring paths
**Decision:** `runner.py` strips `<think>…</think>` blocks (compiled regex,
case-insensitive, dotall) from model output before it reaches any scorer — both
deterministic (`score_case`) and judge (`score_with_judge`). Applied in `run_cell()`
immediately after the API reply is received.

**Why:** Thinking models (qwen3:30b, openthinker:32b) wrap chain-of-thought in
`<think>…</think>`. Without stripping, deterministic scorers see the thinking block as
part of the output: `compilable-code` fails compilation, `conventional-commit` rejects
valid subjects buried after the block, `json-schema` fails parse, and judge models
receive verbose thinking output that breaks strict-JSON verdict parsing. The fix must
be applied universally — not per-scorer — because a scorer has no knowledge of which
model produced the output. The same stripping is applied to judge outputs before JSON
verdict parse (that path was caught and fixed independently, a commit earlier).

**Consequences:** Thinking models now score on their final answer only, which is the
correct measurement. No change to battery authoring; the stripping is invisible to
case definitions.

---

## D-2026-06-21b — Token metrics and cost-savings reporting
**Decision:** Added `prompt_tokens`, `completion_tokens`, and `ttft_p50_s` to `Cell`;
`pricing.py` holds a frontier pricing table with current Anthropic and OpenAI tiers;
`savings_summary()` renders a cost-equivalent Markdown section appended to every
scorecard report. `tokens_per_s` corrected to use completion tokens only. Default
comparison baselines: Claude Sonnet 4.6 + Claude Haiku 4.5 (user-selected).

**Why:** The core value proposition is "how much does local inference save vs. paying a
frontier API?" Without token counts and a pricing reference, a scorecard can only
answer *how good* a local model is — not *how much it saves*. Token counts are
returned in the OpenAI `/v1/chat/completions` `usage` field at no extra cost.
`tokens_per_s` was previously computed as `total_tokens / latency`, which overstates
generation throughput — prompt tokens are processed, not generated; the correct metric
is `completion_tokens / latency`. TTFT is wired through `ChatResult` → `Cell` but
only populated when streaming (deferred to a later pass).

**Consequences:** `pricing.py` must be kept current as frontier prices change. The
savings section appears in Markdown reports only — not in the JSON contract (the JSON
carries raw token counts; the Markdown renders the dollar math). The `--compare` flag
on `gauntlet report` overrides the default baseline pair. `DEFAULT_COMPARE` is
`["claude-sonnet-4-6", "claude-haiku-4-5"]`.

---

## D-2026-06-13c — Privacy remediation: scrub committed IP, rewrite history, recreate remote
**Decision:** A real Tailscale IP had been committed to tracked files (the
scorecard leak-guard test fixtures and config examples). Remediation: replace it in
HEAD with placeholders (`<box-b-host>` in docs) and TEST-NET `203.0.113.10` in
test fixtures; rewrite git history (`git filter-repo --replace-text`) to purge it
from every commit; and recreate the private GitHub remote from the clean local
history so no merged-PR ref retains the old commits.

**Why:** The standing privacy rule is that personal network info must be
*physically incapable* of entering the public tree, not merely gitignored. Even
though the IP is a non-routable tailnet (CGNAT `100.64.0.0/10`) address in a private
repo — so real exposure was negligible — the repo is intended to go public, and the
clean-slate fix is cheap on a young repo with no stars/forks.

**Consequences:** Reinforced in `CLAUDE.md`: never commit a real IP/host — use
`<box-b-host>` placeholders in docs and TEST-NET (`203.0.113.0/24`) in test
fixtures. The leak guard (`scorecard.assert_no_leak`) remains the automated backstop
on emitted scorecards.

---

## D-2026-06-21c — SSE streaming for TTFT measurement
**Decision:** `OpenAIClient.chat()` switches from a blocking `httpx.post()` to an SSE
stream (`stream=True` + `stream_options: {include_usage: true}`). The timestamp of the
first content chunk is captured as `ttft_s`; text is assembled from deltas; token
counts are extracted from the final `usage` chunk.

**Why:** `ttft_p50_s` was wired through `ChatResult` → `Cell` but always `null`
because the blocking path reads the full response at once — there is no "first token"
event. SSE streaming provides that event. TTFT is the latency that matters most for
interactive use cases (code completion, chat), where waiting for the first word is
the primary UX bottleneck, distinct from throughput (tokens/sec).

**Consequences:** All MockTransport test handlers that serve chat completions must
return SSE-formatted bodies. A shared `tests/helpers.py` module provides the `sse()`
builder to reduce per-test boilerplate. The `stream_options.include_usage` field is
required to keep token counts available; not all endpoints support it (they silently
omit `usage`), in which case `prompt_tokens` / `completion_tokens` remain `None`.

---

## D-2026-06-21e — `gauntlet add-case` interactive CLI helper
**Decision:** Added `gauntlet add-case <capability>` — an interactive command that
collects case ID, scoring method, scorer-specific params, and prompt text from the
terminal, then writes the prompt file and appends a YAML case block to the existing
battery file. Prompt text is multiline (blank-line-terminated) unless `--from-file` is
given. All single-line fields use `typer.prompt()`; multiline prompt reads via
`sys.stdin.readline()` in a loop, which is correctly mocked by typer's `CliRunner`.

**Why:** Writing batteries by hand requires knowing the YAML schema, creating the
prompt file in the right directory, and avoiding duplicate IDs — error-prone friction
that slows down case authoring. A CLI guide eliminates all three problems and is
consistent with how the rest of the tool works (no external tools required). Battery
authoring remains a core loop: run the tool, notice a gap, add a case, re-run.

**Design choices:**
- YAML is updated by string-surgery (insert before `\nweights:`) rather than
  yaml.dump/load, to preserve the existing file's formatting (indentation, flow-style
  `weights:` line). The only edge case is `cases: []` (empty flow sequence), detected
  with a regex and replaced with a block-style list.
- Scalar values are single-quoted via `_yaml_scalar()` so backslash-heavy regex
  patterns survive the round-trip without double-escaping (YAML single-quoted strings
  are fully literal — no backslash escapes).
- `--batteries` and `--prompts` default to `batteries` and `.` (same as `gauntlet run`)
  so the command works from the repo root without flags.

**Consequences:** `gauntlet add-case` covers all six scoring methods. `batteries/README.md`
authoring guide is still the reference for manual authoring; add-case is the fast path.
10 new tests; test suite 117 → 127.

---

## D-2026-06-21d — Battery matrix expansion (code-debug, reasoning, classify)
**Decision:** Added three new batteries covering capabilities not in the original four
(commit-msg, code-gen, extract-json, summarize-short):

- **code-debug:** 4 cases testing bug identification and repair — missing `return`,
  wrong operator, index error, logic inversion. Three cases use `regex` to verify the
  specific fix; one uses `compilable-code`.
- **reasoning:** 4 cases of arithmetic / logical deduction with exact numeric or
  single-word answers. All scored with `exact`.
- **classify:** 5 cases of single-label classification (sentiment, topic, urgency,
  intent routing) with exact lowercase answers.

**Why:** The original four batteries measured code generation, structured extraction,
commit formatting, and summarization. Reasoning ability and instruction-following
under label constraints are qualitatively different skills; a model that excels at
code-gen may perform poorly on multi-step arithmetic or constrained classification.
Bug-fixing specifically tests whether a model can diagnose incorrect logic — a high
value skill for tool routing.

**Consequences:** Battery count grows from 4 to 7. `test_seeded_batteries_load_clean`
updated to assert the three new capabilities. The `exact` scorer is intentionally
strict — a model outputting "The sentiment is positive" instead of "positive" fails,
which is the correct measurement (instruction-following failure). Case prompts include
explicit format instructions ("Output ONLY the number/word, lowercase, nothing else")
to make the expected format unambiguous.
