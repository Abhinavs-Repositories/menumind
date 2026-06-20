import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)


class Settings(BaseSettings):
    # --- Google Gemini (embeddings) ---
    google_api_key: str = Field(default="")
    embedding_model: str = "models/gemini-embedding-001"
    embedding_dimensions: int = 768

    # --- Google Gemini (menu parsing / vision) ---
    vision_model: str = "gemini-2.5-flash"

    # --- Qdrant Cloud (vector store) ---
    qdrant_url: str = Field(default="")
    qdrant_api_key: str = Field(default="")
    qdrant_collection_name: str = "menu_embeddings"
    qdrant_batch_size: int = 50

    # --- Groq (LLM generation) ---
    groq_api_key: str = Field(default="")
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Agentic Doc (PDF parsing) ---
    vision_agent_api_key: str = Field(default="")

    # --- RAG tuning ---
    rag_top_k: int = 10
    rag_top_k_rerank: int = 5
    rag_min_score: float = 0.25
    rag_max_context_chars: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
