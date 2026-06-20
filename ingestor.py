import logging
import time
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    UpdateStatus,
    VectorParams,
)

from config import get_settings
from embedder import EmbeddedChunk

logger = logging.getLogger(__name__)


class QdrantIngestor:
    """Manage Qdrant Cloud collections and ingest embedded chunks."""

    def __init__(self, collection_name: str | None = None):
        settings = get_settings()
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.batch_size = settings.qdrant_batch_size

        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=300,
        )
        logger.info("Connected to Qdrant at %s", settings.qdrant_url)

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def ensure_collection(self, vector_size: int, recreate: bool = False) -> None:
        """Create the collection if it doesn't exist, optionally recreating it."""
        exists = self._collection_exists()

        if exists and recreate:
            logger.info("Deleting existing collection '%s'", self.collection_name)
            self.client.delete_collection(self.collection_name)
            exists = False

        if not exists:
            logger.info(
                "Creating collection '%s' (size=%d, cosine)",
                self.collection_name,
                vector_size,
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            info = self.client.get_collection(self.collection_name)
            logger.info(
                "Collection '%s' exists: %d points, %d-dim",
                self.collection_name,
                info.points_count,
                info.config.params.vectors.size,
            )

        self.ensure_payload_indexes()

    def ensure_payload_indexes(self) -> None:
        """Create payload indexes needed for filtered retrieval (idempotent)."""
        indexes = {
            "restaurant": PayloadSchemaType.KEYWORD,
            "page_number": PayloadSchemaType.INTEGER,
        }
        for field, schema in indexes.items():
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=schema,
                )
                logger.info("Created payload index on '%s'", field)
            except Exception as exc:  # already exists -> Qdrant returns an error
                logger.debug("Payload index on '%s' not created (%s)", field, exc)

    def collection_info(self) -> dict:
        """Return basic collection stats."""
        info = self.client.get_collection(self.collection_name)
        return {
            "name": self.collection_name,
            "points": info.points_count,
            "vector_size": info.config.params.vectors.size,
            "status": str(info.status),
        }

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, embedded_chunks: list[EmbeddedChunk]) -> dict:
        """Upsert embedded chunks into the collection in batches."""
        if not embedded_chunks:
            logger.warning("Nothing to ingest — empty list.")
            return {"ingested": 0}

        vector_size = len(embedded_chunks[0].embedding)
        self.ensure_collection(vector_size)

        points = self._build_points(embedded_chunks)

        logger.info("Ingesting %d points into '%s' ...", len(points), self.collection_name)
        start = time.time()
        ok, fail = 0, 0

        for i in range(0, len(points), self.batch_size):
            batch = points[i : i + self.batch_size]
            try:
                result = self.client.upsert(
                    collection_name=self.collection_name,
                    wait=True,
                    points=batch,
                )
                if result and result.status == UpdateStatus.COMPLETED:
                    ok += len(batch)
                else:
                    fail += len(batch)
            except Exception:
                logger.exception("Batch %d failed", i // self.batch_size + 1)
                fail += len(batch)

        elapsed = time.time() - start
        logger.info(
            "Ingestion done: %d ok, %d failed, %.1fs (%.1f pts/s)",
            ok, fail, elapsed, ok / elapsed if elapsed > 0 else 0,
        )
        return {"ingested": ok, "failed": fail, "elapsed_s": round(elapsed, 1)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.collection_name)
            return True
        except Exception:
            return False

    @staticmethod
    def _build_points(embedded_chunks: list[EmbeddedChunk]) -> list[PointStruct]:
        points = []
        for ec in embedded_chunks:
            c = ec.chunk
            payload = {
                "text": c.text,
                "text_length": c.char_count,
                "page_number": c.page_number,
                "chunk_id": c.chunk_id,
                "chunk_type": c.chunk_type,
                "restaurant": c.restaurant,
                "original_id": f"page_{c.page_number}_chunk_{c.chunk_id}",
            }
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=ec.embedding,
                    payload=payload,
                )
            )
        return points
