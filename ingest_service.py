"""Ingest an uploaded menu file (PDF/image) into the vector store.

Reuses the existing pipeline in-memory: Gemini vision parse -> per-block chunks
(tagged with the restaurant) -> Gemini embeddings -> Qdrant upsert. The only
disk write is a short-lived temp copy of the upload (PyMuPDF/Pillow need a path).
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from chunker import Chunk
from embedder import GeminiEmbedder
from ingestor import QdrantIngestor
from menu_parser.gemini_client import GeminiMenuClient
from utils import strip_html_comments

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}


def ingest_menu_file(
    file_bytes: bytes,
    filename: str,
    restaurant: str,
    collection: Optional[str] = None,
) -> dict:
    """Parse + embed + ingest one uploaded menu file. Returns a summary dict."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported file type '{suffix}'. Use PDF, JPG, or PNG.")

    restaurant = restaurant.strip()
    if not restaurant:
        raise ValueError("restaurant name is required")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        logger.info("Parsing upload '%s' as restaurant '%s'", filename, restaurant)
        result = GeminiMenuClient().parse_menu(tmp_path)

        chunks: list[Chunk] = []
        for page in result.raw_response.get("pages", []):
            for block in page.get("blocks", []):
                text = strip_html_comments(block.get("text", ""))
                if not text:
                    continue
                chunks.append(
                    Chunk(
                        chunk_id=len(chunks),
                        page_number=page.get("page_number", 0),
                        text=text,
                        chunk_type=block.get("block_type", "element"),
                        restaurant=restaurant,
                    )
                )

        if not chunks:
            return {"restaurant": restaurant, "pages": result.page_count, "chunks": 0}

        embedded = GeminiEmbedder().embed_chunks(chunks)
        ingestor = QdrantIngestor(collection_name=collection)
        stats = ingestor.ingest(embedded)  # ensures collection + payload indexes

        logger.info("Ingested '%s': %d chunks", restaurant, stats.get("ingested", 0))
        return {
            "restaurant": restaurant,
            "pages": result.page_count,
            "chunks": stats.get("ingested", len(chunks)),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
