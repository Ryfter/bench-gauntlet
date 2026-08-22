# Benchmark integrity — threat model

A score is only worth the integrity of how it was obtained. This note enumerates
the ways a model under test could earn a number it did not deserve, what
Gauntlet does about each, and — the part that matters most — **what each control
does not cover**.

The guiding rule: an overstated guarantee is worse than a documented gap. A
reader who trusts a control that does not hold draws confident wrong
conclusions; a reader who knows the limit can compensate.

## Scope

This is about **measurement integrity**, not security. Gauntlet benchmarks
cooperative local models, not adversaries. Nothing here assumes a model is
actively trying to break out — the realistic failure is a model that notices a
readable file next to it, or a serving stack that helpfully answers on the
model's behalf. Those are the cases these controls are built for.

## The vectors

### A — Answer leakage into the prompt

*Risk:* hidden asserts, a reference solution, or expected outputs reach the
model. The score then measures recall of the answer, not capability.

*Control:* `integrity.assert_no_prompt_leak()` compares whitespace-normalised
**lines** (not tokens) between the prompt and the case's hidden material, and
raises `IntegrityError` on any shared run of ≥40 characters. Lines shorter than
that are ignored — `return []` and `for i in x:` collide constantly and a
token-level check drowns in false positives. `tests/test_case_validation.py`
enforces the same property across all 108 cases at build time.

*Exemption:* the `test-authoring` dimension is exempt by design. There the model
is handed an implementation and asked to write tests that catch its planted bug,
so prompt/hidden-test overlap **is** the task. What stays hidden is which
behaviour is wrong.

*Residual risk:* paraphrase. A prompt that *describes* the expected output in
prose rather than quoting it will not trip a substring check. Case review is the
only defence.

### B — Runtime filesystem lookup

*Risk:* generated code reads the answers instead of computing them.

*Control:* an in-sandbox guard (`scoring/_guard.py`) patches `builtins.open`,
`io.open`, `os.open`, `os.listdir` and `os.scandir` to refuse paths resolving
under the benchmark tree **and the sandbox's own copy** of `hidden_tests.py`.
Process creation (`os.system`, `os.popen`, the `exec*`/`spawn*` family,
`subprocess`) is blocked outright. `sys.path` entries reaching the benchmark
tree are stripped.

The deny-list is targeted rather than a general confinement, deliberately: the
sandbox must still import the standard library, which lives outside the scratch
directory.

*Verified:* `os.system("cp hidden_tests.py leaked.txt")` followed by reading the
copy **defeated an earlier version of this guard completely** — the copy had an
allowed name, so the `open()` patch never saw it. That is why process creation is
blocked as a class rather than by filename.

*Residual risk:* this is a Python-level guard, and Python offers plenty of ways
around one — `ctypes` calling libc directly, re-execing the interpreter, raw
syscalls, restoring the unpatched builtins from a fresh `importlib` import.
**It blocks accidental and casual cheating. It is not a security boundary.**
Real isolation needs OS support: a container, seccomp, or a mount namespace
(`bwrap`/`unshare`). Those are not currently used because Gauntlet must run on
Windows as well as Linux.

### C — Runtime network egress

*Risk:* generated code fetches an answer instead of computing it.

*Control:* the guard replaces `socket.socket`, `socket.create_connection`,
`socket.socketpair` and `socket.create_server` with functions that record a
violation and raise. The sandbox environment is also stripped of inherited proxy
and API-key variables.

*Residual risk:* same as B — `ctypes` can reach the socket syscalls directly.
An OS-level network namespace would close this properly.

### D — Inference-time tool use

*Risk:* the serving stack answers on the model's behalf via web search or a tool
call, and Gauntlet scores the *stack* while believing it measured the model.

*Control:* `integrity.assert_request_is_tool_free()` runs at the HTTP boundary in
`client.py` — the only place a request is constructed, so nothing can bypass it —
and refuses any payload carrying `tools`, `functions`, `tool_choice`,
`function_call`, `plugins`, `web_search`, `retrieval` or `connectors`. An empty
list is allowed, since serving stacks routinely send `tools: []`.
`integrity.response_used_tools()` additionally inspects the reply shape, because
a gateway may inject tools we never asked for.

*Residual risk:* a gateway that performs retrieval *silently*, without declaring
it in the request or reflecting it in the response, is undetectable from here.
Trusting the endpoint is unavoidable at some level.

### E — Canary tokens

*Risk:* a leak we did not anticipate.

*Control:* every hidden-test file carries a deterministic per-case marker
(`GAUNTLET-CANARY-<12 hex>`, derived from the case id). If a canary appears in a
model's **output**, the model demonstrably saw the file it is graded against.
The cell is marked `integrity_violation` and **unscored** — not zero. We cannot
say what the model can do; only that this number is not evidence of it.

*Residual risk:* catches only leaks that get *echoed*. A model that reads the
tests and stays quiet about it is invisible to this check. Canaries are a
backstop, not a primary control.

## In-process grading: the structural limit

The grader runs in the same process as the candidate, because `check(ns)` must
call the candidate's own functions. That means the expected values are, in
principle, reachable from candidate code.

This was verified rather than assumed. Attacks written with full knowledge of
the runner's internals:

| attack | before hardening | after |
|---|---|---|
| `gc.get_objects()` → hidden module `__dict__` | **succeeded — extracted answers** | detected |
| frame-walk to the runner's locals | failed | detected |
| call `check()` as a brute-force oracle | failed | detected |
| `os.system` copy, then read the copy | **succeeded — extracted answers** | detected |

`gc.get_objects`, `gc.get_referrers` and `sys._getframe` are now blocked, which
turns these from silent successes into recorded violations.

**This raises the bar; it does not close the hole.** Determined code sharing a
process with its own grader can reach the grader's data. Closing it properly
means grading out-of-process, which is incompatible with calling arbitrary
candidate functions. Given the threat model — cooperative models, not
adversaries — the cost of that redesign is not currently justified. If Gauntlet
is ever used to rank models with something at stake, revisit this first.

## Fail closed

If a control cannot be enabled, affected cells are marked **unscored** with the
reason recorded — never silently scored as though the control were active. This
follows from the scoring-honesty invariant in `CLAUDE.md`: a benchmark must not
report numbers it cannot vouch for.

A violation likewise yields `unscored`, not `0.0`. Zero is a claim about the
model's ability; unscored is an admission that we do not know.

## Current results

Against 16 red-team attempts (authored by an outside model given the sandbox
description) plus 4 white-box attacks written with knowledge of the internals:

```
red team:   0/16 obtained the answers,  9 recorded as explicit violations
white box:  0/4  obtained the answers,  4 recorded as explicit violations
```

The gap between "obtained nothing" and "recorded as a violation" is attempts
that simply failed — a cheat that never worked is not evidence the guard stopped
it. Both numbers are reported for that reason.

## If you extend this

- Add attacks to the red-team corpus before adding controls; an untested control
  is a guess.
- Prefer blocking a *class* of access (process creation) over a specific path.
  The `os.system` bypass existed because the original guard reasoned about
  filenames.
- Never let a control fail open. Silent degradation is the one failure mode that
  makes a scorecard actively misleading rather than merely incomplete.
