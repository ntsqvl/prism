"""
embedding_service.py
────────────────────
Step 6 — Generate and store vector embeddings for document chunks.

Called AFTER context discovery has classified all documents.
Uses AI/ML API with text-embedding-3-small (1536 dimensions,
matching the vector(1536) column in document_chunk).

Processes embedding_job rows in 'pending' state for a given cycle.
Supports retry up to MAX_EMBEDDING_RETRIES on transient failures.
"""

import uuid
import logging
import time
from datetime import datetime, timezone
import json

from openai import OpenAI
from sqlalchemy.orm import Session

from models.vendor import DocumentChunkModel, VendorDocumentModel, VendorModel
from models.agent import EmbeddingJobModel, AuditLogModel
from core.config import settings

logger = logging.getLogger(__name__)

def _get_aiml_client() -> OpenAI:
    """Lazily construct and return an OpenAI client for embeddings."""
    if not settings.AIML_API_KEY and not settings.OPENAI_API_KEY and not settings.FEATHERLESS_API_KEY:
        raise RuntimeError("No AIML/OpenAI API key configured for embeddings")

    api_key = settings.AIML_API_KEY or settings.OPENAI_API_KEY or settings.FEATHERLESS_API_KEY
    base_url = settings.AIML_BASE_URL
    return OpenAI(api_key=api_key, base_url=base_url)

EMBEDDING_BATCH_SIZE = 20   # chunks per API call — balance throughput vs payload size


def _write_audit(db, event_type, cycle_id=None, detail=None):
    log = AuditLogModel(cycle_id=cycle_id, event_type=event_type, detail=detail)
    db.add(log)


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Call AI/ML API embedding endpoint for a batch of texts.
    Returns list of 1536-dim float vectors.
    """
    client = _get_aiml_client()
    response = client.embeddings.create(
        model=settings.AIML_EMBEDDING_MODEL,
        input=texts,
    )
    # Response items are ordered the same as input
    return [item.embedding for item in response.data]


def run_embeddings_for_cycle(cycle_id: uuid.UUID, db: Session) -> dict:
    """
    Find all pending embedding_job rows for chunks belonging to this cycle.
    Embed in batches and update document_chunk.embedding + job status.

    Returns summary: {completed, failed, skipped}
    """
    # Collect all pending jobs for this cycle's chunks
    pending_jobs = (
        db.query(EmbeddingJobModel)
        .join(DocumentChunkModel, EmbeddingJobModel.chunk_id == DocumentChunkModel.chunk_id)
        .join(VendorDocumentModel, DocumentChunkModel.document_id == VendorDocumentModel.document_id)
        .join(VendorModel, VendorDocumentModel.vendor_id == VendorModel.vendor_id)
        .filter(VendorModel.cycle_id == cycle_id)
        .filter(EmbeddingJobModel.status == "pending")
        .filter(EmbeddingJobModel.attempts < settings.MAX_EMBEDDING_RETRIES)
        .all()
    )

    if not pending_jobs:
        logger.info("No pending embedding jobs for cycle %s", cycle_id)
        return {"completed": 0, "failed": 0, "skipped": 0}

    logger.info("Embedding %d chunks for cycle %s", len(pending_jobs), cycle_id)
    results = {"completed": 0, "failed": 0, "skipped": 0}

    # Process in batches
    for batch_start in range(0, len(pending_jobs), EMBEDDING_BATCH_SIZE):
        batch = pending_jobs[batch_start: batch_start + EMBEDDING_BATCH_SIZE]
        chunk_ids = [job.chunk_id for job in batch]

        # Fetch the actual chunk text
        chunks = (
            db.query(DocumentChunkModel)
            .filter(DocumentChunkModel.chunk_id.in_(chunk_ids))
            .all()
        )
        chunk_map = {c.chunk_id: c for c in chunks}
        job_map = {job.chunk_id: job for job in batch}

        texts = [chunk_map[cid].content for cid in chunk_ids if cid in chunk_map]
        valid_chunk_ids = [cid for cid in chunk_ids if cid in chunk_map]

        if not texts:
            results["skipped"] += len(batch)
            continue

        try:
            vectors = _embed_batch(texts)
        except Exception as exc:
            logger.error("Embedding batch failed: %s", exc)
            # Increment attempt count on all jobs in this batch
            for cid in valid_chunk_ids:
                job = job_map[cid]
                job.attempts += 1
                job.error_message = str(exc)
                if job.attempts >= settings.MAX_EMBEDDING_RETRIES:
                    job.status = "failed"
                    results["failed"] += 1
                else:
                    results["failed"] += 1
            db.commit()
            time.sleep(1)   # back off before next batch
            continue

        # Persist embeddings
        for cid, vector in zip(valid_chunk_ids, vectors):
            chunk = chunk_map[cid]
            job = job_map[cid]

            # Persist embedding as JSON text
            chunk.embedding = json.dumps(vector)
            chunk.embedding_model = settings.AIML_EMBEDDING_MODEL
            chunk.embedded_at = datetime.now(timezone.utc)

            job.status = "completed"
            job.attempts += 1
            job.completed_at = datetime.now(timezone.utc)
            results["completed"] += 1

        db.commit()
        logger.debug("Embedded batch %d–%d", batch_start, batch_start + len(batch))

    _write_audit(
        db, "embeddings_completed", cycle_id=cycle_id,
        detail=results,
    )
    db.commit()

    logger.info("Embedding complete for cycle %s: %s", cycle_id, results)
    return results
