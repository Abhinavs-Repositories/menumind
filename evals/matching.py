"""Relevance matching: decide whether a retrieved chunk answers a gold item.

Menu chunks are short and fact-dense, so we judge relevance by *content*, not by
fragile chunk ids. A chunk is relevant when it carries the gold facts (e.g. the
dish name) — exactly what the LLM needs to answer. The synthetic generator also
records the source point id for an exact-match fast path.
"""

from __future__ import annotations

import re
import unicodedata

from evals.datatypes import GoldItem

_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")


def normalize(text: str) -> str:
    """Lowercase, strip accents, drop punctuation, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = _NON_ALNUM_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _tokens(text: str) -> set[str]:
    return set(normalize(text).split())


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def facts_present(facts: list[str], text: str) -> bool:
    """True when every expected fact is a normalized substring of `text`."""
    if not facts:
        return False
    norm = normalize(text)
    return all(normalize(f) in norm for f in facts if normalize(f))


def is_relevant(item: GoldItem, doc: dict, overlap_threshold: float = 0.6) -> bool:
    """Whether a single retrieved doc is relevant to the gold item."""
    # 1) Exact source-chunk match (synthetic items know their origin).
    if item.source_id and doc.get("id") == item.source_id:
        return True
    # 2) Fact-bearing chunk: the answer text is physically present.
    if facts_present(item.expected_facts, doc.get("text", "")):
        return True
    # 3) Fallback for synthetic items: high token overlap with the source chunk
    #    (covers paraphrase / re-chunk cases where the point id changed).
    if item.source_text and _jaccard(item.source_text, doc.get("text", "")) >= overlap_threshold:
        return True
    return False


def relevance_flags(item: GoldItem, docs: list[dict]) -> list[bool]:
    """Relevance label for each doc in ranked order."""
    return [is_relevant(item, d) for d in docs]


def context_has_answer(item: GoldItem, context: str) -> bool:
    """Whether the answer facts survived rerank + truncation into the LLM context."""
    if facts_present(item.expected_facts, context):
        return True
    if item.source_text and _jaccard(item.source_text, context) >= 0.5:
        return True
    return False
