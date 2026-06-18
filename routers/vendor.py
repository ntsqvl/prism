"""
vendor.py router
────────────────
POST /cycle/{cycle_id}/vendor/add       — add a vendor to a cycle
POST /vendor/{vendor_id}/upload         — upload a PDF document for a vendor
GET  /cycle/{cycle_id}/vendors          — list vendors with completeness scores
GET  /vendor/{vendor_id}/documents      — list documents for a vendor
POST /cycle/{cycle_id}/ingest           — trigger extraction for all pending docs
"""

import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from models.vendor import VendorModel, VendorDocumentModel
from models.procurement import ProcurementCycleModel
from schemas.vendor import (
    VendorCreateRequest,
    VendorResponse,
    DocumentUploadResponse,
    DocumentStatusResponse,
    CompletenessCheckResponse,
    CompletenessItemResponse,
)
from services.ingestion_service import extract_and_chunk_document, process_all_vendor_documents
from services.context_service import build_document_checklist
from core.config import settings

router = APIRouter(prefix="", tags=["vendors"])


@router.post("/cycle/{cycle_id}/vendor/add", response_model=VendorResponse)
def add_vendor(cycle_id: uuid.UUID, body: VendorCreateRequest, db: Session = Depends(get_db)):
    cycle = db.get(ProcurementCycleModel, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    vendor = VendorModel(cycle_id=cycle_id, vendor_name=body.vendor_name)
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.post("/vendor/{vendor_id}/upload", response_model=DocumentUploadResponse)
async def upload_document(
    vendor_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    vendor = db.get(VendorModel, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save file to disk under uploads/cycle_id/vendor_id/
    upload_dir = Path(settings.UPLOAD_DIR) / str(vendor.cycle_id) / str(vendor_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = VendorDocumentModel(
        vendor_id=vendor_id,
        file_path=str(file_path),
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/cycle/{cycle_id}/ingest")
def trigger_ingestion(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Trigger extraction + chunking for all pending documents in this cycle.
    Returns a summary of how many succeeded / failed.
    """
    cycle = db.get(ProcurementCycleModel, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    results = process_all_vendor_documents(cycle_id, db)
    return {"cycle_id": str(cycle_id), "ingestion_results": results}


@router.get("/cycle/{cycle_id}/vendors", response_model=list[VendorResponse])
def list_vendors(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    cycle = db.get(ProcurementCycleModel, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return db.query(VendorModel).filter_by(cycle_id=cycle_id).all()


@router.get("/vendor/{vendor_id}/documents", response_model=list[DocumentStatusResponse])
def list_documents(vendor_id: uuid.UUID, db: Session = Depends(get_db)):
    vendor = db.get(VendorModel, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    docs = db.query(VendorDocumentModel).filter_by(vendor_id=vendor_id).all()
    result = []
    for doc in docs:
        result.append(DocumentStatusResponse(
            document_id=doc.document_id,
            file_path=doc.file_path,
            document_type_code=doc.document_type_code,
            extraction_status=doc.extraction_status,
            page_count=doc.page_count,
            chunk_count=len(doc.chunks),
        ))
    return result


@router.get("/vendor/{vendor_id}/completeness", response_model=CompletenessCheckResponse)
def check_completeness(vendor_id: uuid.UUID, db: Session = Depends(get_db)):
    vendor = db.get(VendorModel, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    checklist = build_document_checklist(vendor.cycle_id, db)
    submitted_codes = {
        doc.document_type_code
        for doc in vendor.documents
        if doc.document_type_code and doc.extraction_status == "extracted"
    }

    items = []
    for item in checklist:
        items.append(CompletenessItemResponse(
            document_type_code=item["document_type_code"],
            document_name=item["document_name"],
            is_present=item["document_type_code"] in submitted_codes,
            is_mandatory=item["is_mandatory"],
            consequence_if_missing=item["consequence_if_missing"],
            source=item["source"],
        ))

    score = float(vendor.completeness_score) if vendor.completeness_score else 0.0
    return CompletenessCheckResponse(
        vendor_id=vendor.vendor_id,
        vendor_name=vendor.vendor_name,
        completeness_score=score,
        submission_status=vendor.submission_status,
        required_documents=items,
    )
