"""Capture the live retrieval pipeline for one query.

We call MenuRAG's own pipeline steps so the eval measures exactly what the app
runs in production (same embedder, same Qdrant collection, same rerank + context
build), just instrumented to expose the intermediate rankings.
"""

from __future__ import annotations

import time

from evals.datatypes import CaptureResult, GoldItem
from rag import MenuRAG


def capture(rag: MenuRAG, item: GoldItem) -> CaptureResult:
    """Run retrieve -> rerank -> build_context and time each stage."""
    t0 = time.time()
    retrieved = rag._retrieve(item.question, restaurant=item.restaurant)
    t1 = time.time()
    # _rerank may return the same list when there are <= top_k_rerank docs; copy
    # the input so the pre-rerank ranking we keep isn't reordered underneath us.
    reranked = rag._rerank(item.question, list(retrieved))
    t2 = time.time()
    context = rag._build_context(reranked)

    return CaptureResult(
        retrieved=retrieved,
        reranked=reranked,
        context=context,
        retrieve_s=round(t1 - t0, 3),
        rerank_s=round(t2 - t1, 3),
    )
