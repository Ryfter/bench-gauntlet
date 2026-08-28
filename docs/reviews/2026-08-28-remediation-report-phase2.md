# Remaining HIGH/MEDIUM remediation report (phase 2)

Date: 2026-08-28  
Branch: `fix/review-remaining` (from `fix/review-critical-high`)  
Scope: consolidated findings 24–26 (the unfinished HIGH items) and 27–37 (all 11 MEDIUM)

Prior phase: `docs/reviews/2026-08-28-remediation-report.md` (3 CRITICAL + 17 HIGH). This increment does not redo that work and does not attempt findings 10, 11, or 23.

## FIXED

1. **Non-atomic/non-idempotent persistence — H-12/P2-21** — `6eed9c0`. Snapshots (`meta.json`, scorecard JSON/Markdown) go through temp-file/`os.replace`. `cells.jsonl` and `cases.jsonl` are keyed upserts, so a torn tail is skipped and a crash between case rows and the cell marker cannot duplicate evidence on resume. `analyze_fleet.load_jsonl` also skips unparseable lines. Regressions: `test_read_completed_skips_torn_trailing_line`, `test_assemble_scorecard_skips_torn_trailing_line`, `test_append_cell_is_idempotent_for_the_same_key`, `test_append_case_rows_is_idempotent_for_the_same_case_key`, `test_write_meta_crash_before_commit_keeps_prior_snapshot`, `test_write_json_crash_before_commit_keeps_prior_snapshot`, `test_execute_plan_resume_after_case_rows_without_cell_does_not_duplicate`, `test_load_jsonl_skips_a_torn_trailing_line`.

2. **Sandbox resource limits — H-13** — `4a0220c`. Best-effort CPU/memory/process caps via POSIX rlimits or `prlimit` where they work, a Windows Job Object, a parent-side RSS watchdog (macOS rejects `RLIMIT_AS` from this Python), capped stdout/stderr reads, and a timeout on Windows `taskkill`. Comments keep the documented claim that this is host-stability containment, not a security boundary. Regressions: `test_sandbox_output_flood_does_not_score_as_success`, `test_sandbox_memory_bomb_does_not_score_as_success`, `test_kill_tree_bounds_windows_taskkill`.

3. **Default tests can operate LM Studio — H-14** — `87dce42`. Autouse non-live guard in `tests/conftest.py` blocks `lms`/`ollama` subprocesses and remote sockets (localhost still allowed for refused-connection tests). `tests/test_cli_run.py` now injects every VRAM operation and disables the overlay. Remaining unit `execute_plan` / `vram.*` call sites were audited: runner tests already stubbed VRAM; `test_runstatus` stubs unload; live tests keep `pytest.mark.live`. Regressions: `test_non_live_tests_cannot_invoke_lms`, `test_non_live_tests_cannot_invoke_ollama_cli`, `test_non_live_tests_cannot_open_remote_sockets`.

4. **Judge verdict parsing — M-1** — `42ca185`. Score must be a finite JSON number; `passed` must be a JSON boolean when present; contradictory pass flags raise. Regressions: `test_parse_verdict_rejects_non_finite_score`, `test_parse_verdict_rejects_string_passed_and_coercive_types`, `test_parse_verdict_rejects_contradictory_pass_flag`.

5. **Embedding dimension/count mismatches — M-2** — `293b16c`. `cosine` and `recall_at_k` reject unequal lengths and non-finite components instead of truncating with `zip`. `run_embed_cell` requires matching corpus/query/response counts and equal dimensions. Regressions: `test_cosine_rejects_dimension_mismatch_and_non_finite`, `test_recall_at_k_rejects_count_mismatch`. Constant-vector rejection also landed in this commit (used by M-3).

6. **Constant embeddings and unconstrained k — M-3** — `a38fd5a` (CLI/chance baseline; library checks in `293b16c`). `1 <= k < corpus_size` is enforced at the CLI and library boundary; constant embedding sets become unscored; the embed command prints a chance recall@k baseline. Regressions: `test_run_embed_cell_rejects_constant_vectors`, `test_run_embed_cell_rejects_k_covering_the_corpus`, `test_embed_command_rejects_k_covering_the_corpus`.

7. **ToC oversized cells — M-4** — `97db171`. Known footprints are checked against the selected box before every placement; impossible cells defer with a typed footprint reason. Regressions: `test_cell_larger_than_every_box_is_deferred`, `test_affinity_box_too_small_defers_instead_of_scheduling`.

8. **Surface-constraint integration — M-5** — `d426653`. `Case.constraints` is on the schema; code-exec scoring runs the AST checker after extraction and stores `constraint_violations` on `CaseResult` without changing the functional score. This commit also removes `Battery.weights` (see M-6). Regression: `test_code_exec_records_constraint_violations_separately_from_score`.

9. **Battery weights ignored — M-6** — `62398da` (test) + field removal in `d426653`. The unsupported scoring knob is gone from the model until multiple components exist; YAML may still carry `weights:` (ignored extra). Regression: `test_battery_weights_are_not_a_scoring_knob`.

10. **Equal-score champions — M-7** — `e4896fa`. Champion selection sorts by quality, pass rate, then lexicographic `(model, box, context)`, independent of input/`as_completed` order. This commit also contains the empty-fleet production check (see M-8). Regression: `test_compact_summary_tie_is_independent_of_input_order`.

11. **Empty fleets — M-8** — `194f465` (test) + `e4896fa` (raise before `ThreadPoolExecutor`). Config with no runnable models is a typed `GauntletError`, not `max_workers=0`. Regression: `test_orchestrate_rejects_empty_model_fleet`. Unresolved target/box references were already fail-closed in the prior HIGH remediation.

12. **Frontier key at the client boundary — M-9** — `10fa54c`. `_frontier_client` and `OpenAIClient(require_key=True)` reject missing/whitespace keys; the stripped key is what goes on the Authorization header. CLI also treats whitespace-only `GAUNTLET_FRONTIER_API_KEY` as unset. Regressions: `test_frontier_client_requires_a_nonblank_key`, `test_openai_client_require_key_propagates_stripped_value`.

13. **Truncated non-code responses — M-10** — `76f5c9d`. Truncated exact/regex/schema/conventional-commit/compilable-code failures become unscored `truncated` unless the reply already passed. Rewrites `test_a_non_code_exec_result_is_left_alone`, which had pinned truncated exact as a scored 0. Regression: `test_truncated_exact_match_failure_is_unscored`.

14. **Parent-death sandbox orphans — M-11** — `66926d6`. The sandbox runner arms `PR_SET_PDEATHSIG` on Linux and a `getppid` watch elsewhere; Windows already uses `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` from H-13. Stale `gauntlet-codeexec-*` scratch dirs are removed on the next case. Still best-effort, not a security boundary. A synchronized hard-kill of the parent on every OS was not reproduced; the regressions cover the mechanism and leftover-directory cleanup. Regressions: `test_sandbox_runner_arms_parent_death`, `test_stale_sandbox_directories_are_removed`.

## NOT FIXED

None of the in-scope HIGH or MEDIUM findings were skipped.

Out of scope (unchanged, as instructed):

- **Finding 10 — parallel VRAM race (H-6/P2-15).** Still blocked on a physical-GPU identity decision.
- **Finding 11 — judge-family aliases (H-7/P2-10).** Still blocked on a canonical base-family taxonomy.
- **Finding 23 — judge exclusive-VRAM lifecycle (P2-14).** Still blocked on live LM Studio JIT observation plus a product choice.

## REQUIRES HUMAN DECISION

Unchanged from the prior report, and not acted on here:

- **Git-history purge** of historical host/device identifiers. No rewrite, force-push, or ref purge.
- **Physical GPU resource identity (finding 10).**
- **Canonical model base-family metadata (finding 11).**
- **Judge deployment/lifecycle (finding 23).**
- **Live `busy` reload** as a kill switch mid-run.

No new design decisions were taken autonomously beyond the in-scope fixes above. M-6 chose “remove the unsupported field” rather than inventing a weighted-aggregation scheme that has no second component.

## Final verification

Mandated safe invocation:

```text
PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider --basetemp=/tmp/bench-gauntlet-pytest-safe
```

Final result: **825 passed, 8 skipped, 4 deselected in 23.65s**.

The pass count is **32 above** the 793-passed baseline from the prior remediation increment.