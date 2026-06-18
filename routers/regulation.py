"""
regulation.py router
────────────────────
GET /regulations                 — list all known regulation frameworks
GET /regulations/{code}          — get a single regulation with its rules
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.regulation import RegulationFrameworkModel, RegulationRuleModel
from schemas.regulation import RegulationResponse, RegulationRuleResponse

router = APIRouter(prefix="", tags=["regulations"])


@router.get("/regulations", response_model=list[RegulationResponse])
def list_regulations(db: Session = Depends(get_db)):
    """Return all regulation frameworks in the system."""
    return db.query(RegulationFrameworkModel).order_by(
        RegulationFrameworkModel.regulation_code
    ).all()


@router.get("/regulations/{regulation_code}", response_model=RegulationResponse)
def get_regulation(regulation_code: str, db: Session = Depends(get_db)):
    reg = db.get(RegulationFrameworkModel, regulation_code)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Regulation '{regulation_code}' not found")
    return reg


@router.get(
    "/regulations/{regulation_code}/rules",
    response_model=list[RegulationRuleResponse],
)
def get_regulation_rules(regulation_code: str, db: Session = Depends(get_db)):
    """List all agent evaluation rules for a specific regulation."""
    reg = db.get(RegulationFrameworkModel, regulation_code)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Regulation '{regulation_code}' not found")

    return (
        db.query(RegulationRuleModel)
        .filter_by(regulation_code=regulation_code)
        .order_by(RegulationRuleModel.agent_type, RegulationRuleModel.severity)
        .all()
    )
