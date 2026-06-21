"""Generate a synthetic gold set from the live Qdrant chunks.

For each restaurant we sample real chunks and ask an LLM to write a natural diner
question answerable from THAT chunk, plus the verbatim facts pinning the answer.
Each item records its source point id, so retrieval can be scored by exact origin
as well as by fact presence. Self-consistency is enforced: any generated item
whose expected_facts aren't actually in the source chunk is dropped.

Defaults to the Groq backend (Gemini's free tier caps generate_content at ~20/day).

Usage (from repo root):
    python -m evals.generate_synthetic                       # ~4 per restaurant
    python -m evals.generate_synthetic --per-restaurant 6
    python -m evals.generate_synthetic --restaurant Taj --per-restaurant 10
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel
from qdrant_client import QdrantClient

from config import get_settings
from evals.datatypes import SYNTHETIC_PATH
from evals.llm import make_backend
from evals.matching import facts_present
from utils import strip_html_comments

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("evals.generate")

GEN_SYSTEM = """You write evaluation questions for a restaurant-menu Q&A system. \
Given ONE chunk of menu text, produce a single realistic question a diner would \
ask that is answerable using ONLY this chunk. Rules:
- The question must be answerable from this chunk alone (don't require other pages).
- expected_facts: 1-2 SHORT strings copied VERBATIM from the chunk that pin the \
answer (usually the dish/section name; include a price digit only if it appears here).
- expected_answer: a short, correct answer (e.g. a price, a yes/no, a brief list).
- category: one of price, description, hours, dietary, contact, availability.
- Prefer concrete lookups (prices, what's in a dish, timings) over vague questions."""


class SynthQ(BaseModel):
    question: str
    expected_facts: list[str]
    expected_answer: str
    category: str


def all_chunks(qdrant: QdrantClient, collection: str) -> list[dict]:
    """Scroll the whole collection, returning {id, restaurant, page, text}."""
    out: list[dict] = []
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection,
            limit=256,
            with_payload=["text", "restaurant", "page_number"],
            with_vectors=False,
            offset=offset,
        )
        for p in points:
            text = strip_html_comments(p.payload.get("text", "") or "")
            if text:
                out.append({
                    "id": str(p.id),
                    "restaurant": p.payload.get("restaurant"),
                    "page": p.payload.get("page_number"),
                    "text": text,
                })
        if offset is None:
            break
    return out


def _useful(chunk: dict, min_chars: int) -> bool:
    """Skip tiny headers / pure-figure chunks; favour content with substance."""
    t = chunk["text"]
    return len(t) >= min_chars and any(c.isalpha() for c in t)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic gold questions from Qdrant chunks")
    ap.add_argument("--per-restaurant", type=int, default=4, help="questions per restaurant")
    ap.add_argument("--restaurant", help="limit to one restaurant (exact payload value)")
    ap.add_argument("--min-chars", type=int, default=40, help="skip chunks shorter than this")
    ap.add_argument("--backend", default="groq", choices=["groq", "gemini"])
    ap.add_argument("--model", help="override the generation model")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(SYNTHETIC_PATH))
    args = ap.parse_args()

    settings = get_settings()
    qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=60)
    backend = make_backend(args.backend, args.model, role="gen")
    logger.info("Generator backend: %s | collection: %s", backend.name, settings.qdrant_collection_name)

    chunks = all_chunks(qdrant, settings.qdrant_collection_name)
    by_rest: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        if c["restaurant"] and _useful(c, args.min_chars):
            if args.restaurant and c["restaurant"] != args.restaurant:
                continue
            by_rest[c["restaurant"]].append(c)

    if not by_rest:
        logger.error("No usable chunks found (restaurant filter too strict?).")
        return

    rng = random.Random(args.seed)
    items: list[dict] = []
    dropped = 0

    for restaurant in sorted(by_rest):
        pool = by_rest[restaurant]
        rng.shuffle(pool)
        sampled = pool[: args.per_restaurant]
        logger.info("%s: %d chunks -> sampling %d", restaurant, len(pool), len(sampled))

        for j, chunk in enumerate(sampled):
            try:
                q = backend.complete(GEN_SYSTEM, f"MENU CHUNK:\n{chunk['text'][:1500]}", SynthQ, 0.4)
            except Exception as e:  # noqa: BLE001
                logger.warning("  gen failed for %s chunk: %s", restaurant, e)
                continue

            facts = [f for f in q.expected_facts if f.strip()]
            if not facts_present(facts, chunk["text"]):  # enforce self-consistency
                dropped += 1
                logger.info("  dropped (facts not in chunk): %r", q.question)
                continue

            slug = restaurant.lower().replace(" ", "-").replace("/", "-")
            items.append({
                "id": f"syn-{slug}-{j:02d}",
                "restaurant": restaurant,
                "question": q.question,
                "expected_facts": facts,
                "expected_answer": q.expected_answer,
                "category": q.category,
                "source_id": chunk["id"],
                "source_text": chunk["text"],
            })
            time.sleep(0.1)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "backend": backend.name,
            "collection": settings.qdrant_collection_name,
            "count": len(items),
            "items": items,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Wrote %d synthetic items (%d dropped) -> %s", len(items), dropped, out_path)


if __name__ == "__main__":
    main()
