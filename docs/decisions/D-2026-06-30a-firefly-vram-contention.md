# Decision: Firefly VRAM contention mitigation via box split

**Date:** 2026-06-30  
**Context:** First real Firefly scorecard run (RTX 5090, 32GB VRAM)  
**Problem:** Firefly runs two serving stacks on same GPU: LM Studio (port 1234) and Ollama (port 11434). Using `gauntlet orchestrate` (parallel multi-target runner) would load models on both servers simultaneously, risking OOM on 32GB VRAM.

**Decision:** Split single `firefly` box into two independent box IDs (`firefly-lms` and `firefly-oll`), both labeled `RTX 5090 desktop`, with `firefly-oll` marked `busy: true`.

**Rationale:**
- `busy: true` defers all cells for a box, allowing clean single-server inference per run
- Box splitting preserves hardware label (public metadata) while enabling per-server scheduling
- Exclusive loading (one model at a time per server) respects VRAM budget under load

**Alternative considered:** Mark both boxes non-busy and hope sequential runner avoids overlap. Rejected: orchestrate parallelizes across targets, guaranteeing simultaneous loads.

**Outcome:** Firefly smoke test (4 models) and full battery (9 models) both succeeded cleanly with firefly-ollama deferred, firefly-lmstudio running exclusively. VRAM safety confirmed.

**Impact:** Unblocks multi-target scorecard runs on systems with shared-GPU serving stacks.
