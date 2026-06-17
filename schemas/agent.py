from pydantic import BaseModel, ConfigDict
import uuid


class IngestionStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cycle_id: uuid.UUID
    total_documents: int
    extracted: int
    ocr_required: int
    failed: int
    pending: int
    total_chunks: int
    chunks_embedded: int
    embedding_pending: int


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    log_id: uuid.UUID
    cycle_id: uuid.UUID | None
    vendor_id: uuid.UUID | None
    event_type: str
    agent_type: str | None
    detail: dict | None
    created_at: str


class AgentFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    finding_id: uuid.UUID
    cycle_id: uuid.UUID
    vendor_id: uuid.UUID | None
    agent_type: str | None
    dimension: str
    regulation_code: str | None
    score: float | None
    severity: str | None
    finding_summary: str
    evidence_quote: str | None
    evidence_page: int | None
    evidence_chunk_id: uuid.UUID | None
    is_dealbreaker: bool
    created_at: str
