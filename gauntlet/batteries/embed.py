"""Embeddings retrieval eval. Embed a small corpus + queries, rank docs by cosine
similarity per query, and score recall@k. Pure math is unit-tested; run_embed_cell
is the only network-touching part."""
from __future__ import annotations

import math

from gauntlet import errors
from gauntlet.models import Cell


def _finite_vector(vec: list[float], *, name: str) -> None:
    if not vec:
        raise ValueError(f"{name} must be a non-empty vector")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool)
               and math.isfinite(float(x)) for x in vec):
        raise ValueError(f"{name} contains a non-finite or non-numeric component")


def cosine(a: list[float], b: list[float]) -> float:
    _finite_vector(a, name="left")
    _finite_vector(b, name="right")
    if len(a) != len(b):
        raise ValueError(f"cosine dimension mismatch: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def rank_indices(query_vec: list[float], doc_vecs: list[list[float]]) -> list[int]:
    """Doc indices ordered by descending cosine similarity to the query."""
    return sorted(range(len(doc_vecs)),
                  key=lambda i: cosine(query_vec, doc_vecs[i]), reverse=True)


def recall_at_k(rankings: list[list[int]], relevant: list[int], k: int = 1) -> float:
    """Fraction of queries whose relevant doc appears in the top-k ranked docs."""
    if not rankings:
        return 0.0
    if len(rankings) != len(relevant):
        raise ValueError(
            f"recall count mismatch: {len(rankings)} rankings vs {len(relevant)} labels"
        )
    hits = sum(1 for ranked, rel in zip(rankings, relevant, strict=True)
               if rel in ranked[:k])
    return hits / len(rankings)


def chance_recall_at_k(corpus_size: int, k: int) -> float:
    """Uniform-random baseline: probability the one relevant doc is in the top-k."""
    if corpus_size <= 0:
        return 0.0
    return min(1.0, max(0, k) / corpus_size)


def validate_k(k: int, corpus_size: int) -> None:
    if not isinstance(k, int) or isinstance(k, bool) or k < 1 or k >= corpus_size:
        raise errors.GauntletError(
            f"embed k must satisfy 1 <= k < corpus_size ({corpus_size}), got {k}"
        )


def _degenerate_vectors(vecs: list[list[float]]) -> bool:
    if len(vecs) < 2:
        return False
    first = vecs[0]
    return all(v == first for v in vecs[1:])


def run_embed_cell(
    client,
    model: str,
    target: str | None,
    box: str,
    context: int,
    corpus: list[str],
    queries: list[str],
    relevant: list[int],
    k: int = 1,
) -> Cell:
    """Embed corpus + queries, rank, score recall@k into an `embed` Cell. A transport
    failure yields an errored cell with quality None (never silently 0)."""
    validate_k(k, len(corpus))
    if len(queries) != len(relevant):
        raise errors.GauntletError("embed queries and relevant labels must be the same length")
    try:
        doc_vecs = client.embeddings(model=model, inputs=corpus)
        q_vecs = client.embeddings(model=model, inputs=queries)
    except errors.GauntletError:
        return Cell(model=model, target=target, box=box, context=context,
                    capability="embed", quality=None, pass_rate=None,
                    cases=len(queries), errors=1)
    if len(doc_vecs) != len(corpus) or len(q_vecs) != len(queries):
        raise errors.GauntletError("embedding response count does not match the request")
    dim = len(doc_vecs[0]) if doc_vecs else 0
    try:
        for vec in doc_vecs + q_vecs:
            _finite_vector(vec, name="embedding")
            if len(vec) != dim:
                raise ValueError("embedding dimension mismatch")
    except ValueError as exc:
        raise errors.GauntletError(str(exc)) from exc
    if _degenerate_vectors(doc_vecs) or _degenerate_vectors(q_vecs):
        return Cell(model=model, target=target, box=box, context=context,
                    capability="embed", quality=None, pass_rate=None,
                    cases=len(queries), errors=1)
    rankings = [rank_indices(q, doc_vecs) for q in q_vecs]
    recall = recall_at_k(rankings, relevant, k=k)
    return Cell(model=model, target=target, box=box, context=context,
                capability="embed", quality=recall, pass_rate=recall,
                cases=len(queries), errors=0)
