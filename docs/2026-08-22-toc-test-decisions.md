# ToC scheduler edge tests — rationale

**Date:** 2026-08-22  
**Branch:** `feat/codegen-execution-scorer`  
**File:** `tests/test_toc_scheduler.py`

---

## Decision — expand boundary coverage

| | |
|---|---|
| **Choice** | Add 13+ edge-case tests beyond happy-path placement |
| **Reasoning** | Wrong-box scheduling is silent — cells land on tight vs broad, exclusive vs parallel, with no user-visible error. Boundary bugs (cost ceiling 5.0, affinity pinning, empty plans) are cheaper to catch in unit tests than in fleet mis-routes |
| **Kevin direction** | "Come up with more tests" + review recent scheduler coding patterns |

---

## Cases covered

| Test area | Why it matters |
|---|---|
| Empty cell list | Must yield empty plan, not throw |
| Cost vs weight precedence | Scheduling order follows policy, not accidental field order |
| Cost ceiling 5.0 | Heavy cells route broad/exclusive; cheap cells pack tight |
| Critical + affinity | Pinned box honored even when stronger box exists |
| Heavy → highest VRAM broad | VRAM routing invariant |
| Defer paths | Cells that cannot fit defer rather than corrupt batches |

---

## Deliberate assertion fix

Single cheap cell on tight box starts **exclusive** until a second cell joins the batch — documents actual scheduler behavior, not assumed parallel default.
