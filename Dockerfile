# MenuMind backend — Hugging Face Spaces (Docker SDK). Listens on 7860.
FROM python:3.11-slim

# HF Spaces run containers as a non-root user (uid 1000).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH="/home/user/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache

WORKDIR /app

# Install Python deps first for better layer caching.
COPY --chown=user api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir --user -r api/requirements.txt

# Copy what the API needs at runtime (incl. menu parsing for /ingest).
COPY --chown=user api/ ./api/
COPY --chown=user menu_parser/ ./menu_parser/
COPY --chown=user rag.py embedder.py ingestor.py chunker.py config.py utils.py ingest_service.py ./

EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
