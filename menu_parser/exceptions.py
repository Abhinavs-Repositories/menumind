from typing import Optional


class RateLimitExceeded(Exception):
    """Gemini's free-tier rate limit (RPM or daily quota) was hit.

    Raised immediately, without internal retry, so the caller controls
    backoff strategy (e.g. pausing a multi-file batch) instead of stalling
    silently inside a single parse_menu() call.
    """


class UnsupportedFileType(Exception):
    """The input file is not a PDF, JPG, or PNG."""


class ParseValidationError(Exception):
    """Gemini's response failed Pydantic validation against the schema."""

    def __init__(self, message: str, raw_response: Optional[dict] = None):
        super().__init__(message)
        self.raw_response = raw_response
