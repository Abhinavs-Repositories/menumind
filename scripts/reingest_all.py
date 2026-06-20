#!/usr/bin/env python3
"""Re-ingest every menu into one Qdrant collection, tagged with `restaurant`.

Reuses the already-parsed JSON in parse_output/json/ (skips the expensive
Gemini vision parse). For each menu stem it picks the most recent JSON file,
chunks it, tags every chunk with a clean restaurant name, embeds, and ingests.

Usage:
    python scripts/reingest_all.py                 # all menus in parse_output/json
    python scripts/reingest_all.py --collection menu_embeddings
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chunker import MenuChunker
from embedder import GeminiEmbedder
from ingestor import QdrantIngestor
from utils import restaurant_label

logger = logging.getLogger(__name__)


def latest_json_per_menu(json_dir: Path) -> dict[str, Path]:
    """Map each menu stem -> its most recent JSON file.

    Filenames look like `Taj_20260619_233946.json`; the stem before the first
    timestamp segment is the menu key. Lexical max == most recent timestamp.
    """
    by_menu: dict[str, Path] = {}
    for path in sorted(json_dir.glob("*.json")):
        # Strip the trailing _YYYYMMDD_HHMMSS to recover the original stem.
        parts = path.stem.rsplit("_", 2)
        menu_stem = parts[0] if len(parts) == 3 and parts[1].isdigit() else path.stem
        # sorted() is ascending, so the last assignment wins (newest timestamp).
        by_menu[menu_stem] = path
    return by_menu


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    ap = argparse.ArgumentParser(description="Re-ingest all menus with restaurant tags")
    ap.add_argument("-c", "--collection", default=None, help="Qdrant collection name")
    ap.add_argument(
        "--json-dir",
        default="parse_output/json",
        help="Directory of parsed menu JSON files",
    )
    args = ap.parse_args()

    json_dir = Path(args.json_dir)
    menus = latest_json_per_menu(json_dir)
    if not menus:
        print(f"No JSON files found in {json_dir}")
        sys.exit(1)

    print("=" * 60)
    print(f"RE-INGEST {len(menus)} MENUS -> one collection (tagged by restaurant)")
    print("=" * 60)
    for stem, path in menus.items():
        print(f"  {restaurant_label(stem):<16} <- {path.name}")

    chunker = MenuChunker()
    embedder = GeminiEmbedder()
    ingestor = QdrantIngestor(collection_name=args.collection)

    total = 0
    for i, (stem, json_path) in enumerate(menus.items()):
        restaurant = restaurant_label(stem)
        print(f"\n[{i + 1}/{len(menus)}] {restaurant}")

        chunks = chunker.chunk_json(str(json_path))
        if not chunks:
            print("  (no chunks, skipping)")
            continue
        for c in chunks:
            c.restaurant = restaurant

        embedded = embedder.embed_chunks(chunks)

        # Wipe + recreate on the very first menu, then append the rest.
        if i == 0:
            ingestor.ensure_collection(embedder.dimensions, recreate=True)
        stats = ingestor.ingest(embedded)
        total += stats["ingested"]
        print(f"  -> {stats['ingested']} points ingested")

    info = ingestor.collection_info()
    print(f"\nDone. Collection '{info['name']}': {info['points']} points total "
          f"({total} ingested this run)")


if __name__ == "__main__":
    main()
