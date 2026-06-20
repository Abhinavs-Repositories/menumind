import json
import logging
import re
from pathlib import Path
from typing import Optional

from utils import strip_html_comments

logger = logging.getLogger(__name__)

_PAGE_MARKER_RE = re.compile(r"<!-- (?:text|table|figure), from page (\d+)")


class Chunk:
    """A single text chunk from a menu document."""

    __slots__ = ("chunk_id", "page_number", "text", "char_count", "chunk_type", "restaurant")

    def __init__(
        self,
        chunk_id: int,
        page_number: int,
        text: str,
        chunk_type: str = "page",
        restaurant: str = "",
    ):
        self.chunk_id = chunk_id
        self.page_number = page_number
        self.text = text
        self.char_count = len(text)
        self.chunk_type = chunk_type
        self.restaurant = restaurant

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "page_number": self.page_number,
            "text": self.text,
            "char_count": self.char_count,
            "chunk_type": self.chunk_type,
            "restaurant": self.restaurant,
        }


class MenuChunker:
    """Split parsed menu documents into chunks for embedding."""

    def chunk_markdown(self, markdown_path: str) -> list[Chunk]:
        """Split a raw markdown file into page-level chunks."""
        path = Path(markdown_path)
        content = path.read_text(encoding="utf-8")

        markers = [
            (int(m.group(1)), m.start())
            for m in _PAGE_MARKER_RE.finditer(content)
        ]

        if not markers:
            cleaned = strip_html_comments(content)
            if cleaned:
                return [Chunk(chunk_id=0, page_number=0, text=cleaned)]
            return []

        markers.sort(key=lambda x: x[1])
        chunks: list[Chunk] = []
        current_page: Optional[int] = None
        page_start = markers[0][1]

        for page_num, pos in markers:
            if current_page is not None and page_num != current_page:
                text = strip_html_comments(content[page_start:pos])
                if text:
                    chunks.append(
                        Chunk(chunk_id=len(chunks), page_number=current_page, text=text)
                    )
                page_start = pos
            if current_page != page_num:
                current_page = page_num

        if current_page is not None:
            text = strip_html_comments(content[page_start:])
            if text:
                chunks.append(
                    Chunk(chunk_id=len(chunks), page_number=current_page, text=text)
                )

        logger.info("Chunked %s: %d page-level chunks", path.name, len(chunks))
        return chunks

    def chunk_json(self, json_path: str) -> list[Chunk]:
        """Extract element-level chunks from an agentic-doc JSON file.

        Produces ~25 fine-grained chunks per document (one per text/table/figure
        element), giving much higher RAG precision than page-level chunks.
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_chunks = data.get("chunks", [])
        if not raw_chunks:
            logger.warning("No chunks found in %s", Path(json_path).name)
            return []

        chunks: list[Chunk] = []
        for i, raw in enumerate(raw_chunks):
            text = raw.get("text") or raw.get("content") or raw.get("markdown") or ""
            cleaned = strip_html_comments(text)
            if not cleaned:
                continue

            page_num = raw.get("page", 0)
            if page_num == 0 and "grounding" in raw:
                g = raw["grounding"]
                if isinstance(g, list) and g:
                    page_num = g[0].get("page", 0)
                elif isinstance(g, dict):
                    page_num = g.get("page", 0)

            chunks.append(
                Chunk(
                    chunk_id=len(chunks),
                    page_number=page_num,
                    text=cleaned,
                    chunk_type=raw.get("chunk_type", "element"),
                )
            )

        logger.info(
            "Chunked %s: %d element-level chunks",
            Path(json_path).name,
            len(chunks),
        )
        return chunks

    def chunk_file(
        self,
        markdown_path: str,
        json_path: Optional[str] = None,
    ) -> list[Chunk]:
        """Chunk a document, preferring element-level from JSON when available."""
        if json_path and Path(json_path).exists():
            chunks = self.chunk_json(json_path)
            if chunks:
                return chunks
            logger.info("JSON chunking yielded nothing, falling back to markdown")

        return self.chunk_markdown(markdown_path)
