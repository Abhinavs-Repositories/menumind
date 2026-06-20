import logging
import time
from typing import Optional

from google import genai
from google.genai import types

from chunker import Chunk
from config import get_settings
from utils import truncate

logger = logging.getLogger(__name__)


class EmbeddedChunk:
    """A chunk with its embedding vector attached."""

    __slots__ = ("chunk", "embedding")

    def __init__(self, chunk: Chunk, embedding: list[float]):
        self.chunk = chunk
        self.embedding = embedding


class GeminiEmbedder:
    """Generate embeddings using Google Gemini (gemini-embedding-001).

    Default: 768 dimensions, free tier via Google AI Studio.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        settings = get_settings()
        self._api_key = api_key or settings.google_api_key
        if not self._api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Get one free at https://aistudio.google.com/apikey"
            )
        self._client = genai.Client(api_key=self._api_key)
        self.model = model or settings.embedding_model
        self.dimensions = dimensions or settings.embedding_dimensions

    def embed_text(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
    ) -> list[float]:
        """Embed a single text string. Use RETRIEVAL_QUERY for search queries."""
        result = self._client.models.embed_content(
            model=self.model,
            contents=truncate(text, max_chars=8000),
            config=types.EmbedContentConfig(
                output_dimensionality=self.dimensions,
                task_type=task_type,
            ),
        )
        return list(result.embeddings[0].values)

    def embed_texts(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Embed multiple texts in batches. Use RETRIEVAL_DOCUMENT for indexing."""
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = [truncate(t, max_chars=8000) for t in texts[i : i + batch_size]]
            result = self._client.models.embed_content(
                model=self.model,
                contents=batch,
                config=types.EmbedContentConfig(
                    output_dimensionality=self.dimensions,
                    task_type=task_type,
                ),
            )
            all_embeddings.extend(list(e.values) for e in result.embeddings)

        return all_embeddings

    def embed_chunks(
        self,
        chunks: list[Chunk],
        batch_size: int = 100,
    ) -> list[EmbeddedChunk]:
        """Embed a list of Chunk objects for ingestion into a vector store."""
        if not chunks:
            return []

        logger.info("Embedding %d chunks with %s (%d-dim) ...", len(chunks), self.model, self.dimensions)
        start = time.time()

        texts = [c.text for c in chunks]
        embeddings = self.embed_texts(texts, task_type="RETRIEVAL_DOCUMENT", batch_size=batch_size)

        elapsed = time.time() - start
        logger.info("Embedded %d chunks in %.1fs (%.0f chunks/s)", len(chunks), elapsed, len(chunks) / elapsed if elapsed > 0 else 0)

        return [
            EmbeddedChunk(chunk=chunk, embedding=emb)
            for chunk, emb in zip(chunks, embeddings)
        ]
