"""
context_service.py
──────────────────
Orchestrates Step 4 (Context Discovery) and Step 3 (Checklist Assembly):

  run_context_discovery()      — samples chunks, calls agent, writes cycle_context
  confirm_context()            — user confirmation endpoint logic
  build_document_checklist()   — assembles required doc list from all sources
  calculate_completeness()     — scores each vendor and flags disqualified ones
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.vendor import VendorModel, VendorDocumentModel, DocumentChunkModel, DocumentTypeModel
from models.procurement import CycleContextModel, ProcurementCycleModel
from models.regulation import RegulationDocumentRequirementModel, RegulationFrameworkModel
from models.policy import PolicyDocumentRequirementModel
from models.enterprise import EnterpriseRegulationModel
from models.agent import AuditLogModel, AgentFindingModel
from agents.context_discovery import run_context_discovery_agent
from core.config import settings

logger = logging.getLogger(__name__)


_DOCUMENT_TYPE_CACHE: set[str] | None = None


# ── Audit helper ──────────────────────────────────────────────────────────────

def _write_audit(db: Session, event_type: str, cycle_id=None, vendor_id=None,
                 detail: dict | None = None, agent_type: str | None = None):
    log = AuditLogModel(
        cycle_id=cycle_id, vendor_id=vendor_id,
        event_type=event_type, agent_type=agent_type, detail=detail,
    )
    db.add(log)


def _get_document_type_codes(db: Session) -> set[str]:
    global _DOCUMENT_TYPE_CACHE
    if _DOCUMENT_TYPE_CACHE is None:
        _DOCUMENT_TYPE_CACHE = {
            code for (code,) in db.query(DocumentTypeModel.document_type_code).all()
        }
    return _DOCUMENT_TYPE_CACHE


# ── Step 4: Context Discovery ─────────────────────────────────────────────────

def run_context_discovery(cycle_id: uuid.UUID, db: Session) -> CycleContextModel:
    """
    Sample chunks from all vendor documents in the cycle,
    call the Context Discovery Agent, and persist results.

    - Updates vendor_document.document_type_code for each classified file.
    - Sets requires_confirmation=True when confidence < threshold.
    - Writes 'context_discovered' audit event.
    """
    cycle: ProcurementCycleModel = db.get(ProcurementCycleModel, cycle_id)
    if not cycle:
        raise ValueError(f"Cycle {cycle_id} not found")

    # ── Sample chunks across all vendors ─────────────────────────────────────
    # We spread the sample evenly: take the first N chunks from each document
    # so the agent sees a cross-section of all submitted material.
    all_chunks = (
        db.query(DocumentChunkModel)
        .join(VendorDocumentModel)
        .join(VendorModel)
        .filter(VendorModel.cycle_id == cycle_id)
        .filter(VendorDocumentModel.extraction_status == "extracted")
        .order_by(VendorModel.vendor_id, DocumentChunkModel.chunk_index)
        .limit(settings.CONTEXT_SAMPLE_CHUNKS)
        .all()
    )

    if not all_chunks:
        raise ValueError(f"No extracted chunks found for cycle {cycle_id}. Run ingestion first.")

    sample_payload = [
        {
            "content": c.content,
            "page_start": c.page_start,
            "section_heading": c.section_heading,
            "file_path": c.document.file_path,
        }
        for c in all_chunks
    ]

    # ── Call the agent ────────────────────────────────────────────────────────
    _write_audit(db, "agent_started", cycle_id=cycle_id,
                 agent_type="context_discovery",
                 detail={"chunks_sampled": len(sample_payload)})
    db.commit()

    result = run_context_discovery_agent(sample_payload)

    # ── Persist cycle_context ─────────────────────────────────────────────────
    confidence = float(result["confidence_score"])
    requires_confirmation = confidence < settings.CONTEXT_CONFIDENCE_THRESHOLD

    # Delete stale context if re-running
    existing = db.query(CycleContextModel).filter_by(cycle_id=cycle_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    context = CycleContextModel(
        cycle_id=cycle_id,
        software_type=result["software_type"],
        software_category_code=result["software_category_code"],
        data_sensitivity_code=result["data_sensitivity_code"],
        estimated_contract_value=result.get("estimated_contract_value"),
        discovery_summary=result["discovery_summary"],
        confidence_score=confidence,
        evidence_sources=result.get("evidence_sources", []),
        requires_confirmation=requires_confirmation,
        confirmed_by_user=False,
    )
    db.add(context)
    db.flush()

    # ── Update document_type_code on each vendor_document ────────────────────
    classifications = result.get("document_classifications", [])
    updated_count = 0
    valid_document_type_codes = _get_document_type_codes(db)
    for cls in classifications:
        doc = (
            db.query(VendorDocumentModel)
            .filter_by(file_path=cls["file_path"])
            .first()
        )
        document_type_code = cls.get("document_type_code")
        if doc and document_type_code and document_type_code != "UNKNOWN":
            if document_type_code in valid_document_type_codes:
                doc.document_type_code = document_type_code
                updated_count += 1
            else:
                logger.warning(
                    "Skipping unsupported document type code %s for %s; not present in document_type table",
                    document_type_code,
                    cls.get("file_path"),
                )
        # Persist an agent finding for this classification
        try:
            finding = AgentFindingModel(
                cycle_id=cycle_id,
                vendor_id=(doc.vendor_id if doc else None),
                agent_type="context_discovery",
                dimension="document_classification",
                finding_summary=cls.get("classification_reasoning")
                or f"Classified {cls.get('file_path')} as {cls.get('document_type_code')}",
                evidence_quote=cls.get("classification_reasoning"),
                score=confidence * 100,
            )
            db.add(finding)
        except Exception:
            # Don't fail the whole run if finding persistence fails; continue
            logger.exception("Failed to persist agent finding for %s", cls.get("file_path"))

    # ── Audit ─────────────────────────────────────────────────────────────────
    _write_audit(
        db, "context_discovered", cycle_id=cycle_id,
        agent_type="context_discovery",
        detail={
            "software_category_code": result["software_category_code"],
            "data_sensitivity_code": result["data_sensitivity_code"],
            "confidence_score": confidence,
            "requires_confirmation": requires_confirmation,
            "documents_classified": updated_count,
        },
    )

    db.commit()
    db.refresh(context)

    logger.info(
        "Context discovery done for cycle %s — category=%s, sensitivity=%s, "
        "confidence=%.2f, needs_confirm=%s",
        cycle_id,
        result["software_category_code"],
        result["data_sensitivity_code"],
        confidence,
        requires_confirmation,
    )
    return context


def confirm_context(
    cycle_id: uuid.UUID,
    db: Session,
    software_category_code: str | None = None,
    data_sensitivity_code: str | None = None,
    estimated_contract_value: float | None = None,
) -> CycleContextModel:
    """
    Mark context as confirmed by user.
    Optionally override any agent-discovered fields.
    """
    context = db.query(CycleContextModel).filter_by(cycle_id=cycle_id).first()
    if not context:
        raise ValueError(f"No context found for cycle {cycle_id}")

    if software_category_code:
        context.software_category_code = software_category_code
    if data_sensitivity_code:
        context.data_sensitivity_code = data_sensitivity_code
    if estimated_contract_value is not None:
        context.estimated_contract_value = estimated_contract_value

    context.confirmed_by_user = True
    context.confirmed_at = datetime.now(timezone.utc)
    context.requires_confirmation = False

    _write_audit(db, "user_confirmed", cycle_id=cycle_id,
                 detail={
                     "overrides": {
                         "software_category_code": software_category_code,
                         "data_sensitivity_code": data_sensitivity_code,
                         "estimated_contract_value": estimated_contract_value,
                     }
                 })

    db.commit()
    db.refresh(context)
    return context


# ── Step 3: Checklist Assembly & Completeness ─────────────────────────────────

def build_document_checklist(cycle_id: uuid.UUID, db: Session) -> list[dict]:
    """
    Build the full required document list for this cycle from three sources:
      1. Baseline documents (document_type.is_baseline = True) — always required
      2. Regulation-required docs (regulation_document_requirement)
         for regulations applicable to this enterprise + context
      3. Policy-required docs (policy_document_requirement)
         filtered by contract_value_threshold

    Returns list of dicts:
      {document_type_code, document_name, is_mandatory,
       consequence_if_missing, source}
    """
    cycle = db.get(ProcurementCycleModel, cycle_id)
    if not cycle:
        raise ValueError(f"Cycle {cycle_id} not found")

    context = db.query(CycleContextModel).filter_by(cycle_id=cycle_id).first()
    contract_value = float(context.estimated_contract_value) if (
        context and context.estimated_contract_value
    ) else 0

    checklist: dict[str, dict] = {}  # keyed by document_type_code

    # ── 1. Baseline documents ─────────────────────────────────────────────────
    baselines = db.query(DocumentTypeModel).filter_by(is_baseline=True).all()
    for dt in baselines:
        checklist[dt.document_type_code] = {
            "document_type_code": dt.document_type_code,
            "document_name": dt.name,
            "is_mandatory": True,
            "consequence_if_missing": "flag",
            "source": "baseline",
        }

    # ── 2. Regulation-required documents ─────────────────────────────────────
    # Get applicable regulation codes for this enterprise × context
    applicable_reg_codes = (
        db.query(EnterpriseRegulationModel.regulation_code)
        .filter_by(enterprise_id=cycle.enterprise_id)
        .all()
    )
    reg_codes = [r[0] for r in applicable_reg_codes]

    if reg_codes and context:
        # Further filter by software_category and data_sensitivity if set on the regulation
        reg_doc_reqs = (
            db.query(RegulationDocumentRequirementModel)
            .filter(RegulationDocumentRequirementModel.regulation_code.in_(reg_codes))
            .all()
        )
        for req in reg_doc_reqs:
            code = req.document_type_code
            # Regulation requirements override baseline with stricter consequence
            if code not in checklist or req.consequence_if_missing == "disqualify":
                checklist[code] = {
                    "document_type_code": code,
                    "document_name": req.document_type.name if req.document_type else code,
                    "is_mandatory": req.is_mandatory,
                    "consequence_if_missing": req.consequence_if_missing,
                    "source": f"regulation:{req.regulation_code}",
                }

    # ── 3. Policy-required documents ─────────────────────────────────────────
    if cycle.policy_id:
        policy_doc_reqs = (
            db.query(PolicyDocumentRequirementModel)
            .filter_by(policy_id=cycle.policy_id)
            .all()
        )
        for req in policy_doc_reqs:
            # Skip if contract value doesn't meet threshold
            if req.contract_value_threshold and contract_value < float(req.contract_value_threshold):
                continue
            code = req.document_type_code or req.custom_document_name
            if not code:
                continue
            if code not in checklist or req.consequence_if_missing == "disqualify":
                checklist[code] = {
                    "document_type_code": code,
                    "document_name": req.custom_document_name or code,
                    "is_mandatory": req.is_mandatory,
                    "consequence_if_missing": req.consequence_if_missing,
                    "source": "policy",
                }

    return list(checklist.values())


def calculate_completeness(cycle_id: uuid.UUID, db: Session) -> list[VendorModel]:
    """
    For each vendor in the cycle:
      - Compare submitted documents against the required checklist
      - Calculate completeness_score as a percentage
      - Set submission_status to 'disqualified' if a dealbreaker doc is missing,
        'complete' if all required docs present, 'incomplete' otherwise

    Returns updated list of VendorModel objects.
    """
    checklist = build_document_checklist(cycle_id, db)
    required_codes = {item["document_type_code"] for item in checklist}
    disqualify_codes = {
        item["document_type_code"]
        for item in checklist
        if item["consequence_if_missing"] == "disqualify"
    }

    vendors = db.query(VendorModel).filter_by(cycle_id=cycle_id).all()

    for vendor in vendors:
        submitted_codes = {
            doc.document_type_code
            for doc in vendor.documents
            if doc.document_type_code and doc.extraction_status == "extracted"
        }

        missing_codes = required_codes - submitted_codes
        missing_disqualifiers = disqualify_codes & missing_codes

        # Score = percentage of required docs present
        if required_codes:
            score = round(len(required_codes - missing_codes) / len(required_codes) * 100, 1)
        else:
            score = 100.0

        vendor.completeness_score = score

        if missing_disqualifiers:
            vendor.submission_status = "disqualified"
            logger.warning(
                "Vendor %s (%s) DISQUALIFIED — missing: %s",
                vendor.vendor_id, vendor.vendor_name, missing_disqualifiers,
            )
        elif missing_codes:
            vendor.submission_status = "incomplete"
        else:
            vendor.submission_status = "complete"

    db.commit()
    return vendors
