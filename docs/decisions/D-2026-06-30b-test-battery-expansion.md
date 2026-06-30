# Decision: Expand test batteries to improve discriminative power

**Date:** 2026-06-30  
**Context:** First full Firefly battery run (63 cells) revealed weak model performance on commit-msg (multiple models 0.00) and summarize-short (all models ≤0.45 quality).

**Problem:** Were weak scores due to bad test design (too narrow/hard cases) or genuine model gaps? Original batteries had only 5 commit-msg cases and 4 summarize-short cases.

**Decision:** Add expanded test cases:
- **commit-msg:** docs-01, revert-01, perf-01 (5→8 cases)
- **summarize-short:** technical-paper, narrative-excerpt, news-business (4→7 cases)

**Rationale:**
- Broader test coverage discriminates between models more reliably
- Case variety (docs, revert, perf commits; technical, narrative, news summaries) tests different model strengths
- Expanded judge rubrics for summarize are stringent but fair — test fitness

**Result (81-cell expanded run):**
- nemotron-3-nano-4b: 0.57→0.44 on summarize (new cases harder, revealing weakness)
- gemma-4-31b: 1.00→0.88 on commit-msg (perfect score was overfit to narrow test set)
- Models scoring 0 before (qwen3.5-9b, gpt-oss-20b) still 0 (model gaps, not test design)

**Finding:** Expanded cases are legitimate and improve battery quality by revealing real model weaknesses that narrow test sets masked.

**Impact:** Better-discriminated scorecard results, more reliable for model selection.
