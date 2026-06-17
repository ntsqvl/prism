"""
agent.py router
───────────────
GET  /cycle/{cycle_id}/audit   — full audit trail
GET  /cycle/{cycle_id}/findings — agent findings (context_discovery type for now)
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import AuditLogModel, AgentFindingModel
from app.schemas.agent import AuditLogResponse, AgentFindingResponse

router = APIRouter(prefix="", tags=["agents"])


@router.get("/cycle/{cycle_id}/audit", response_model=list[AuditLogResponse])
def get_audit_log(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    logs = (
        db.query(AuditLogModel)
        .filter_by(cycle_id=cycle_id)
        .order_by(AuditLogModel.created_at)
        .all()
    )
    return logs


@router.get("/cycle/{cycle_id}/findings", response_model=list[AgentFindingResponse])
def get_findings(cycle_id: uuid.UUID, db: Session = Depends(get_db)):
    findings = (
        db.query(AgentFindingModel)
        .filter_by(cycle_id=cycle_id)
        .order_by(AgentFindingModel.created_at)
        .all()
    )
    return findings
