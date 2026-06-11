# Gauntlet

**A gauntlet of trials for local models.** Empirically answer — while your boxes
are idle — *which local model is best at which job, at what resource cost*, so
routing decisions rest on measured data instead of reputation.

> Working title. Sibling of [ASR-benchmark](https://github.com/Ryfter) in spirit;
> consumed by [Baton](https://github.com/Ryfter/baton), but standalone by design —
> all it asks of a target is an OpenAI-compatible endpoint.

**Status:** spec'd 2026-06-11, repo scaffolded — implementation not started.
Read the design first: [docs/2026-06-11-gauntlet-design.md](docs/2026-06-11-gauntlet-design.md).

## The idea in five lines

1. **Load profiles** (model @ context) are the unit under test — VRAM = weights + KV cache(context), and quality changes at depth.
2. **Batteries** per capability (commit-msg, extract-json, writing registers, OCR, embeddings, judge-duty, needle-at-depth effective-context) — deterministic checks preferred, LLM judges (non-reasoning, strict-JSON) only where needed.
3. **Resumable overnight runs**, sequenced to respect per-box VRAM budgets and tight/broad usage classes; keep-list models skipped.
4. **The scorecard JSON is the contract** — consumers (Baton's claims/culling/champions, humans, students) depend only on it. Markdown reports double as teaching artifacts.
5. **Frontier baseline is opt-in**: a small sampled comparison that detects when a local specialist has closed the gap — declaring that job a permanent $0 route.

## Layout

```
docs/        design spec
batteries/   <capability>.yaml battery definitions
cases/       per-battery prompt/schema/fixture files
scorecards/  run outputs (JSON canonical + MD report)
targets.example.yaml   endpoint roster template
```
