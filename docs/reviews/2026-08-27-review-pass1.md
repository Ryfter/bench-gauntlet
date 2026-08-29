# bench-gauntlet skeptical review — pass 1

Date: 2026-08-27  
Branch reviewed: `feat/codegen-execution-scorer`  
Disposition: defects only

## Test and review evidence

- Read `CLAUDE.md` and `AGENTS.md` before reviewing source.
- Traced all first-party Python imports of HTTP/socket libraries, all scorecard/checkpoint write paths, every CLI inference entry point, all scorer dispatch paths, both planners, and the relevant tests.
- Safe full suite: `PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider --basetemp=/tmp/bench-gauntlet-pytest-safe` → **757 passed, 8 skipped, 4 deselected** in 24.62 s.
- The first run with the ordinary environment reached `tests/test_cli_run.py` and invoked the installed `lms` CLI from a non-live test. Process inspection later showed that pytest's process group was executing `lms unload gemma3:1b`; that exact group was terminated. This is finding H-14, not a product-test failure.
- Reproduction snippets used only temporary directories under `/tmp`; no source files were modified.

## Finding counts

| Severity | Count |
|---|---:|
| CRITICAL | 2 |
| HIGH | 14 |
| MEDIUM | 8 |
| LOW | 0 |

**LOW: no findings.** Lower-severity observations were not included merely to pad the report.

## CRITICAL findings

### C-1 — Personal host/device identifiers are already committed, and raw run files rely on gitignore rather than structural exclusion

- **Status:** CONFIRMED
- **Evidence:** `CLAUDE.md:21-27`; `gauntlet/vram.py:37-53`; `tests/test_vram_lms_ps.py:21-25,36-61,77-80`; `BATON.md:15-19`; `docs/decisions/D-2026-06-30a-firefly-vram-contention.md:1-7`; `.gitignore:4-8`; `gauntlet/runner.py:47-50,124-149`.
- **Failure scenario:** The public tree contains a named workstation/device and a specific work-PC hostname (`ITSCM-KRANK2`), plus operational target names. Separately, each run writes the private `target` directly into `scorecards/<run>/cells.jsonl` and `cases.jsonl`. Those files are merely ignored. `git add -f`, an archive of the working tree, or a misconfigured publishing job can publish them unchanged. This directly contradicts the hard rule that personal network details be physically incapable of entering the public tree and that docs use placeholders.
- **Why tests miss it:** `tests/test_models.py:4-7` only proves `Cell` lacks a `base_url` field. `tests/test_runstatus.py:55-67` only checks the status marker. `tests/test_vram_lms_ps.py:21-61` actively pins the private identifiers as expected fixtures. There is no tracked-tree privacy scan and no assertion that checkpoint writers reject or redact private targets.
- **How to reproduce:** Run `git ls-files -z | xargs -0 rg -n -i 'firefly|wraith2|itscm|hostname'`. Then inspect a local `scorecards/*/{cells,cases}.jsonl`; `append_cell` and `append_case_rows` serialize `target` without a guard.

### C-2 — Candidate code can forge the sandbox verdict and return an arbitrary score outside `[0,1]`

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/scoring/execute.py:45-47,53-54,82-98,323-331,349-395`; `gauntlet/scoring/_guard.py:145-170`; `gauntlet/models.py:12-29`.
- **Failure scenario:** Candidate code runs in the same interpreter before `hidden.check(ns)`. It can replace `builtins.print`. `_emit()` later calls that patched function for the supposedly trusted final verdict. A candidate that emits no solution can write `{"status":"ok","passed":7,"total":1,"violations":[]}` to `sys.__stdout__`; the parent accepts the last JSON line and computes `7 / 1 == 7.0`. No model/result validation bounds the value. The reproduced result was `score=7.0`, `failure_mode=wrong_answer`; changing `passed` to `1` produces a forged perfect pass.
- **Why tests miss it:** `tests/test_scoring_execute.py:31-160` covers ordinary correct/wrong/timeout/file behavior only. `tests/test_integrity.py:111-133` covers canary echoing but not mutation of trusted runner globals. `tests/test_case_validation.py:82-102` validates maintainer reference/mutant solutions, not hostile or accidental mutations of `print`, `json.dumps`, `sum`, or `len`.
- **How to reproduce:** Create a hidden test whose `check` returns `[False, False]`; submit candidate source that assigns `builtins.print` to a function writing a forged `status=ok` JSON line through `sys.__stdout__`; call `code_execution_match`. The current scorer returns the forged ratio, including values greater than 1.

## HIGH findings

### H-1 — `--share` accepts IPv6, bare hostnames, and host:port values, and only removes one field

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/scorecard.py:15-16,118-138,145-179`; `gauntlet/models.py:32-66`; `tests/test_scorecard_json.py:19-42`; `tests/test_cli_report.py:29-37`.
- **Failure scenario:** `_LEAK_RE` recognizes only dotted IPv4 and a URL scheme. `assert_no_leak` accepted all reproduced inputs: `fd00::1`, `workstation`, `workstation:11434`, and mixed-case `WoRkStAtIoN:11434`. `to_dict(..., share=True)` removes only `Cell.target`; it leaves host-like values in `run.id`, `box`, `model`, `judge`, context-depth model IDs, and baseline fields. A mislabeled hardware field or run ID therefore survives a shared JSON/Markdown export. The rejection path also includes `match.group()` in its error, so a rejected endpoint is copied into logs/tracebacks.
- **Why tests miss it:** `tests/test_scorecard_json.py:31-42` tests only IPv4/URL and a clean fixture. `tests/test_cli_report.py:29-37` asserts only that `target` disappears. There are no IPv6, no-dot hostname, host:port, mixed-case, nested-field, or error-message tests.
- **How to reproduce:** Call `assert_no_leak(json.dumps({"box": value}))` for the four values above; all return normally. Build a scorecard with `box="workstation:11434"`, call `to_dict(sc, share=True)`, and observe the value remains.

### H-2 — The single-HTTP-component invariant is false

- **Status:** CONFIRMED
- **Evidence:** `CLAUDE.md:28-30`; `gauntlet/enrich/lmstudio.py:3,28-33`; `gauntlet/enrich/ollama.py:3,27-32`; `gauntlet/client.py:28-47`; `gauntlet/cli.py:29-50`.
- **Failure scenario:** Both enrichment adapters construct their own `httpx.Client` and perform GET requests outside `OpenAIClient`. This bypasses the client’s error taxonomy, centralized auth, timeout policy, and integrity checks. Any future boundary control added to `OpenAIClient` will not cover `/api/v1/models` or `/api/tags`.
- **Why tests miss it:** `tests/test_enrich_lmstudio.py` and `tests/test_enrich_ollama.py` exercise only pure parsers. `tests/test_cli_targets.py:8-29` replaces the adapter with a lambda, so it specifically avoids the offending HTTP implementation. There is no architectural import check.
- **How to reproduce:** Run `rg -n '\bhttpx\b' gauntlet --glob '*.py'`. Production imports appear in both enrichers in addition to `client.py`.

### H-3 — Prompt-leak and response-tool integrity controls are tested but disconnected from production

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/integrity.py:50-75,78-113`; `gauntlet/client.py:49-93`; `gauntlet/runner.py:197-238`; `gauntlet/scoring/execute.py:280-304`; `tests/test_integrity.py:36-108`.
- **Failure scenario:** `assert_no_prompt_leak` and `response_used_tools` have no production callers. A custom code-exec case can place hidden assertions verbatim in its prompt and still score. Separately, an SSE choice carrying both `content="positive"` and `tool_calls` with `finish_reason="tool_calls"` is accepted by `OpenAIClient`; the content can receive a perfect deterministic score. The request-side field check does not detect server-injected tool use.
- **Why tests miss it:** `tests/test_integrity.py:38-108` invokes the helpers directly, proving helper behavior rather than integration. No test patches either helper to fail if the real run path omits it. `tests/test_case_validation.py:59-79` checks only the committed registry at build time; runtime/custom batteries bypass it.
- **How to reproduce:** Patch `gauntlet.integrity.assert_no_prompt_leak` to raise and run a code-exec cell; the patch call count remains zero and the cell scores. Feed `OpenAIClient` an SSE delta containing both content and `tool_calls`; `chat()` returns the content and finish reason without an integrity error.

### H-4 — `busy: true` is not a universal inference guard

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/config.py:15-28,45-55`; `gauntlet/sequencer.py:33-56,114-126`; `gauntlet/cli.py:337-354,400-414`; `tests/test_config_models.py:38-43`; `tests/test_sequencer.py:88-99`.
- **Failure scenario:** `gauntlet depth` and `gauntlet embed` resolve a target and immediately call it; neither checks `cfg.box_for_target(target).busy`. In the main planner, a target with no `box`, a typoed box ID, or an otherwise unresolved mapping gets `box=None` and is scheduled exclusively rather than rejected. The main CLI also loads config and computes the plan once, so changing the config to `busy: true` during a multi-hour run does not stop later profiles.
- **Why tests miss it:** Busy tests cover only `sequencer.plan_run`. `tests/test_config_models.py:38-43` labels the fail-open `busy=False` default “safe.” `tests/test_cli_advanced.py:24-43` exercises depth/embed without a busy box case. There is no end-to-end assertion that every inference entry point consults the busy flag immediately before a call.
- **How to reproduce:** Use a config whose target maps to `Box(..., busy=True)` and invoke `depth` or `embed` with a fake client that records calls; calls still occur. Alternatively omit `Target.box` and run `plan_run`; the cells appear in `groups`, not `deferred`.

### H-5 — An all-busy run still clears the local GPU before doing zero work

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/runner.py:284-306,310-320,383-391`; `gauntlet/vram.py:128-137`; `tests/test_sequencer.py:88-99`.
- **Failure scenario:** `plan_run` correctly returns no groups for a busy box, but `execute_plan` unconditionally calls `vram.unload_all_local()` when `exclusive_vram=True` before checking whether any cell is runnable. A user marks the machine busy because it is being used interactively, starts Gauntlet by mistake, and Gauntlet unloads the resident local model despite scheduling no inference.
- **Why tests miss it:** The busy test stops at the pure planner. `tests/test_runner_execute.py:32-68` has no busy configuration and does not assert VRAM calls. No test covers an empty runnable plan with exclusive VRAM enabled.
- **How to reproduce:** Patch `gauntlet.runner.vram.unload_all_local`, execute a plan whose only box is busy, and inspect the mock: call count is 1 while returned cells are empty.

### H-6 — Parallel orchestration races destructive global VRAM operations across workers

- **Status:** PLAUSIBLE
- **Evidence:** `gauntlet/orchestrate.py:21-48,63-81`; `gauntlet/runner.py:301-308,332-382,383-389`; `gauntlet/vram.py:128-137,214-251`; `docs/decisions/D-2026-06-30a-firefly-vram-contention.md:5-16`.
- **Failure scenario:** Every target worker calls `execute_plan(..., exclusive_vram=True)` against the same process/machine. Each worker independently clears all local models, loads/unloads profiles, and snapshots/releases VRAM. Worker B can unload a model Worker A just loaded or is actively benchmarking. On two serving stacks sharing one GPU, this causes request failures, wrong latency/throughput, or OOM; the decision note’s claim that box splitting plus `busy` makes orchestration safe is undermined by H-5 because even the busy worker clears VRAM.
- **Why tests miss it:** `tests/test_orchestrate.py` tests only `compact_summary`; no test executes two `_run_target` workers with synchronized VRAM mocks. Runner tests are single-threaded.

### H-7 — Same-family judge exclusion is defeated by real model naming variants

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/sequencer.py:17-20`; `gauntlet/runner.py:227-235,261-265`; `gauntlet/scoring/judge.py:38-44`; `tests/test_sequencer.py:32-35`; `tests/test_scoring_judge.py:46-53`.
- **Failure scenario:** `model_family` is merely the substring before the first colon. `google/gemma-3-12b-it-Q4_K_M` becomes `google/gemma-3-12b-it-q4_k_m`, while `gemma3:12b` becomes `gemma3`; they are eligible to judge one another despite being the same family. Provider prefixes, hyphenation, quantization suffixes, aliases, and fine-tune names all evade the guard. A Llama fine-tune such as `dolphin3:8b` is likewise treated as unrelated to its Llama base.
- **Why tests miss it:** `tests/test_sequencer.py:32-35` validates the oversimplified split. `tests/test_scoring_judge.py:46-48` manually supplies `("dolphin3:8b", "llama")`, but production `_judge_pool_for` derives that family as `dolphin3`; the test constructs a state production cannot produce.
- **How to reproduce:** Compare `model_family('google/gemma-3-12b-it-Q4_K_M')` with `model_family('gemma3:12b')`; they differ, so `select_judge` accepts the alias.

### H-8 — Unscored cases are reintroduced as failures in `pass_rate`, and transport-unscored coverage is reported as complete

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/scorecard.py:33-35`; `gauntlet/runner.py:205-211`; `scripts/analyze_fleet.py:378-400`; `tests/test_scorecard_aggregate.py:22-29`; `tests/test_runner_cell.py:97-106`.
- **Failure scenario:** A cell with one pass and one unjudgeable case has honest `quality=1.0` but `pass_rate=0.5`; an all-unjudgeable judge cell reports `pass_rate=0.0`. That is a second score channel silently treating unknown as failure. Worse, transport errors carry no `failure_mode`, while fleet coverage subtracts only three named unscored modes. A cell that scored one case and lost nine to HTTP failures can display 100% coverage and a quality of 1.0.
- **Why tests miss it:** `tests/test_scorecard_aggregate.py:22-29` and `tests/test_runner_cell.py:97-106` explicitly pin the buggy pass-rate behavior. Coverage tests do not include transport-error `CaseResult`s without a failure mode.
- **How to reproduce:** Aggregate `[CaseResult(score=1, passed=True), CaseResult(score=None, passed=False)]`; current output is `(quality=1.0, pass_rate=0.5)`. Build a cell with `cases=10`, `errors=9`, no failure modes, and call `scripts.analyze_fleet.coverage`; it returns 1.0.

### H-9 — Three seeded deterministic batteries award high/full scores to meaningless output

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/scoring/exact.py:8-13`; `gauntlet/scoring/schema.py:10-41`; `batteries/code-debug.yaml:4-26`; `batteries/commit-msg.yaml:4-27`; `batteries/extract-json.yaml:4-19`; `cases/extract-json/invoice-01.schema.json:1-8`; `tests/test_scoring_schema.py:14-40`; `tests/test_seed_batteries.py:40-62`.
- **Failure scenario:**
  - `logic-inversion` uses `compilable-code`; an empty string compiles and scores 1.0.
  - Regex debug cases accept prose such as “The correction is to use `width * height`; code omitted.”
  - The same generic `feat: x` passes every commit-message case, including required `revert`, `perf`, and breaking-change/footer tasks.
  - Content-free typed JSON such as `{"invoice_no":"","total":0}` passes invoice extraction because schemas validate shape, not source facts. Equivalent dummy objects pass the other schemas.
- **Why tests miss it:** Scorer tests prove syntax/pattern/schema mechanics, not case semantics. `tests/test_seed_batteries.py:40-62` checks only that required fields exist and schemas are syntactically valid. Unlike code-exec, these batteries have no reference-positive and degenerate-negative validation gate.
- **How to reproduce:** Call the current scorer for the four outputs above against the named cases; each returns true. The reproduced calls returned `True` for empty compilation, generic commit, prose regex, and dummy invoice JSON.

### H-10 — Context-depth scoring is defeated by prompt echo and turns network faults into model failure

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/batteries/context_depth.py:15-18,48-55,58-81`; `tests/test_context_depth.py:30-42`; `tests/test_cli_advanced.py:24-34`.
- **Failure scenario:** The answer token is literally present in every prompt, and `score_retrieval` only checks whether that token appears anywhere in output. A model/server that echoes the prompt earns 100% at every depth without retrieving anything. Separately, every `GauntletError` is counted as a miss, so a complete network outage produces `effective_90pct=0`, falsely claiming the model has no usable context.
- **Why tests miss it:** `tests/test_context_depth.py:30-32` deliberately pins substring containment and never tests prompt echo. `tests/test_cli_advanced.py:24-34` explicitly asserts that an unreachable endpoint writes a zero curve, thereby treating the transport bug as expected behavior.
- **How to reproduce:** `score_retrieval(build_haystack(2048, .5))` returns true because the prompt contains the answer. A fake client that always raises `errors.Unreachable` passed to `run_context_depth` returns `effective_90pct=0` (reproduced).

### H-11 — HTTP protocol/embedding failures are either scored as wrong answers or escape and abort the command

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/client.py:65-105,126-139`; `gauntlet/runner.py:203-238`; `gauntlet/batteries/embed.py:46-58`; `tests/test_client.py:47-60,63-76`; `tests/test_cli_advanced.py:84-104`.
- **Failure scenario:** Malformed/non-SSE `200 OK` chat responses are silently ignored line by line, yielding empty text that deterministic scorers mark 0.0 rather than unscored. The baseline test itself returns non-streaming JSON to a streaming client, so its supposed “good commit” becomes empty. For embeddings, only `ConnectError` is translated; `ReadTimeout`, HTTP 4xx/5xx, invalid JSON, missing `data`, and malformed rows escape `run_embed_cell` because it catches only `GauntletError`, aborting the CLI instead of producing an unscored cell.
- **Why tests miss it:** `tests/test_client.py:47-60` treats a no-content stream as ordinary but does not distinguish protocol corruption. The baseline test asserts only gap metadata, not the frontier cell’s score. Embedding tests cover only success and `ConnectError`, not other `httpx` exceptions or malformed 200 responses.
- **How to reproduce:** Feed `chat()` a normal non-streaming completion JSON with HTTP 200; it returns empty text. Feed `run_embed_cell` an `OpenAIClient` whose mock transport raises `httpx.ReadTimeout`; the exception escapes as `ReadTimeout`, not `GauntletError` (reproduced).

### H-12 — Checkpoints are non-atomic; a torn line blocks resume, and the case-before-cell order duplicates rows after a crash

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/runner.py:47-50,124-160,240-244,373-375,395-404`; `gauntlet/scorecard.py:135-139,182-199`; `scripts/analyze_fleet.py:43-58`; `tests/test_runner_checkpoint.py:14-35`; `tests/test_scorecard_dimensions.py:52-82`.
- **Failure scenario:** `append_cell`, `append_case_rows`, metadata writes, and scorecard rewrites use direct writes with no temp-file/rename or recovery. A kill/power loss can leave a partial JSONL line; `read_completed`, `assemble_scorecard`, and `analyze_fleet.load_jsonl` then fail on the entire run. Also, `run_cell` appends case rows before its cell checkpoint. A crash in between causes resume to rerun the cell and append duplicate cases, skewing per-case means and counts.
- **Why tests miss it:** Tests cover only complete happy-path lines and celebrate append-only behavior. None injects a torn final line, an exception between case and cell writes, duplicate rows, or a failed overwrite.
- **How to reproduce:** Write `{"model":"partial"` to `cells.jsonl` and call `read_completed`; it raises a Pydantic `ValidationError` (reproduced). Append cases without a cell, resume, and observe the same case keys twice in `cases.jsonl`.

### H-13 — The execution sandbox has no memory/CPU/output limits and no OS-level filesystem/network confinement

- **Status:** PLAUSIBLE
- **Evidence:** `gauntlet/scoring/execute.py:146-156,214-255,316-340`; `gauntlet/scoring/_guard.py:14-23,47-67,126-170`; `docs/2026-07-25-benchmark-integrity-threat-model.md:42-75,98-120`.
- **Failure scenario:** The child has a wall-clock timeout, but no address-space, resident-memory, file-size, process-count, or CPU-time limit. `communicate()` buffers unbounded stdout/stderr in the parent. Candidate code can allocate until the OS starts swapping/OOM-killing, print enough data to exhaust parent memory before timeout, or use `ctypes`/raw syscalls to bypass Python-level file/socket patches. A wedged Windows `taskkill` also has no timeout at `execute.py:231-236`.
- **Why tests miss it:** `tests/test_scoring_execute.py:81-87` covers a CPU loop timeout only. `tests/test_integrity.py` covers patched Python APIs. No test constrains RSS/output, exercises `ctypes`, validates network namespace/firewall behavior, or makes `taskkill` hang.

### H-14 — The default non-live test suite can query, unload, and load real workstation models

- **Status:** CONFIRMED
- **Evidence:** `tests/test_cli_run.py:38-48`; `tests/test_runner_execute.py:32-66`; `gauntlet/runner.py:301-308,332-382`; `gauntlet/vram.py:128-137,160-168,214-251`; `pyproject.toml:31-36`.
- **Failure scenario:** Ordinary unit tests call `execute_plan` with the default `exclusive_vram=True` and do not mock `vram`. If `lms` is installed, pytest executes real `lms ps`, `lms unload`, and `lms load` commands. During this review, the normal suite first stalled at `tests/test_cli_run.py` and later process inspection showed `lms unload gemma3:1b` running under pytest; removing `lms` from `PATH` made the full suite complete in 24.62 seconds. On a developer box, the suite can evict an interactive model or load a benchmark model despite live tests being opt-in.
- **Why tests miss it:** There is no autouse fixture forbidding external commands/network in non-live tests. Runner tests mock HTTP only, leaving resource-control subprocesses real.
- **How to reproduce:** On a machine with `lms` installed, run the documented pytest command and observe `lms` subprocesses at `test_cli_run`/`test_runner_execute`. Compare with `PATH=/usr/bin:/bin ... pytest`, which avoids those calls and completes promptly.

## MEDIUM findings

### M-1 — Judge verdict parsing accepts `NaN`, booleans, strings, and contradictory pass flags

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/scoring/judge.py:24-35`; `tests/test_scoring_judge.py:9-43`.
- **Failure scenario:** `float(data["score"])` plus `max/min` maps `"NaN"` to 1.0 under the current operand order. `bool(data["passed"])` maps the JSON string `"false"` to `True`. A verdict `{"score":0,"passed":"false"}` therefore records a failed quality score but a passed case; `{"score":"NaN"}` becomes `(1.0, True)`.
- **Why tests miss it:** Tests cover ordinary floats, omission, fences, and bad JSON only. They do not validate JSON types, finiteness, score/pass consistency, or reject extra/malformed values.
- **How to reproduce:** Call `parse_verdict('{"score":"NaN"}')` and `parse_verdict('{"score":0,"passed":"false"}')`; reproduced outputs were `(1.0, True)` and `(0.0, True)`.

### M-2 — Embedding math silently scores malformed vector/count responses

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/batteries/embed.py:12-32,35-59`; `gauntlet/client.py:132-139`; `tests/test_embed.py:4-55`; `tests/test_seed_batteries.py:65-68`.
- **Failure scenario:** `cosine` uses `zip`, so different-dimensional vectors are silently truncated; `cosine([1,0], [1])` returns 1.0. `recall_at_k` zips rankings with labels but divides by `len(rankings)`; one returned query vector for two requested queries can score 1.0 based only on the first. NaN/Inf vectors and invalid relevant indices/k values are also unvalidated.
- **Why tests miss it:** Tests use equal dimensions and equal list lengths. The seed-data check validates the static corpus only, not server response shape.
- **How to reproduce:** The two calls above returned 1.0: `cosine([1.0,0.0],[1.0])` and `recall_at_k([[0]],[0,1],1)`.

### M-3 — A cell larger than every box is scheduled anyway

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/toc_scheduler.py:74-92,119-158`; `tests/test_toc_scheduler.py:144-157,207-221,343-348`; `docs/2026-08-21-toc-scheduler-usage.md:1-3,16-31`.
- **Failure scenario:** `_place_tight` starts a new batch whenever the open batch cannot fit, but never checks whether the cell itself exceeds box VRAM. Heavy and critical placement ignore footprint completely. An 80 GB cell is scheduled exclusively on an 8 GB box with nothing deferred, guaranteeing load failure/retry starvation once wired.
- **Why tests miss it:** Overflow tests cover three individually fitting 4 GB cells on a 10 GB box. No test uses a single impossible footprint. `test_tight_cell_without_vram_footprint_is_exclusive` treats unknown as runnable rather than probing impossible capacity.
- **How to reproduce:** `plan_placement([TocBox(id='tiny',vram_gb=8,usage_class='tight')], [TocCell(...,vram_gb=80,estimated_cost=1)])` returns one batch on `tiny` and zero deferred cells (reproduced).

### M-4 — The advertised surface-constraint checker is dead code

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/scoring/constraints.py:1-20,25-36,111-129`; `gauntlet/battery.py:26-37`; `gauntlet/scoring/__init__.py:58-93`; `tests/test_scoring_constraints.py:1-70`.
- **Failure scenario:** `Case` has no `constraints` field, `score_case` never calls `check_constraints`, and `CaseResult` has no structured constraint result. A case asking for “no imports” or “must use a generator” can functionally pass while violating the instruction, despite the module claiming violations are reported separately.
- **Why tests miss it:** Every constraint test calls the helper directly. There is no battery-load, dispatch, runner, or scorecard integration test; deleting the production wiring is impossible to detect because no wiring exists.
- **How to reproduce:** Run `rg -n 'check_constraints|constraints:' gauntlet batteries cases/code-gen/registry.json`; the only production occurrence is the helper definition, and no case schema can carry the field.

### M-5 — Battery weights are accepted but ignored

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/battery.py:40-54`; `gauntlet/scorecard.py:19-46`; `gauntlet/runner.py:245-256`; `batteries/README.md:1-23`.
- **Failure scenario:** A battery author sets non-default weights expecting the documented scoring knob to affect aggregation. `aggregate_cell` always takes an unweighted arithmetic mean and never receives the `Battery`. Even `{quality: 0}` or multiple future components have no effect, so configuration silently lies.
- **Why tests miss it:** All seeded batteries use `{quality: 1.0}`. No test varies weights or asserts they reach aggregation.
- **How to reproduce:** Construct two otherwise identical batteries with different `weights`, score the same results through `run_cell`, and compare cells; quality is identical. `rg -n 'weights' gauntlet` shows the field is never consumed outside model/loading code unrelated to battery weights.

### M-6 — Equal-scoring champions are nondeterministic under parallel orchestration

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/orchestrate.py:66-81,85-111`; `tests/test_orchestrate.py:12-58`.
- **Failure scenario:** `as_completed` makes `all_cells` order depend on thread completion. `compact_summary` resolves ties with `max` on `(quality, pass_rate)` only, so the first equal cell wins. Two equal models can alternate as “champion” across runs even with identical measurements.
- **Why tests miss it:** Tests have strict quality winners and no tie case. They do not permute input or simulate different future-completion orders.
- **How to reproduce:** Call `compact_summary` with equal cells `[a,b]`, then `[b,a]`; the reproduced champion changed from `a` to `b`.

### M-7 — Empty/invalid fleets are accepted by config and crash orchestration outside the typed cell-outcome model

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/config.py:39-55,84-95`; `gauntlet/orchestrate.py:63-69`; `gauntlet/runner.py:342-346`; `tests/test_config_models.py:38-43`; `tests/test_orchestrate.py:1-58`.
- **Failure scenario:** `GauntletConfig()` is valid with zero models, but `orchestrate` constructs `ThreadPoolExecutor(max_workers=0)` and raises `ValueError`. A `ModelProfile.target` that names no configured target is also accepted; execution can load a model and then crash at `tgt.base_url` because `tgt` is `None`. Neither becomes a deferred/unscored typed outcome.
- **Why tests miss it:** Orchestration tests cover only the pure summary formatter. Config tests do not validate referential integrity or empty fleets.
- **How to reproduce:** `orchestrate(GauntletConfig(), [], 'r', '.', None)` raises `ValueError: max_workers must be greater than 0` (reproduced). A model pointing at a missing target reaches an `AttributeError` in `execute_plan`.

### M-8 — The frontier-key invariant is enforced only by the CLI caller, not by the frontier client boundary

- **Status:** CONFIRMED
- **Evidence:** `gauntlet/cli.py:493-496,499-529,540-545`; `gauntlet/client.py:31-47`; `tests/test_cli_advanced.py:57-71,84-104`.
- **Failure scenario:** `_frontier_client` defaults `api_key=None` and creates a usable client without checking `GAUNTLET_FRONTIER_API_KEY`; the only guard is an `if not key` in the Typer command. Any internal caller, imported helper, future retry/resume path, or direct invocation below the CLI can run the frontier baseline without the required environment credential. A whitespace-only environment value also passes the CLI truthiness check and reaches the request path.
- **Why tests miss it:** The no-key test exercises only the CLI happy guard. The with-key test replaces `_frontier_client` with a fake that ignores `api_key` and never asserts the key received, so it would pass if key propagation were deleted.
- **How to reproduce:** Call `_frontier_client('http://placeholder.invalid', api_key=None)`; it returns an `OpenAIClient` rather than refusing. Set `GAUNTLET_FRONTIER_API_KEY` to whitespace and patch `_frontier_client` with a recording fake; the baseline command invokes it.

## Test-quality defects called out by finding

The most consequential weak or misleading tests are:

- `tests/test_scorecard_aggregate.py:22-29` and `tests/test_runner_cell.py:97-106` pin unscored cases as pass-rate failures (H-8).
- `tests/test_cli_advanced.py:24-34` pins a network outage as zero effective context (H-10).
- `tests/test_cli_advanced.py:84-104` mocks a streaming API with non-SSE JSON and never checks the frontier score, so it passes while the “good commit” is discarded (H-11).
- `tests/test_integrity.py:36-108` tests helpers directly but never proves the production client/runner calls them (H-3).
- `tests/test_scoring_constraints.py:1-70` comprehensively tests a helper that has no production caller or schema field (M-4).
- `tests/test_toc_scheduler.py:362-378` computes `order` and never asserts it; the test name promises critical→heavy→cheap ordering but checks only the first critical item and set membership (M-3/M-6).
- `tests/test_case_validation.py:82-102` proves only one hand-picked mutant per case is caught; it does not challenge the harness with verdict forgery, global monkeypatching, prompt echo, or generic constants (C-2/H-9).
- `tests/test_cli_run.py:38-48` and `tests/test_runner_execute.py:32-66` mock HTTP but leave real VRAM subprocesses enabled (H-14).
- `tests/test_runner_checkpoint.py:14-35`, `tests/test_runner_assemble.py:10-20`, and `tests/test_scorecard_dimensions.py:52-82` cover only complete writes; they cannot detect torn lines, crash windows, or resume duplication (H-12).

## Highest-priority untested branches

1. Candidate mutation of runner globals and forged sandbox output.
2. Busy enforcement in `depth`, `embed`, all-busy `execute_plan`, and busy changes during a run.
3. Runtime prompt-leak and response-tool detection through the actual client/runner path.
4. IPv6/bare-host/host:port leakage across every shared field and error path.
5. Partial JSONL recovery and idempotent per-case resume.
6. Every `httpx` exception and malformed-200 response for chat and embeddings.
7. Same-family aliases using provider prefixes, quantization/fine-tune suffixes, and casing/hyphen variants.
8. Single-cell VRAM impossibility, negative/NaN scheduling costs, and retry accounting once ToC is wired.
9. RSS/stdout/process-count exhaustion and Windows timeout teardown failure.
10. Equal-score deterministic tie-breaking and empty-fleet orchestration.
