from sqlalchemy import Column, String, Numeric
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base


class PolicyDocumentRequirementModel(Base):
    __tablename__ = "policy_document_requirement"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), nullable=False)
    document_type_code = Column(String, nullable=True)
    custom_document_name = Column(String, nullable=True)
    is_mandatory = Column(String, nullable=True)
    consequence_if_missing = Column(String, nullable=True)
    contract_value_threshold = Column(Numeric, nullable=True)
