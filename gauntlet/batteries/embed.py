"""Embeddings retrieval eval. Embed a small corpus + queries, rank docs by cosine
similarity per query, and score recall@k. Pure math is unit-tested; run_embed_cell
is the only network-touching part."""
from __future__ import annotations

import math

from gauntlet import errors
from gauntlet.models import Cell


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
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
    hits = sum(1 for ranked, rel in zip(rankings, relevant) if rel in ranked[:k])
    return hits / len(rankings)


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
    try:
        doc_vecs = client.embeddings(model=model, inputs=corpus)
        q_vecs = client.embeddings(model=model, inputs=queries)
    except errors.GauntletError:
        return Cell(model=model, target=target, box=box, context=context,
                    capability="embed", quality=None, pass_rate=None,
                    cases=len(queries), errors=1)
    rankings = [rank_indices(q, doc_vecs) for q in q_vecs]
    recall = recall_at_k(rankings, relevant, k=k)
    return Cell(model=model, target=target, box=box, context=context,
                capability="embed", quality=recall, pass_rate=recall,
                cases=len(queries), errors=0)
