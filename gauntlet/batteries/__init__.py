"""Special battery runners — evals that don't fit the per-case score_case flow
(needle-at-depth context curves, embeddings retrieval). Each module exposes a
pure core (TDD'd, no network) plus a thin live runner over OpenAIClient."""
