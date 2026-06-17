from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from database import Base


class EmbeddingJobModel(Base):
    __tablename__ = "embedding_job"
    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunk.chunk_id"), nullable=False)
    status = Column(String, nullable=False, default="pending")
    attempts = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AuditLogModel(Base):
    __tablename__ = "audit_log"
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_id = Column(UUID(as_uuid=True), nullable=True)
    vendor_id = Column(UUID(as_uuid=True), nullable=True)
    event_type = Column(String, nullable=False)
    agent_type = Column(String, nullable=True)
    detail = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentFindingModel(Base):
    __tablename__ = "agent_finding"
    finding_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_id = Column(UUID(as_uuid=True), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), nullable=True)
    agent_type = Column(String, nullable=True)
    dimension = Column(String(100), nullable=False)
    regulation_code = Column(String(100), nullable=True)
    score = Column(Numeric, nullable=True)
    severity = Column(String(20), nullable=True)
    finding_summary = Column(Text, nullable=False)
    evidence_quote = Column(Text, nullable=True)
    evidence_page = Column(Integer, nullable=True)
    evidence_chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunk.chunk_id"), nullable=True)
    is_dealbreaker = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
