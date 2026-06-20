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
import threading
import uuid
from pathlib import Path
from typing import Optional

# Allow `import rag` etc. when launched as `api.main:app` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ingest_service import ingest_menu_file
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

# Optional shared key protecting the write endpoint (set as a Space secret).
# If unset, /ingest is open (fine for local dev).
INGEST_API_KEY = os.getenv("INGEST_API_KEY", "")


def require_ingest_key(provided: Optional[str]) -> None:
    if INGEST_API_KEY and provided != INGEST_API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing ingest key")


# In-memory ingest job tracking (single-process; resets on restart).
_jobs: dict[str, dict] = {}

# Lazy singleton: build clients once, reuse across requests.
_rag: Optional[MenuRAG] = None


def get_rag() -> MenuRAG:
    global _rag
    if _rag is None:
        logger.info("Initializing MenuRAG ...")
        _rag = MenuRAG()
    return _rag


class Turn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    restaurant: Optional[str] = None
    history: Optional[list[Turn]] = None


@app.get("/")
def root() -> dict:
    """Root route so platform health probes (e.g. HF Spaces) see a 200."""
    return {"service": "menumind-api", "status": "ok", "docs": "/docs"}


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

    history = [t.model_dump() for t in req.history] if req.history else None

    def event_stream():
        try:
            for ev in rag.ask_stream(
                req.question, restaurant=req.restaurant, history=history
            ):
                yield _sse(ev["type"], ev["data"])
        except Exception as exc:
            logger.exception("chat stream failed")
            yield _sse("error", str(exc))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    restaurant: str = Form(...),
    x_ingest_key: Optional[str] = Header(default=None),
) -> dict:
    """Upload a menu (PDF/image); parse + embed + ingest it in the background."""
    require_ingest_key(x_ingest_key)
    if not restaurant or not restaurant.strip():
        raise HTTPException(status_code=400, detail="restaurant is required")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")

    job_id = uuid.uuid4().hex
    name = restaurant.strip()
    _jobs[job_id] = {"status": "processing", "restaurant": name}
    filename = file.filename or "menu.pdf"

    def run() -> None:
        try:
            result = ingest_menu_file(data, filename, name)
            _jobs[job_id] = {"status": "done", **result}
        except Exception as exc:  # noqa: BLE001 - surface message to client
            logger.exception("ingest job failed")
            _jobs[job_id] = {"status": "error", "restaurant": name, "error": str(exc)}

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id, "status": "processing", "restaurant": name}


@app.get("/ingest/{job_id}")
def ingest_status(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job id")
    return job
