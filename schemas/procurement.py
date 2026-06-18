from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
import uuid
from datetime import datetime


class CycleCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enterprise_id": "00000000-0000-0000-0000-000000000000",
                "policy_id": None,
                "title": "RFP for Accounting Software"
            }
        }
    )
    enterprise_id: uuid.UUID
    policy_id: Optional[uuid.UUID] = None
    title: str = Field(..., min_length=3, max_length=255, description="Procurement cycle / RFP title")


class CycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cycle_id: uuid.UUID
    enterprise_id: uuid.UUID
    policy_id: Optional[uuid.UUID] = None
    title: str
    status: str


class CycleContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cycle_id: uuid.UUID
    software_type: Optional[str] = None
    software_category_code: Optional[str] = None
    data_sensitivity_code: Optional[str] = None
    estimated_contract_value: Optional[float] = None
    discovery_summary: Optional[str] = None
    confidence_score: Optional[float] = None
    evidence_sources: Optional[List[str]] = Field(default_factory=list)
    requires_confirmation: Optional[bool] = False
    confirmed_by_user: Optional[bool] = False
    confirmed_at: Optional[datetime] = None


class ContextConfirmRequest(BaseModel):
    software_category_code: Optional[str] = None
    data_sensitivity_code: Optional[str] = None
    estimated_contract_value: Optional[float] = None
