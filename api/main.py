"""MenuMind backend API.

A thin FastAPI layer over the existing RAG engine. Two endpoints power the
mobile app:

    GET  /menus  -> ["Marriott", "Taj", ...]      (pick one menu)
    POST /chat   -> Server-Sent Events stream      (streamed answer)

Run locally from the repo root:
    uvicorn api.main:app --reload --port 8000
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Allow `import rag` etc. when launched as `api.main:app` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from rag import MenuRAG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("menumind.api")

app = FastAPI(title="MenuMind API", version="1.0.0")

# CORS: the Expo app (and web build) call this from another origin.
# ALLOWED_ORIGINS is a comma-separated list; "*" by default for dev.
_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy singleton: build clients once, reuse across requests.
_rag: Optional[MenuRAG] = None


def get_rag() -> MenuRAG:
    global _rag
    if _rag is None:
        logger.info("Initializing MenuRAG ...")
        _rag = MenuRAG()
    return _rag


class ChatRequest(BaseModel):
    question: str
    restaurant: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/menus")
def menus() -> list[str]:
    """List the restaurants/menus available to chat with."""
    try:
        return get_rag().list_restaurants()
    except Exception as exc:
        logger.exception("listing menus failed")
        raise HTTPException(status_code=503, detail=str(exc))


def _sse(event: str, data) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """Stream a RAG answer for a question scoped to one restaurant."""
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    rag = get_rag()

    def event_stream():
        try:
            for ev in rag.ask_stream(req.question, restaurant=req.restaurant):
                yield _sse(ev["type"], ev["data"])
        except Exception as exc:
            logger.exception("chat stream failed")
            yield _sse("error", str(exc))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
