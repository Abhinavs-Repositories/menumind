"""Shared dataclasses + gold-set loaders for the eval suite."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

GOLD_DIR = Path(__file__).resolve().parent / "gold"
CURATED_PATH = GOLD_DIR / "curated.yaml"
SYNTHETIC_PATH = GOLD_DIR / "synthetic.json"


@dataclass
class GoldItem:
    """One evaluation question with its relevance ground truth.

    A retrieved chunk counts as *relevant* to this item when either:
      - its Qdrant point id == ``source_id`` (exact; set by the synthetic
        generator, which knows the originating chunk), or
      - every string in ``expected_facts`` appears in the chunk text
        (normalized substring match — robust to chunk-id drift / re-ingest).
    """

    id: str
    question: str
    expected_facts: list[str]
    set_name: str  # "curated" | "synthetic"
    restaurant: Optional[str] = None
    category: str = "general"
    expected_answer: Optional[str] = None  # for the correctness judge (curated)
    source_id: Optional[str] = None        # Qdrant point id (synthetic)
    source_text: Optional[str] = None       # originating chunk text (synthetic)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "expected_facts": self.expected_facts,
            "set_name": self.set_name,
            "restaurant": self.restaurant,
            "category": self.category,
            "expected_answer": self.expected_answer,
            "source_id": self.source_id,
            "source_text": self.source_text,
            "notes": self.notes,
        }


@dataclass
class CaptureResult:
    """Everything observed for one query, used to compute metrics."""

    retrieved: list[dict] = field(default_factory=list)   # pre-rerank, Qdrant order
    reranked: list[dict] = field(default_factory=list)    # post-rerank, final order
    context: str = ""
    retrieve_s: float = 0.0
    rerank_s: float = 0.0


def _coerce_facts(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if str(v).strip()]


def load_curated(path: Path = CURATED_PATH) -> list[GoldItem]:
    """Load the hand-authored gold set (YAML)."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    items: list[GoldItem] = []
    for i, r in enumerate(raw):
        items.append(
            GoldItem(
                id=r.get("id") or f"curated-{i:03d}",
                question=r["question"],
                expected_facts=_coerce_facts(r.get("expected_facts")),
                set_name="curated",
                restaurant=r.get("restaurant"),
                category=r.get("category", "general"),
                expected_answer=r.get("expected_answer"),
                notes=r.get("notes", ""),
            )
        )
    return items


def load_synthetic(path: Path = SYNTHETIC_PATH) -> list[GoldItem]:
    """Load the LLM-generated gold set (JSON, written by generate_synthetic)."""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = raw.get("items", raw) if isinstance(raw, dict) else raw
    items: list[GoldItem] = []
    for i, r in enumerate(records):
        items.append(
            GoldItem(
                id=r.get("id") or f"synthetic-{i:03d}",
                question=r["question"],
                expected_facts=_coerce_facts(r.get("expected_facts")),
                set_name="synthetic",
                restaurant=r.get("restaurant"),
                category=r.get("category", "general"),
                expected_answer=r.get("expected_answer"),
                source_id=r.get("source_id"),
                source_text=r.get("source_text"),
                notes=r.get("notes", ""),
            )
        )
    return items


def load_gold(set_name: str = "all") -> list[GoldItem]:
    """Load 'curated', 'synthetic', or 'all' gold items."""
    if set_name == "curated":
        return load_curated()
    if set_name == "synthetic":
        return load_synthetic()
    if set_name == "all":
        return load_curated() + load_synthetic()
    raise ValueError(f"unknown gold set '{set_name}' (use curated|synthetic|all)")
