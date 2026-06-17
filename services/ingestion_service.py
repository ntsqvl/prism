"""
ingestion_service.py
────────────────────
Steps 1–3 of the pipeline:
  1. Extract text from PDF (pdfplumber) or OCR (pytesseract) if scanned
  2. Chunk the extracted text into sections with page + heading metadata
  3. Store chunks in document_chunk table
  4. Queue embedding jobs in embedding_job table

Embedding (Step 6) is intentionally separate — triggered after
context discovery classifies documents (Step 4).
"""

import os
import re
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
from sqlalchemy.orm import Session

from models.vendor import VendorModel, VendorDocumentModel, DocumentChunkModel
from models.agent import EmbeddingJobModel, AuditLogModel
from core.config import settings

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_audit(
    db: Session,
    event_type: str,
    cycle_id=None,
    vendor_id=None,
    detail: dict | None = None,
    agent_type: str | None = None,
):
    log = AuditLogModel(
        cycle_id=cycle_id,
        vendor_id=vendor_id,
        event_type=event_type,
        agent_type=agent_type,
        detail=detail,
    )
    db.add(log)
    # Don't commit here — caller commits the full transaction


def _is_scanned_pdf(pdf_path: str) -> bool:
    """
    Return True when the PDF has no selectable text on any page.
    A page is considered image-only when it yields fewer than 20 chars.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if len(text.strip()) >= 20:
                    return False
        return True
    except Exception:
        return True


def _extract_with_pdfplumber(pdf_path: str) -> tuple[str, int]:
    """
    Returns (full_text, page_count).
    Each page is delimited by a sentinel so chunker can track pages.
    """
    pages_text: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
    full_text = "\n\n<<<PAGE_BREAK>>>\n\n".join(pages_text)
    return full_text, len(pages_text)


def _extract_with_ocr(pdf_path: str) -> tuple[str, int]:
    """
    Fallback OCR extraction using pytesseract + pdf2image.
    Returns (full_text, page_count).
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(pdf_path, dpi=300)
        pages_text: list[str] = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="eng")
            pages_text.append(text)
        full_text = "\n\n<<<PAGE_BREAK>>>\n\n".join(pages_text)
        return full_text, len(pages_text)
    except ImportError:
        logger.error("pytesseract / pdf2image not installed — cannot OCR %s", pdf_path)
        raise


def _detect_heading(line: str) -> bool:
    """
    Heuristic: a line is treated as a section heading if it is:
    - Short (≤ 80 chars), capitalised, and NOT a regular sentence.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False
    # All-caps or Title Case with no trailing punctuation that looks like prose
    is_title_case = stripped == stripped.title() and not stripped.endswith((",", ";"))
    is_all_caps = stripped == stripped.upper() and len(stripped) > 3
    starts_with_number = bool(re.match(r"^\d+[\.\)]\s+[A-Z]", stripped))
    return is_title_case or is_all_caps or starts_with_number


def _chunk_text(
    full_text: str,
    chunk_size: int = None,
    overlap: int = None,
) -> list[dict]:
    """
    Split text into overlapping chunks preserving page numbers and headings.

    Returns list of dicts:
      {chunk_index, page_start, page_end, section_heading, content}
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    # Split on page sentinel while tracking page numbers
    page_blocks = full_text.split("<<<PAGE_BREAK>>>")
    chunks: list[dict] = []
    current_heading: str | None = None
    buffer: list[str] = []
    buffer_pages: list[int] = []
    chunk_index = 0

    def flush_buffer():
        nonlocal chunk_index
        if not buffer:
            return
        content = " ".join(buffer).strip()
        # Bug 4 fix: always increment chunk_index on every flush attempt so
        # that if a near-empty chunk is skipped, the next real chunk still
        # gets a unique index. Without this, two chunks can share the same
        # chunk_index, violating any UNIQUE(document_id, chunk_index) DB constraint.
        current_index = chunk_index
        chunk_index += 1
        if len(content) < 30:          # skip near-empty chunks
            return
        chunks.append({
            "chunk_index": current_index,
            "page_start": buffer_pages[0] if buffer_pages else 1,
            "page_end": buffer_pages[-1] if buffer_pages else 1,
            "section_heading": current_heading,
            "content": content,
        })

    for page_num, page_text in enumerate(page_blocks, start=1):
        words = page_text.split()
        for i, word in enumerate(words):
            # Check if this word starts a new heading line
            line_context = " ".join(words[max(0, i - 5): i + 10])
            if _detect_heading(word) and i > 0:
                # When approaching chunk_size, flush first
                if len(" ".join(buffer)) >= chunk_size:
                    flush_buffer()
                    # Keep overlap words in new buffer
                    overlap_words = buffer[-overlap:] if len(buffer) > overlap else buffer[:]
                    buffer = overlap_words
                    buffer_pages = [page_num] * len(buffer)
                current_heading = word  # simplified — real heading is next few words

            buffer.append(word)
            buffer_pages.append(page_num)

            if len(" ".join(buffer)) >= chunk_size:
                flush_buffer()
                overlap_words = buffer[-overlap:] if len(buffer) > overlap else buffer[:]
                buffer = overlap_words
                buffer_pages = [page_num] * len(buffer)

    flush_buffer()  # final remainder
    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def extract_and_chunk_document(
    document_id: uuid.UUID,
    db: Session,
) -> VendorDocumentModel:
    """
    Full Steps 1–3 for a single vendor_document row:
      1. Detect if OCR needed
      2. Extract text
      3. Chunk and store in document_chunk
      4. Queue embedding jobs
      5. Write audit events

    Raises on unrecoverable failure (caller sets extraction_status='failed').
    """
    doc: VendorDocumentModel = db.get(VendorDocumentModel, document_id)
    if not doc:
        raise ValueError(f"VendorDocument {document_id} not found")

    # Bug 1 fix: explicitly fetch vendor instead of relying on the ORM
    # relationship (doc.vendor), which can return None if the relationship
    # is not declared or lazy-loading fails after a partial commit.
    vendor: VendorModel = db.get(VendorModel, doc.vendor_id)
    if not vendor:
        raise ValueError(f"Vendor {doc.vendor_id} not found for document {document_id}")
    cycle_id = vendor.cycle_id

    logger.info("Starting extraction for document %s (%s)", document_id, doc.file_path)

    # ── Step 1: Detect OCR need ───────────────────────────────────────────────
    needs_ocr = _is_scanned_pdf(doc.file_path)
    if needs_ocr:
        doc.extraction_status = "ocr_required"
        # Bug 2 fix: use flush() instead of commit() here so the status is
        # visible within the session without closing the transaction. A
        # mid-loop commit leaves the session in an invalid state if a later
        # document fails, causing PendingRollbackError for all subsequent docs.
        db.flush()
        logger.info("Document %s flagged as scanned — running OCR", document_id)

    # ── Step 2: Extract text ──────────────────────────────────────────────────
    try:
        if needs_ocr:
            full_text, page_count = _extract_with_ocr(doc.file_path)
        else:
            full_text, page_count = _extract_with_pdfplumber(doc.file_path)
    except Exception as exc:
        doc.extraction_status = "failed"
        db.flush()
        _write_audit(db, "extraction_failed", cycle_id=cycle_id, vendor_id=vendor.vendor_id,
                     detail={"document_id": str(document_id), "error": str(exc)})
        db.commit()  # commit the failure + audit entry so it's persisted even if caller swallows
        raise

    doc.extracted_text = full_text
    doc.page_count = page_count
    doc.extraction_status = "extracted"

    # ── Step 3: Chunk ─────────────────────────────────────────────────────────
    raw_chunks = _chunk_text(full_text)
    logger.info("Document %s → %d chunks", document_id, len(raw_chunks))

    for raw in raw_chunks:
        chunk = DocumentChunkModel(
            document_id=document_id,
            chunk_index=raw["chunk_index"],
            page_start=raw["page_start"],
            page_end=raw["page_end"],
            section_heading=raw["section_heading"],
            content=raw["content"],
        )
        db.add(chunk)
        db.flush()  # get chunk_id before creating embedding job

        # ── Queue embedding job ───────────────────────────────────────────────
        job = EmbeddingJobModel(chunk_id=chunk.chunk_id, status="pending")
        db.add(job)

    # ── Audit ─────────────────────────────────────────────────────────────────
    _write_audit(
        db,
        event_type="document_ingested",
        cycle_id=cycle_id,
        vendor_id=vendor.vendor_id,
        detail={
            "document_id": str(document_id),
            "file_path": doc.file_path,
            "page_count": page_count,
            "chunk_count": len(raw_chunks),
            "ocr_used": needs_ocr,
        },
    )

    db.commit()
    db.refresh(doc)
    logger.info("Extraction complete for document %s", document_id)
    return doc


def process_all_vendor_documents(cycle_id: uuid.UUID, db: Session) -> dict:
    """
    Run extract_and_chunk_document for every vendor document in the cycle
    that is still in 'pending' status.

    Returns summary dict with counts.
    """
    from models.vendor import VendorModel

    vendors = db.query(VendorModel).filter_by(cycle_id=cycle_id).all()
    results = {"extracted": 0, "failed": 0, "skipped": 0}

    for vendor in vendors:
        for doc in vendor.documents:
            if doc.extraction_status != "pending":
                results["skipped"] += 1
                continue
            try:
                extract_and_chunk_document(doc.document_id, db)
                results["extracted"] += 1
            except Exception as exc:
                logger.error("Failed to extract %s: %s", doc.document_id, exc)
                results["failed"] += 1

    return results
