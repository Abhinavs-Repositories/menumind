import logging
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import get_settings
from menu_parser.exceptions import ParseValidationError, RateLimitExceeded
from menu_parser.pdf_to_images import load_pages_as_images

logger = logging.getLogger(__name__)


class MenuExtractionFields(BaseModel):
    """Structured fields extracted from a menu document.

    Flat/parallel-array schema: item_names/prices/descriptions are NOT
    positionally bound to each other or to menu_sections -- the model is
    instructed to keep them aligned, but nothing in the schema enforces
    it. A nested MenuSection -> List[MenuItem(name, price, description)]
    schema would bind each item's fields to one object instead of relying
    on parallel arrays staying in sync, which matters more as menu
    page-density goes up. Kept flat here on request; revisit if the
    compare_outputs.py eval shows item/price drift on dense menus.
    """

    restaurant_name: Optional[str] = Field(default=None)
    menu_sections: list[str] = Field(default_factory=list)
    item_names: list[str] = Field(default_factory=list)
    prices: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    beverages: list[str] = Field(default_factory=list)
    contact_info: Optional[str] = Field(default=None)
    hours: Optional[str] = Field(default=None)
    special_offers: list[str] = Field(default_factory=list)


class MenuBlock(BaseModel):
    """One logical content block on a page, mirroring agentic-doc's chunk types."""

    block_type: str = Field(description='One of: "text", "table", "figure"')
    text: str = Field(description="Markdown for this block only")


class MenuPage(BaseModel):
    page_number: int
    blocks: list[MenuBlock] = Field(default_factory=list)


class GeminiMenuResponse(BaseModel):
    """Aggregate result shape (all pages stitched together)."""

    pages: list[MenuPage] = Field(default_factory=list)
    extraction: MenuExtractionFields


class SinglePageResponse(BaseModel):
    """Schema Gemini fills for ONE page. Parsing per page bounds each response
    so a single dense/looping page can't balloon into an unterminated megabyte
    of JSON, and one bad page no longer fails the whole document."""

    blocks: list[MenuBlock] = Field(default_factory=list)
    extraction: MenuExtractionFields


class MenuParseResult(BaseModel):
    """Result handed back to parser.py."""

    markdown: str
    structured: MenuExtractionFields
    page_count: int
    raw_response: dict


SYSTEM_PROMPT = """You are a precise menu-document parser. You will be shown one page of a \
restaurant menu as an image. Convert it into the JSON schema you've been given. \
Follow these rules exactly:

1. ITEM-PRICE BINDING: Menus rarely use table borders. Items and their prices are usually \
aligned by whitespace or dot-leaders on the same visual row, not by an explicit table \
structure. Use horizontal position on the page (the price sits at the same row, typically \
right-aligned) to associate each price with the correct item -- do not assume order alone, \
and do not let a price drift onto the wrong item because the dot-leader is long. \
CRITICAL: when you write the markdown for a table block, you MUST put each item's price on \
the same line as that item, e.g. "Item Name — 925" or as a markdown table row \
"| Item Name | 925 | description |". NEVER write all item names as one group followed by \
all prices as a separate group further down -- even though the source image may render names \
and prices as two visually separate columns, your output text must interleave them per row, \
because the markdown text (not the image) is what gets stored and searched later.

2. HEADERS VS ITEMS: Distinguish section/category headers (e.g. "STARTERS", "MAIN COURSE") \
from item names by visual hierarchy -- larger font, bold weight, all-caps, or extra spacing \
above -- not merely by vertical position on the page. A header introduces a new menu_section; \
items below it belong to that section until the next header.

3. READING ORDER: Menus are frequently laid out in multiple side-by-side sections (e.g. \
the left half of a page lists "Starters" and the right half lists "Salads"). Read each \
section/column as a complete top-to-bottom unit before moving to the next one, so the \
markdown preserves natural reading order. This is about which section you read first, not \
about separating an item from its own price -- name and price on the same row always stay \
together per rule 1, even within a single section's column of rows.

4. NO HALLUCINATION: Only output text and prices you can actually read in the image. If a \
price is illegible or genuinely absent, leave it out rather than guessing. Never invent items, \
sections, or contact details that are not visibly printed.

5. MISSING PRICES: Some items intentionally have no fixed price (e.g. "Market Price", \
"Seasonal", "Ask your server", or simply blank). In that case, record the item name and use \
the literal text shown (e.g. "Market Price") as its price entry, or omit the price entry \
entirely if nothing at all is printed -- do not invent a numeric price.

For every page, emit one or more blocks. Use block_type "table" for grid/columnar item-price \
listings, "text" for prose (descriptions, headers, contact info, hours), and "figure" for \
photos/logos/decorative graphics with no extractable text (text may be empty for figures). \
Each block's text should be valid Markdown reflecting only that block's content, in reading \
order.

Separately, fill the `extraction` object with the menu's overall structured fields \
(restaurant name, the list of section names found, the list of item names, the list of \
prices, descriptions, beverages, contact info, hours, special offers), drawing only from what \
is visibly printed across all pages."""


def _build_page_prompt(page_number: int, total: int) -> str:
    return (
        f"This is page {page_number} of {total} of a restaurant menu, provided as "
        f"one image. Parse THIS page into the required JSON schema: its content "
        f"blocks, plus the structured fields visible on this page."
    )


class GeminiMenuClient:
    """Parses restaurant menu PDFs/images into Markdown + structured fields via Gemini Flash vision."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self._api_key = api_key or settings.google_api_key
        if not self._api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Get one free at https://aistudio.google.com/apikey"
            )
        self._client = genai.Client(api_key=self._api_key)
        self.model = model or settings.vision_model
        self.max_output_tokens = settings.vision_max_output_tokens

    def parse_menu(self, file_path: Path) -> MenuParseResult:
        """Parse a PDF or image file into Markdown + structured menu fields.

        Pages are parsed one at a time: this bounds each Gemini response (so a
        dense or looping page can't produce an unterminated megabyte of JSON)
        and isolates failures (a single unparseable page is skipped, not fatal).
        """
        file_path = Path(file_path)
        images = load_pages_as_images(file_path)

        pages: list[MenuPage] = []
        extractions: list[MenuExtractionFields] = []
        failures: list[str] = []

        for idx, image in enumerate(images, start=1):
            try:
                page = self._parse_page(image, idx, len(images))
            except RateLimitExceeded:
                # Quota/RPM is global, not page-specific — let the caller decide.
                raise
            except ParseValidationError as e:
                logger.warning(
                    "Skipping page %d/%d of %s: %s", idx, len(images), file_path.name, e
                )
                failures.append(f"p{idx}: {e}")
                continue
            pages.append(MenuPage(page_number=idx, blocks=page.blocks))
            extractions.append(page.extraction)

        if not pages:
            raise ParseValidationError(
                f"Gemini failed to parse any page of {file_path.name} "
                f"({'; '.join(failures) or 'no pages'})"
            )
        if failures:
            logger.warning(
                "%s: parsed %d/%d pages (%d skipped)",
                file_path.name, len(pages), len(images), len(failures),
            )

        extraction = _merge_extractions(extractions)
        markdown = _stitch_markdown(pages)
        aggregate = GeminiMenuResponse(pages=pages, extraction=extraction)
        return MenuParseResult(
            markdown=markdown,
            structured=extraction,
            page_count=len(images),
            raw_response=aggregate.model_dump(),
        )

    def _parse_page(self, image, page_number: int, total: int) -> SinglePageResponse:
        """Parse a single page image into blocks + structured fields."""
        response = self._generate([_build_page_prompt(page_number, total), image])
        _raise_if_truncated(response, page_number)

        text = getattr(response, "text", None)
        if not text:
            raise ParseValidationError(
                f"Gemini returned an empty response for page {page_number} "
                f"(possibly blocked or no extractable content)"
            )
        try:
            return SinglePageResponse.model_validate_json(text)
        except (ValidationError, ValueError) as e:
            raise ParseValidationError(
                f"page {page_number} failed schema validation: {e}",
                raw_response={"text": text[:2000]},
            ) from e

    @retry(
        retry=retry_if_exception_type((errors.ServerError, RateLimitExceeded)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _generate(self, contents: list):
        try:
            return self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=SinglePageResponse,
                    # Disable extended thinking: this is deterministic OCR +
                    # structured extraction, not multi-step reasoning, so the
                    # thinking budget only adds latency/cost here.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    temperature=0.1,
                    # Bound the output so a looping generation fails fast (caught
                    # as a truncation error) instead of emitting ~1MB of JSON.
                    max_output_tokens=self.max_output_tokens,
                ),
            )
        except errors.ClientError as e:
            if e.code == 429:
                # Transient per-minute RPM limits are retried by @retry above;
                # if they persist (daily quota), the final raise surfaces here.
                raise RateLimitExceeded(
                    f"Gemini free-tier rate limit hit (RPM / daily quota): {e}"
                ) from e
            raise


def _raise_if_truncated(response, page_number: int) -> None:
    """Detect a MAX_TOKENS cutoff and raise a clear error.

    Without this, a truncated response yields unterminated JSON and surfaces as
    a cryptic 'EOF while parsing a string' validation error.
    """
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return
    finish_reason = getattr(candidates[0], "finish_reason", None)
    name = getattr(finish_reason, "name", str(finish_reason) if finish_reason else "")
    if name == "MAX_TOKENS":
        raise ParseValidationError(
            f"page {page_number} response was truncated at the output-token limit "
            f"(finish_reason=MAX_TOKENS) — the page may be unusually dense, or the "
            f"model looped. Try raising VISION_MAX_OUTPUT_TOKENS or splitting the PDF."
        )


def _merge_extractions(parts: list[MenuExtractionFields]) -> MenuExtractionFields:
    """Combine per-page structured fields into one document-level extraction."""
    merged = MenuExtractionFields()
    for p in parts:
        merged.restaurant_name = merged.restaurant_name or p.restaurant_name
        merged.contact_info = merged.contact_info or p.contact_info
        merged.hours = merged.hours or p.hours
        merged.menu_sections.extend(p.menu_sections)
        merged.item_names.extend(p.item_names)
        merged.prices.extend(p.prices)
        merged.descriptions.extend(p.descriptions)
        merged.beverages.extend(p.beverages)
        merged.special_offers.extend(p.special_offers)
    # De-dupe section names while preserving first-seen order.
    merged.menu_sections = list(dict.fromkeys(merged.menu_sections))
    return merged


def _stitch_markdown(pages: list[MenuPage]) -> str:
    parts = []
    for page in pages:
        for block in page.blocks:
            parts.append(f"<!-- {block.block_type}, from page {page.page_number} -->\n{block.text}")
    return "\n\n".join(parts)
