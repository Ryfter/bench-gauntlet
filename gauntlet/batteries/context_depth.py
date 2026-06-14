"""Needle-at-depth: turn a model's *advertised* context into an *effective* one.

A unique 'needle' fact is buried at a given depth inside filler text sized to a
target context length; the model is asked to retrieve it. Sweeping lengths yields
an accuracy curve, and `effective_context` reduces that curve to the largest length
where retrieval still holds at/above the threshold (the scorecard's effective_90pct).

The core (approx_tokens/build_haystack/score_retrieval/effective_context) is pure
and unit-tested; `run_context_depth` is the only part that touches the network."""
from __future__ import annotations

from gauntlet import errors
from gauntlet.models import ContextDepth

DEFAULT_ANSWER = "CERULEAN-OTTER-42"
DEFAULT_NEEDLE = f"Important: the secret passcode for the vault is {DEFAULT_ANSWER}. Remember it."
DEFAULT_QUESTION = ("\n\nQuestion: What is the secret passcode for the vault? "
                    "Answer with ONLY the passcode.")
_FILLER = ("The archivists catalogued another uneventful afternoon in the great "
           "library, shelving ledgers no one would ever read. ")

# ~4 characters per token is the standard coarse heuristic for English text.
_CHARS_PER_TOKEN = 4


def approx_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def build_haystack(
    context_tokens: int,
    depth_fraction: float,
    *,
    needle: str = DEFAULT_NEEDLE,
    question: str = DEFAULT_QUESTION,
    filler: str = _FILLER,
) -> str:
    """Filler sized to ~context_tokens with `needle` inserted at `depth_fraction`
    (0.0 = start, 1.0 = end), then the retrieval `question` appended."""
    target_chars = context_tokens * _CHARS_PER_TOKEN
    reps = max(1, target_chars // len(filler))
    body = filler * reps
    cut = int(len(body) * max(0.0, min(1.0, depth_fraction)))
    haystack = body[:cut] + needle + body[cut:]
    return haystack + question


def score_retrieval(output: str, answer: str = DEFAULT_ANSWER) -> bool:
    return answer.lower() in output.lower()


def effective_context(samples: list[tuple[int, float]], threshold: float = 0.9) -> int:
    """Largest context length whose accuracy is >= threshold; 0 if none qualify."""
    qualifying = [length for length, acc in samples if acc >= threshold]
    return max(qualifying) if qualifying else 0


def run_context_depth(
    client,
    model: str,
    advertised: int,
    lengths: list[int],
    depths: list[float] | None = None,
) -> ContextDepth:
    """Sweep context lengths × needle depths, retrieve, and reduce to effective_90pct.
    A length's accuracy is the mean over depths. Transport failures count as misses
    (accuracy contribution 0) so the run never aborts."""
    depths = depths or [0.1, 0.5, 0.9]
    samples: list[tuple[int, float]] = []
    for length in lengths:
        hits = 0
        for depth in depths:
            prompt = build_haystack(length, depth)
            try:
                reply = client.chat(model=model, prompt=prompt, max_tokens=32)
            except errors.GauntletError:
                continue
            if score_retrieval(reply.text):
                hits += 1
        samples.append((length, hits / len(depths)))
    return ContextDepth(model=model, advertised=advertised,
                        effective_90pct=effective_context(samples))
