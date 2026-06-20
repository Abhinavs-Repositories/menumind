import json
import logging
import time
from pathlib import Path
from typing import Optional

from menu_parser.gemini_client import GeminiMenuClient

logger = logging.getLogger(__name__)


class ParseResult:
    """Container for a single parsed document."""

    def __init__(
        self,
        file_name: str,
        raw_markdown: str,
        json_path: Optional[str],
        raw_markdown_path: str,
        chunks_count: int,
        extraction: Optional[dict],
        processing_time: float,
    ):
        self.file_name = file_name
        self.raw_markdown = raw_markdown
        self.json_path = json_path
        self.raw_markdown_path = raw_markdown_path
        self.chunks_count = chunks_count
        self.extraction = extraction
        self.processing_time = processing_time


class MenuParser:
    """Parse PDF/image menus into markdown + JSON using Gemini Flash vision."""

    def __init__(self, output_dir: str = "parse_output"):
        self.output_dir = Path(output_dir)
        self.json_dir = self.output_dir / "json"
        self.raw_md_dir = self.output_dir / "raw_markdown"
        for d in (self.json_dir, self.raw_md_dir):
            d.mkdir(parents=True, exist_ok=True)
        self._client = GeminiMenuClient()

    def parse_file(
        self,
        file_path: str,
        extract_fields: bool = True,
    ) -> ParseResult:
        """Parse a single PDF or image file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        logger.info("Parsing %s ...", path.name)
        start = time.time()

        result = self._client.parse_menu(path)
        elapsed = time.time() - start

        raw_md_path = self.raw_md_dir / f"{path.stem}_raw.md"
        raw_md_path.write_text(result.markdown, encoding="utf-8")

        # chunker.py's chunk_json() expects {"chunks": [{"text", "page", "chunk_type"}, ...]}
        chunks = [
            {"text": block["text"], "page": page["page_number"], "chunk_type": block["block_type"]}
            for page in result.raw_response.get("pages", [])
            for block in page.get("blocks", [])
        ]
        json_path = self.json_dir / f"{path.stem}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        json_path.write_text(
            json.dumps({"chunks": chunks}, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        extraction = result.structured.model_dump() if extract_fields else None

        logger.info("Parsed %s: %d chunks, %.1fs", path.name, len(chunks), elapsed)

        return ParseResult(
            file_name=path.name,
            raw_markdown=result.markdown,
            json_path=str(json_path),
            raw_markdown_path=str(raw_md_path),
            chunks_count=len(chunks),
            extraction=extraction,
            processing_time=elapsed,
        )

    def parse_folder(
        self,
        folder_path: str,
        patterns: list[str] | None = None,
        extract_fields: bool = True,
    ) -> list[ParseResult]:
        """Parse all supported files in a folder."""
        folder = Path(folder_path)
        if not folder.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder}")

        if patterns is None:
            patterns = ["*.pdf", "*.jpg", "*.jpeg", "*.png"]

        files: list[Path] = []
        for pat in patterns:
            files.extend(folder.rglob(pat))
        files = sorted(set(files))

        if not files:
            logger.warning("No supported files found in %s", folder)
            return []

        logger.info("Found %d files in %s", len(files), folder)

        results = []
        for f in files:
            try:
                results.append(self.parse_file(str(f), extract_fields=extract_fields))
            except Exception:
                logger.exception("Failed to parse %s", f.name)

        return results
