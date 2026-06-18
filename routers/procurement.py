"""
procurement.py router
─────────────────────
POST /cycle/create                          — create a new procurement cycle
GET  /cycle/{cycle_id}                      — get cycle details
POST /cycle/{cycle_id}/context/discover     — trigger context discovery agent
GET  /cycle/{cycle_id}/context              — get discovered context
POST /cycle/{cycle_id}/context/confirm      — user confirms or overrides context
POST /cycle/{cycle_id}/embed               — trigger embedding for all chunks
GET  /cycle/{cycle_id}/ingestion-status    — check extraction + embedding progress
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.procurement import ProcurementCycleModel, CycleContextModel
from models.vendor import VendorModel, VendorDocumentModel, DocumentChunkModel
from models.enterprise import EnterpriseModel
from models.agent import EmbeddingJobModel
from schemas.procurement import (
    CycleCreateRequest,
    CycleResponse,
    CycleContextResponse,
    ContextConfirmRequest,
)
from schemas.agent import IngestionStatusResponse
from services.context_service import (
    run_context_discovery,
    confirm_context,
    calculate_completeness,
)
from services.embedding_service import run_embeddings_for_cycle

router = APIRouter(prefix="", tags=["procurement"])


def _format_evidence_sources(evidence_sources) -> list[str]:
    formatted: list[str] = []
    for item in evidence_sources or []:
        if isinstance(item, str):
            formatted.append(item)
            continue

        if isinstance(item, dict):
            parts = []
            source_file = item.get("source_file") or item.get("file_path")
            page = item.get("page")
            quote = item.get("quote")

            if source_file:
                parts.append(str(source_file))
            if page is not None:
                parts.append(f"p.{page}")
            if quote:
                parts.append(str(quote))

            formatted.append(" — ".join(parts) if parts else str(item))
            continue

        formatted.append(str(item))

    return formatted


def _context_response_payload(context: CycleContextModel) -> dict:
    return {
        "cycle_id": context.cycle_id,
        "software_type": context.software_type,
        "software_category_code": context.software_category_code,
        "data_sensitivity_code": context.data_sensitivity_code,
        "estimated_contract_value": float(context.estimated_contract_value)
        if context.estimated_contract_value is not None
        else None,
        "discovery_summary": context.discovery_summary,
        "confidence_score": float(context.confidence_score)
        if context.confidence_score is not None
        else None,
        "evidence_sources": _format_evidence_sources(context.evidence_sources),
        "requires_confirmation": bool(context.requires_confirmation),
        "confirmed_by_user": bool(context.confirmed_by_user),
        "confirmed_at": context.confirmed_at,
    }


@router.post("/cycle/create", response_model=CycleResponse)
def create_cycle(body: CycleCreateRequest, db: Session = Depends(get_db)):
    # Validate enterprise exists to avoid a DB-level foreign key error
    enterprise = db.get(EnterpriseModel, body.enterprise_id)
    if not enterprise:
        raise HTTPException(status_code=400, detail="Enterprise not found")

    cycle = ProcurementCycleModel(
        enterprise_id=body.enterprise_id,
        policy_id=body.policy_id,
        title=body.title,
        status="active",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.get("/cycle/{cycle_id}", response_model=CycleResponse)
def get_cycle(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    cycle = db.get(ProcurementCycleModel, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return cycle


@router.post("/cycle/{cycle_id}/context/discover", response_model=CycleContextResponse)
def discover_context(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Trigger the Context Discovery Agent (Step 4).
    Must be called after all documents have been ingested (Step 1–3).
    """
    try:
        context = run_context_discovery(cycle_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}")
    return _context_response_payload(context)


@router.get("/cycle/{cycle_id}/context", response_model=CycleContextResponse)
def get_context(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    context = db.query(CycleContextModel).filter_by(cycle_id=cycle_id).first()
    if not context:
        raise HTTPException(
            status_code=404,
            detail="Context not yet discovered. Call POST /cycle/{cycle_id}/context/discover first."
        )
    return _context_response_payload(context)


@router.post("/cycle/{cycle_id}/context/confirm", response_model=CycleContextResponse)
def confirm_context_endpoint(
    cycle_id: uuid.UUID,
    body: ContextConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    User confirms the discovered context (or overrides low-confidence fields).
    Required when confidence_score < 0.80 before proceeding to checklist + analysis.
    """
    try:
        context = confirm_context(
            cycle_id=cycle_id,
            db=db,
            software_category_code=body.software_category_code,
            data_sensitivity_code=body.data_sensitivity_code,
            estimated_contract_value=body.estimated_contract_value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _context_response_payload(context)


@router.post("/cycle/{cycle_id}/completeness")
def run_completeness(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Calculate completeness scores for all vendors in the cycle.
    Triggers document checklist assembly (Step 3) and vendor scoring.
    """
    try:
        vendors = calculate_completeness(cycle_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return [
        {
            "vendor_id": str(v.vendor_id),
            "vendor_name": v.vendor_name,
            "completeness_score": float(v.completeness_score) if v.completeness_score else 0,
            "submission_status": v.submission_status,
        }
        for v in vendors
    ]


@router.post("/cycle/{cycle_id}/embed")
def trigger_embeddings(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Generate embeddings for all document chunks in this cycle (Step 6).
    Run AFTER context discovery and document classification are complete.
    """
    cycle = db.get(ProcurementCycleModel, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    results = run_embeddings_for_cycle(cycle_id, db)
    return {"cycle_id": str(cycle_id), "embedding_results": results}


@router.get("/cycle/{cycle_id}/ingestion-status", response_model=IngestionStatusResponse)
def ingestion_status(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Returns a full status snapshot of extraction and embedding progress.
    """
    cycle = db.get(ProcurementCycleModel, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    vendors = db.query(VendorModel).filter_by(cycle_id=cycle_id).all()
    vendor_ids = [v.vendor_id for v in vendors]
    docs = db.query(VendorDocumentModel).filter(
        VendorDocumentModel.vendor_id.in_(vendor_ids)
    ).all()

    doc_ids = [d.document_id for d in docs]
    chunks = db.query(DocumentChunkModel).filter(
        DocumentChunkModel.document_id.in_(doc_ids)
    ).all()
    chunk_ids = [c.chunk_id for c in chunks]

    pending_jobs = db.query(EmbeddingJobModel).filter(
        EmbeddingJobModel.chunk_id.in_(chunk_ids),
        EmbeddingJobModel.status == "pending",
    ).count()

    embedded = sum(1 for c in chunks if c.embedding is not None)

    return IngestionStatusResponse(
        cycle_id=cycle_id,
        total_documents=len(docs),
        extracted=sum(1 for d in docs if d.extraction_status == "extracted"),
        ocr_required=sum(1 for d in docs if d.extraction_status == "ocr_required"),
        failed=sum(1 for d in docs if d.extraction_status == "failed"),
        pending=sum(1 for d in docs if d.extraction_status == "pending"),
        total_chunks=len(chunks),
        chunks_embedded=embedded,
        embedding_pending=pending_jobs,
    )
