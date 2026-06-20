#!/usr/bin/env python3
"""Eyeball-quality comparison: new Gemini parser vs old agentic-doc parser.

Usage:
    python scripts/compare_outputs.py menu_inputs
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from menu_parser.gemini_client import GeminiMenuClient

_SUFFIXES = ("*.pdf", "*.jpg", "*.jpeg", "*.png")


def _summarize_gemini(client: GeminiMenuClient, path: Path) -> dict:
    result = client.parse_menu(path)
    s = result.structured
    return {
        "pages": result.page_count,
        "items": len(s.item_names),
        "prices": len(s.prices),
        "sections": len(s.menu_sections),
        "restaurant_name": s.restaurant_name,
    }


def _summarize_agentic_doc(path: Path) -> dict | None:
    try:
        from agentic_doc.parse import parse as agentic_parse
    except ImportError:
        return None

    try:
        results = agentic_parse(str(path))
    except Exception as e:
        return {"error": str(e)}

    if not results:
        return {"error": "no results"}

    result = results[0]
    extraction = {}
    if getattr(result, "extraction", None) is not None:
        try:
            extraction = result.extraction.model_dump()
        except Exception:
            extraction = {}

    return {
        "chunks": len(getattr(result, "chunks", [])),
        "items": len(extraction.get("item_names", [])),
        "prices": len(extraction.get("prices", [])),
        "sections": len(extraction.get("menu_sections", [])),
        "restaurant_name": extraction.get("restaurant_name"),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/compare_outputs.py <folder>")
        sys.exit(1)

    folder = Path(sys.argv[1])
    files = sorted({p for pat in _SUFFIXES for p in folder.glob(pat)})
    if not files:
        print(f"No menu files found in {folder}")
        return

    client = GeminiMenuClient()

    for f in files:
        print(f"\n=== {f.name} ===")

        try:
            g = _summarize_gemini(client, f)
            print(
                f"  gemini      : {g['items']} items, {g['prices']} prices, "
                f"{g['sections']} sections, {g['pages']} pages, "
                f"restaurant={g['restaurant_name']!r}"
            )
        except Exception as e:
            print(f"  gemini      : FAILED ({e})")

        a = _summarize_agentic_doc(f)
        if a is None:
            print("  agentic-doc : not installed, skipped")
        elif "error" in a:
            print(f"  agentic-doc : FAILED ({a['error']})")
        else:
            print(
                f"  agentic-doc : {a['items']} items, {a['prices']} prices, "
                f"{a['sections']} sections, {a['chunks']} chunks, "
                f"restaurant={a['restaurant_name']!r}"
            )


if __name__ == "__main__":
    main()
