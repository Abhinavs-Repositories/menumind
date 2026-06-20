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
    """Top-level schema Gemini fills in a single multimodal call."""

    pages: list[MenuPage] = Field(default_factory=list)
    extraction: MenuExtractionFields


class MenuParseResult(BaseModel):
    """Result handed back to parser.py."""

    markdown: str
    structured: MenuExtractionFields
    page_count: int
    raw_response: dict


SYSTEM_PROMPT = """You are a precise menu-document parser. You will be shown every page of a \
restaurant menu, in order, as images. Convert them into the JSON schema you've been given. \
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


def _build_user_prompt(page_count: int) -> str:
    return (
        f"This menu has {page_count} page(s), provided as images in order below "
        f"(page 1 first). Parse all pages into the required JSON schema."
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

    def parse_menu(self, file_path: Path) -> MenuParseResult:
        """Parse a PDF or image file into Markdown + structured menu fields."""
        file_path = Path(file_path)
        images = load_pages_as_images(file_path)

        contents = [_build_user_prompt(len(images)), *images]
        response = self._generate(contents)

        try:
            parsed = GeminiMenuResponse.model_validate_json(response.text)
        except (ValidationError, ValueError) as e:
            raise ParseValidationError(
                f"Gemini output failed schema validation for {file_path.name}: {e}",
                raw_response={"text": response.text},
            ) from e

        markdown = _stitch_markdown(parsed.pages)
        return MenuParseResult(
            markdown=markdown,
            structured=parsed.extraction,
            page_count=len(images),
            raw_response=parsed.model_dump(),
        )

    @retry(
        retry=retry_if_exception_type(errors.ServerError),
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
                    response_schema=GeminiMenuResponse,
                    # Disable extended thinking: this is deterministic OCR +
                    # structured extraction, not multi-step reasoning, so the
                    # thinking budget only adds latency/cost here.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    temperature=0.1,
                ),
            )
        except errors.ClientError as e:
            if e.code == 429:
                raise RateLimitExceeded(
                    f"Gemini free-tier rate limit hit (15 RPM / 1500 req/day): {e}"
                ) from e
            raise


def _stitch_markdown(pages: list[MenuPage]) -> str:
    parts = []
    for page in pages:
        for block in page.blocks:
            parts.append(f"<!-- {block.block_type}, from page {page.page_number} -->\n{block.text}")
    return "\n\n".join(parts)
