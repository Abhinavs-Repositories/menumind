import re

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Clean display names for the menu PDFs in menu_inputs/. Falls back to a
# title-cased filename stem for anything not listed here.
_RESTAURANT_LABELS = {
    "Mariott": "Marriott",
    "milestone": "Milestone",
    "mocha_cafe": "Mocha Cafe",
    "OONAtheOne": "OONA the One",
    "PunjabGrill": "Punjab Grill",
    "Taj": "Taj",
}


def restaurant_label(stem: str) -> str:
    """Map a menu filename stem to a clean, human-friendly restaurant name."""
    if stem in _RESTAURANT_LABELS:
        return _RESTAURANT_LABELS[stem]
    return stem.replace("_", " ").replace("-", " ").title()


def strip_html_comments(text: str) -> str:
    """Remove agentic-doc HTML coordinate comments from text."""
    cleaned = _HTML_COMMENT_RE.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def truncate(text: str, max_chars: int = 8000) -> str:
    """Truncate text to max_chars, appending ellipsis if trimmed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
