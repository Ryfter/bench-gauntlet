# Critical/high remediation report

Date: 2026-08-28  
Branch: `fix/review-critical-high`  
Scope: consolidated findings 1-26 only (3 CRITICAL, 23 HIGH)

## FIXED

1. **Sandbox verdict forgery — C-2/P2-1** — `c24ca75`. Captured a trusted child verdict channel before candidate execution and strictly validated parent-side verdict objects, violation lists, integer counts, and bounds. Regression: `test_candidate_cannot_forge_sandbox_verdict_through_shared_globals` first reproduced score `7.0`, then verified the real `0/3` result.
2. **Committed identifiers/private ledgers — C-1** — `97df92f`. Scrubbed current tracked identifiers and non-TEST-NET fixtures, removed private device defaults, moved raw run ledgers to an OS-private root, rejected ledgers inside the repository, and added a hashed tracked-tree privacy gate. Regressions: `test_tracked_tree_contains_no_private_network_or_device_identifiers`, `test_run_paths_refuse_private_ledgers_inside_tracked_tree`, and the private-root assertion in `test_run_unreachable_target_writes_scorecard_and_does_not_crash`.
3. **Run/resume path traversal — P2-2** — `801ba9f`. Restricted run and namespace IDs to safe single ASCII components and verified resolved ledger paths remain below the private root, including symlink escapes. Regressions: the `test_private_run_paths_*` group in `test_runner_checkpoint.py`.
4. **Incomplete output redaction — H-1/P2-3** — `68341ca`, corrective `cf7c271`. Sanitized shared identifiers recursively, recognized IPv6 and host:port forms, stopped echoing matched secrets, suppressed target URLs/exceptions in diagnostics, and preserved report behavior. Regressions: IPv6/host-port and nested share tests in `test_scorecard_json.py`, plus `test_targets_lists_models`, `test_unreachable_raises_typed_error`, and shared Markdown coverage.
5. **HTTP boundary bypass — H-2/P2-4** — `4ba99af`. Routed native enrichment GETs through `OpenAIClient.get_json`. Regression: `test_only_openai_client_module_imports_http_libraries` AST-scans production modules.
6. **Disconnected prompt-leak control — H-3** — `f075e50`. The production code-exec path now loads each case's hidden material and checks its prompt before inference, including custom batteries. Regression: `test_run_cell_rejects_hidden_code_exec_material_in_custom_prompt`.
7. **Disconnected response tool-use control — H-3/P2-11** — `8146867`. Tool/function-bearing SSE choices now become integrity-tainted unscored cases. Regressions: `test_chat_rejects_server_injected_tool_use` and `test_run_cell_records_tool_tainted_response_as_unscored`.
8. **Busy bypass/unresolved mappings — H-4/P2-12** — `4bed649`. Added config referential-integrity validation and a centralized fail-closed runnable-target check used by `depth` and `embed`. Regressions: unresolved-reference parametrization and `test_require_runnable_target_fails_closed_for_busy_box`.
9. **Empty plan mutates VRAM — H-5** — `32c4fed`. Returns before any VRAM inspection/mutation when no runnable cells exist. Regression: `test_execute_plan_all_busy_returns_before_any_vram_operation`.
12. **Unscored pass-rate failures — H-8/P2-7** — `79f1e0b`. Pass rate now uses scored cases only, all-unscored is null, and `scored_coverage` is persisted. Regressions: corrected `test_scorecard_aggregate.py` expectations and the no-judge runner assertion.
13. **Transport-unscored fleet coverage — H-8** — `dbbbde3`. Fleet analysis prefers persisted `scored_coverage`. Regression: `test_explicit_scored_coverage_includes_transport_unscored_cases`.
14. **Shape-only JSON extraction — H-9/P2-5** — `853da1b`. All four active schemas now bind source values and reject degenerate constants. Regression: `test_extract_json_cases_accept_sources_and_reject_degenerate_constants` validates positive and negative outputs for every case.
15. **Generic commit constant — H-9/P2-6** — `e2b2df5`. Added per-case type, required-content, and breaking-footer requirements. Regression: `test_commit_message_cases_reject_one_generic_constant` proves `feat: x` fails all eight cases.
16. **Format-only code-debug — H-9/P2-18** — `0dbe074`. Replaced regex/compilation scoring with hidden executable behavior checks for all six repairs. Regression: `test_code_debug_cases_reject_non_executable_pattern_answers` covers both working references and prose/format-only negatives.
17. **Context prompt echo/public constant — H-10/P2-16** — `a3ecd10`. Generates a random per-probe needle and requires normalized exact output. Regression: `test_score_retrieval_requires_normalized_exact_answer` rejects prompt echo and prefixed prose.
18. **Context transport becomes zero — H-10/P2-8** — `316d837`. Effective depth is nullable, probe coverage is persisted, and incomplete lengths do not contribute. Regression: corrected `test_depth_command_unreachable_writes_unscored_curve`.
19. **Malformed chat 200 scored empty — H-11** — `92a65a0`, fixture correction `95f3749`. Requires at least one structurally valid SSE choice and raises a typed protocol outcome otherwise. Regression: `test_chat_rejects_non_sse_or_malformed_200`; the baseline fixture now emits valid SSE.
20. **Embedding failures escape — H-11/P2-20** — `11045fe`. Translates all HTTP failures plus invalid JSON/data/row shapes at the client boundary. Regression: `test_embeddings_translate_status_and_protocol_failures`.
21. **Judge failures abort cells — P2-9** — `45f7f8b`. Judge transport/load failures now append an unscored `transport_error` result and continue. Regression: `test_run_cell_judge_transport_failure_is_unscored_not_raised`.
22. **Explicit load failure ignored — P2-13** — `1602069`. Failed loads emit typed `load_error` cells without client creation, ping, or inference; runner tests inject all VRAM operations. Regression: `test_execute_plan_load_failure_never_pings_or_infers`.

## NOT FIXED

10. **Parallel orchestration VRAM race — H-6/P2-15.** Needs a product/schema decision defining canonical physical-GPU ownership. Current box IDs cannot serve as lock keys because the documented split-target workaround assigns one physical GPU multiple box IDs; locking by target or box would leave the reported race open.
11. **Judge-family aliases — H-7/P2-10.** Needs a canonical base-family taxonomy and migration policy for every configured base model and fine-tune. No alias parser can honestly supply the required metadata, and inventing family values would risk prohibited same-family grading.
23. **Judge exclusive-VRAM lifecycle — P2-14.** Needs the unresolved product decision documented by the review: explicit same-target judge scheduling versus a separate judge target, informed by a synchronized live LM Studio observation of JIT load/evict behavior.
24. **Non-atomic/non-idempotent persistence — H-12/P2-21.** Not reached in this remediation increment. It remains independently actionable and requires a dedicated transactional/upsert design and crash-injection regressions; no partial write-path change was made.
25. **Sandbox resource limits — H-13.** Not reached in this remediation increment. It requires cross-platform CPU/memory/process/output limits and a bounded Windows `taskkill` design while preserving the documented non-security-boundary claim.
26. **Default tests can operate LM Studio — H-14.** Not fully fixed. `tests/test_runner_execute.py` now injects every VRAM operation, but the required suite-wide autouse subprocess/network guard and audit of all remaining unit call sites were not completed.

## REQUIRES HUMAN DECISION

- **Git-history purge:** current tracked files are scrubbed and structurally guarded, but historical commits may still contain the reported personal host/device identifiers. No history rewrite, remote recreation, force-push, or ref purge was attempted. A human must decide whether and how to purge existing history.
- **Physical GPU resource identity (finding 10):** choose the config field and migration semantics used to serialize targets that share one GPU.
- **Canonical model base-family metadata (finding 11):** choose authoritative family values and how aliases/fine-tunes inherit them.
- **Judge deployment/lifecycle (finding 23):** choose explicit same-target scheduling or a separate judge target after live server behavior is observed.
- **Live `busy` reload:** the confirmed direct-command and unresolved-mapping defects are fixed; whether a config edit must act as a live kill switch during an already-running plan remains an explicit product decision.

## Final verification

Mandated safe invocation:

```text
PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider --basetemp=/tmp/bench-gauntlet-pytest-safe
```

Final result: **793 passed, 8 skipped, 4 deselected in 24.72s**.

The pass count is **36 above** the 757-passed baseline.
