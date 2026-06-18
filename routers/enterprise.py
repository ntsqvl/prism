# =============================================================
# enterprise.py
# FastAPI router for Stage 0 — Enterprise Registration.
#
# Endpoints:
#   GET  /enterprise/options          → returns all dropdown options
#   POST /enterprise/register         → registers a new enterprise
#   GET  /enterprise/{enterprise_id}  → retrieves a registered enterprise
#
# Two types of fields:
#   DROPDOWN  → predefined options returned by /options endpoint
#   FREE TEXT → user types freely (company name, custom industry)
# =============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
from typing import List, Optional

from database import get_db
from schemas.enterprise import (
    EnterpriseRegisterRequest,
    EnterpriseRegisterResponse,
    EnterpriseOptionsResponse,
    EnterpriseGetResponse,
)
from services.enterprise_service import (
    get_options,
    check_duplicate_enterprise,
    create_enterprise,
    get_enterprise as service_get_enterprise,
    search_enterprises_by_name,
    resolve_country_label,
    resolve_industry_label,
)


router = APIRouter(prefix="/enterprise", tags=["Enterprise Registration — Stage 0"])


@router.get(
    "/options",
    response_model=EnterpriseOptionsResponse,
    summary="Get dropdown options for enterprise registration form",
)
def get_enterprise_options():
    return get_options()


@router.get("", response_model=List[EnterpriseGetResponse], summary="Search enterprises by name")
def search_enterprises(name: Optional[str] = None, db: Session = Depends(get_db)):
    """Search for enterprises by partial name match using query param `name`.

    Example: GET /enterprise?name=tech
    """
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide 'name' query parameter to search.")
    results = search_enterprises_by_name(db, name)
    return [
        EnterpriseGetResponse(
            enterprise_id=str(e.enterprise_id),
            name=e.name,
            country_code=e.country_code,
            industry_code=e.industry_code,
            country_label=resolve_country_label(e.country_code),
            industry_label=resolve_industry_label(e.industry_code),
            created_at=e.created_at,
        )
        for e in results
    ]


@router.post(
    "/register",
    response_model=EnterpriseRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new enterprise",
)
def register_enterprise(payload: EnterpriseRegisterRequest, db: Session = Depends(get_db)):
    if check_duplicate_enterprise(db, payload.name, payload.country_code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An enterprise named '{payload.name}' in '{payload.country_code}' is already registered."
            ),
        )

    try:
        new = create_enterprise(db, payload.name, payload.country_code, payload.industry_code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save enterprise to database. Error: {str(e)}",
        )

    return EnterpriseRegisterResponse(
        enterprise_id=str(new.enterprise_id),
        name=new.name,
        country_code=new.country_code,
        industry_code=new.industry_code,
        country_label=resolve_country_label(new.country_code),
        industry_label=resolve_industry_label(new.industry_code),
        created_at=new.created_at,
        message=(
            f"Enterprise '{new.name}' registered successfully. Applicable regulations for "
            f"{resolve_country_label(new.country_code)} — {resolve_industry_label(new.industry_code)} "
            f"will be detected automatically."
        ),
    )


@router.get("/{enterprise_id}", response_model=EnterpriseGetResponse, summary="Get enterprise by ID")
def get_enterprise(enterprise_id: str, db: Session = Depends(get_db)):
    try:
        parsed = uuid.UUID(enterprise_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{enterprise_id}' is not a valid UUID.")

    ent = service_get_enterprise(db, parsed)
    if not ent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Enterprise with ID '{enterprise_id}' not found.")

    return EnterpriseGetResponse(
        enterprise_id=str(ent.enterprise_id),
        name=ent.name,
        country_code=ent.country_code,
        industry_code=ent.industry_code,
        country_label=resolve_country_label(ent.country_code),
        industry_label=resolve_industry_label(ent.industry_code),
        created_at=ent.created_at,
    )
