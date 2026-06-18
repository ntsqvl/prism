from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
import uuid


class VendorCreateRequest(BaseModel):
    vendor_name: str


class VendorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    vendor_id: uuid.UUID
    vendor_name: str
    cycle_id: uuid.UUID
    completeness_score: Optional[float] = 0.0
    submission_status: Optional[str] = "pending"


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: uuid.UUID
    vendor_id: uuid.UUID
    file_path: str
    extraction_status: str
    page_count: Optional[int] = None
    document_type_code: Optional[str] = None


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: uuid.UUID
    file_path: str
    document_type_code: Optional[str]
    extraction_status: str
    page_count: Optional[int]
    chunk_count: int


class CompletenessItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_type_code: str
    document_name: str
    is_present: bool
    is_mandatory: bool
    consequence_if_missing: str
    source: str


class CompletenessCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    vendor_id: uuid.UUID
    vendor_name: str
    completeness_score: float
    submission_status: str
    required_documents: List[CompletenessItemResponse] = Field(default_factory=list)
