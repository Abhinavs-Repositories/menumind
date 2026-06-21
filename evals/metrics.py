"""Retrieval metrics computed from per-doc relevance flags.

All metrics treat relevance as binary (a chunk either carries the answer or it
doesn't), which fits menu fact-lookup where each question has one or a few
answer-bearing chunks.
"""

from __future__ import annotations

import math
from statistics import mean
from typing import Sequence


def hit_at_k(flags: Sequence[bool], k: int) -> float:
    """1.0 if any relevant doc appears in the top-k, else 0.0."""
    return 1.0 if any(flags[:k]) else 0.0


def reciprocal_rank(flags: Sequence[bool]) -> float:
    """1 / rank of the first relevant doc (0 if none)."""
    for i, rel in enumerate(flags, start=1):
        if rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(flags: Sequence[bool], k: int) -> float:
    """Binary nDCG@k. Ideal DCG = first `min(#rel, k)` positions filled."""
    rels = [1.0 if r else 0.0 for r in flags[:k]]
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))
    n_rel = min(sum(1 for r in flags if r), k)
    if n_rel == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(i + 2) for i in range(n_rel))
    return dcg / idcg if idcg else 0.0


def precision_at_k(flags: Sequence[bool], k: int) -> float:
    """Fraction of the top-k that is relevant."""
    top = flags[:k]
    if not top:
        return 0.0
    return sum(1 for r in top if r) / len(top)


def safe_mean(values: Sequence[float]) -> float:
    return round(mean(values), 4) if values else 0.0
