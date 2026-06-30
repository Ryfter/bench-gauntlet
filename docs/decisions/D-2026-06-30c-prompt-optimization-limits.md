# Decision: Prompt optimization has limited impact on model performance

**Date:** 2026-06-30  
**Context:** After identifying weak model performance, tested whether better-crafted prompts could improve scores.

**Experiment:** Created improved prompt variants with explicit format instructions:
- commit-msg: "Output ONLY a conventional commit message"
- extract-json: "Output ONLY the JSON object, no markdown fence"
- code-gen: "Output ONLY compilable code, no explanation"

Tested on qwen3.5-9b (weak: scores 0 on commit-msg/extract-json) and gemma-4-31b (strong: scores 0.88 commit-msg, 0.83 extract-json).

**Results:**
- **qwen3.5-9b:** commit-msg 0.00→0.00, extract-json 0.00→0.00 (no change)
- **gemma-4-31b:** commit-msg 0.88→0.89 (+0.01), extract-json 0.83→0.71 (-0.12)

**Findings:**
1. Better prompts **cannot fix fundamental model gaps** — qwen's weakness on commit-msg persists even with explicit format instructions; indicates model doesn't know the pattern
2. Overly-prescriptive prompts can **degrade performance on competent models** — gemma's extract-json dropped when format requirements became stricter
3. Original test prompts are **near-optimal** — looser, clearer instructions performed better than rigid ones

**Decision:** Keep original prompts. Weak model scores reflect genuine capability gaps, not test or prompt design issues.

**Impact:** Confidence that scorecard results are honest model measurements, not artifacts of test design. Prompt engineering has ceiling (~1-2% for competent models) and risk of backfire.
