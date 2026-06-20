import logging
import re
import time
from typing import Optional

from groq import Groq
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from config import get_settings
from embedder import GeminiEmbedder
from utils import strip_html_comments

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful restaurant menu assistant.

Answer questions using ONLY the provided context documents. Include specific
details like prices, ingredients, and descriptions when available. If the
context does not contain enough information, say so politely — never make
things up."""


class MenuRAG:
    """RAG engine: Gemini embeddings + Qdrant retrieval + Groq generation."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        embedder: Optional[GeminiEmbedder] = None,
    ):
        settings = get_settings()
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.top_k = settings.rag_top_k
        self.top_k_rerank = settings.rag_top_k_rerank
        self.min_score = settings.rag_min_score
        self.max_context = settings.rag_max_context_chars
        self.groq_model = settings.groq_model

        self.embedder = embedder or GeminiEmbedder()
        self.qdrant = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=30,
        )
        self.groq = Groq(api_key=settings.groq_api_key)

        info = self.qdrant.get_collection(self.collection_name)
        logger.info(
            "RAG ready: collection '%s' (%d vectors), model '%s'",
            self.collection_name,
            info.points_count,
            self.groq_model,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        page_filter: Optional[int] = None,
    ) -> dict:
        """Run the full RAG pipeline: embed → retrieve → generate."""
        start = time.time()

        docs = self._retrieve(question, page_filter)
        if not docs:
            return {
                "question": question,
                "answer": "I couldn't find relevant information in the menu database. Try rephrasing your question.",
                "sources": [],
                "retrieval_count": 0,
                "time_s": round(time.time() - start, 2),
            }

        docs = self._rerank(question, docs)
        context = self._build_context(docs)
        answer, gen_time = self._generate(question, context)

        elapsed = time.time() - start
        logger.info("RAG answered in %.2fs (gen %.2fs)", elapsed, gen_time)

        return {
            "question": question,
            "answer": answer,
            "sources": [
                {
                    "page": d["page_number"],
                    "score": round(d["score"], 4),
                    "preview": d["text"][:200],
                }
                for d in docs[:3]
            ],
            "retrieval_count": len(docs),
            "time_s": round(elapsed, 2),
        }

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _retrieve(
        self,
        query: str,
        page_filter: Optional[int] = None,
    ) -> list[dict]:
        query_vec = self.embedder.embed_text(query, task_type="RETRIEVAL_QUERY")

        search_filter = None
        if page_filter is not None:
            search_filter = Filter(
                must=[FieldCondition(key="page_number", match=MatchValue(value=page_filter))]
            )

        results = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=query_vec,
            query_filter=search_filter,
            limit=self.top_k,
            score_threshold=self.min_score,
            with_payload=True,
            with_vectors=False,
        )

        docs = []
        for hit in results.points:
            docs.append(
                {
                    "id": hit.id,
                    "score": hit.score,
                    "text": strip_html_comments(hit.payload.get("text", "")),
                    "page_number": hit.payload.get("page_number"),
                    "chunk_id": hit.payload.get("chunk_id"),
                }
            )

        logger.info("Retrieved %d documents (min_score=%.2f)", len(docs), self.min_score)
        return docs

    def _rerank(self, query: str, docs: list[dict]) -> list[dict]:
        """Embedding-based reranking using Gemini cosine similarity."""
        if len(docs) <= self.top_k_rerank:
            return docs

        import numpy as np

        query_vec = np.array(self.embedder.embed_text(query, task_type="RETRIEVAL_QUERY"))
        doc_vecs = self.embedder.embed_texts(
            [d["text"][:500] for d in docs],
            task_type="RETRIEVAL_DOCUMENT",
        )

        scored = []
        for doc, dvec in zip(docs, doc_vecs):
            dv = np.array(dvec)
            cos = float(np.dot(query_vec, dv) / (np.linalg.norm(query_vec) * np.linalg.norm(dv) + 1e-10))
            doc["rerank_score"] = cos
            scored.append(doc)

        scored.sort(key=lambda d: d["rerank_score"], reverse=True)
        return scored[: self.top_k_rerank]

    def _build_context(self, docs: list[dict]) -> str:
        parts: list[str] = []
        total = 0
        for i, doc in enumerate(docs):
            text = doc["text"].strip()
            if total + len(text) > self.max_context:
                break
            page = doc.get("page_number", "?")
            part = f"[Page {page}]\n{text}"
            parts.append(part)
            total += len(part)
        return "\n\n".join(parts)

    def _generate(self, question: str, context: str) -> tuple[str, float]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{context}\n\nAnswer based on the context above.",
            },
        ]

        start = time.time()
        resp = self.groq.chat.completions.create(
            model=self.groq_model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000,
        )
        gen_time = time.time() - start

        answer = resp.choices[0].message.content
        return answer, gen_time
