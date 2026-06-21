"""Tiny structured-JSON LLM helper for the eval suite (Groq or Gemini backend).

Why this exists: the judge and the synthetic-question generator both need "given a
prompt, return JSON matching a schema". The default backend is **Groq** because
Gemini's free tier caps generate_content at ~20 requests/day (shared with menu
parsing), which is far too small to judge a full gold set. Gemini stays available
as an option.
"""

from __future__ import annotations

import json
import logging
from typing import Type, TypeVar

from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Decoupled from the app's generator (llama-3.3-70b) to avoid a model grading itself.
DEFAULT_GROQ_JUDGE = "openai/gpt-oss-120b"
DEFAULT_GROQ_GEN = "llama-3.3-70b-versatile"
DEFAULT_GEMINI = "gemini-2.5-flash"


def _is_rate_limit(exc: BaseException) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 429:
        return True
    return "429" in str(exc) or "rate_limit" in str(exc).lower() or "resource_exhausted" in str(exc).lower()


def _schema_hint(schema: Type[BaseModel]) -> str:
    """Compact field list so JSON-mode models know exactly what to return."""
    props = schema.model_json_schema().get("properties", {})
    fields = ", ".join(f'"{k}"' for k in props)
    return f"Return ONLY a JSON object with these keys: {fields}."


class _Backend:
    name: str

    def complete(self, system: str, user: str, schema: Type[T], temperature: float) -> T:  # noqa: D401
        raise NotImplementedError


class GroqBackend(_Backend):
    def __init__(self, model: str):
        from groq import Groq

        self.model = model
        self.name = f"groq:{model}"
        self._client = Groq(api_key=get_settings().groq_api_key)

    @retry(retry=retry_if_exception(_is_rate_limit),
           wait=wait_exponential(multiplier=2, min=3, max=45),
           stop=stop_after_attempt(6), reraise=True)
    def complete(self, system: str, user: str, schema: Type[T], temperature: float) -> T:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": f"{system}\n\n{_schema_hint(schema)}"},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return schema.model_validate_json(resp.choices[0].message.content)


class GeminiBackend(_Backend):
    def __init__(self, model: str):
        from google import genai

        self.model = model
        self.name = f"gemini:{model}"
        self._genai = genai
        self._client = genai.Client(api_key=get_settings().google_api_key)

    @retry(retry=retry_if_exception(_is_rate_limit),
           wait=wait_exponential(multiplier=2, min=5, max=60),
           stop=stop_after_attempt(6), reraise=True)
    def complete(self, system: str, user: str, schema: Type[T], temperature: float) -> T:
        from google.genai import types

        resp = self._client.models.generate_content(
            model=self.model,
            contents=[user],
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                temperature=temperature,
            ),
        )
        text = getattr(resp, "text", None)
        if not text:
            raise ValueError("empty Gemini response")
        return schema.model_validate_json(text)


def make_backend(backend: str, model: str | None = None, *, role: str = "judge") -> _Backend:
    """Build a backend. role picks the default model when none is given."""
    if backend == "groq":
        return GroqBackend(model or (DEFAULT_GROQ_JUDGE if role == "judge" else DEFAULT_GROQ_GEN))
    if backend == "gemini":
        return GeminiBackend(model or DEFAULT_GEMINI)
    raise ValueError(f"unknown backend '{backend}' (use groq|gemini)")
