import io
from pathlib import Path

import fitz
from PIL import Image

from menu_parser.exceptions import UnsupportedFileType

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
_PDF_SUFFIX = ".pdf"

# 150-200 DPI is the practical sweet spot for menu text: below ~150, small
# print and fraction characters (e.g. "1/2 lb") blur enough to cause OCR
# misreads; above ~200, per-page payload size (and Gemini latency/cost)
# grows faster than extraction quality improves. 180 splits the difference.
DEFAULT_DPI = 180


def load_pages_as_images(file_path: Path, dpi: int = DEFAULT_DPI) -> list[Image.Image]:
    """Load a PDF or image file as a list of PIL Images, one per page."""
    suffix = file_path.suffix.lower()

    if suffix in _IMAGE_SUFFIXES:
        return [Image.open(file_path).convert("RGB")]

    if suffix != _PDF_SUFFIX:
        raise UnsupportedFileType(f"Unsupported file type: {suffix}")

    zoom = dpi / 72  # PyMuPDF renders at 72 DPI by default
    matrix = fitz.Matrix(zoom, zoom)

    images: list[Image.Image] = []
    with fitz.open(file_path) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            images.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
    return images
