from sqlalchemy import Column, String, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from database import Base


class ProcurementCycleModel(Base):
    __tablename__ = "procurement_cycle"
    cycle_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(UUID(as_uuid=True), nullable=False)
    policy_id = Column(UUID(as_uuid=True), nullable=True)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")


class CycleContextModel(Base):
    __tablename__ = "cycle_context"
    cycle_id = Column(UUID(as_uuid=True), primary_key=True)
    software_type = Column(String, nullable=True)
    software_category_code = Column(String, nullable=True)
    data_sensitivity_code = Column(String, nullable=True)
    estimated_contract_value = Column(Numeric, nullable=True)
    discovery_summary = Column(String, nullable=True)
    confidence_score = Column(Numeric, nullable=True)
    evidence_sources = Column(JSONB, nullable=True)
    requires_confirmation = Column(String, nullable=True)
    confirmed_by_user = Column(String, nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
