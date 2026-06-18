from sqlalchemy import Column, String, Integer, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base


class RegulationFrameworkModel(Base):
    __tablename__ = "regulation_framework"
    regulation_code = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class RegulationRuleModel(Base):
    __tablename__ = "regulation_rule"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regulation_code = Column(String, ForeignKey("regulation_framework.regulation_code"))
    rule_text = Column(String, nullable=True)


class RegulationDocumentRequirementModel(Base):
    __tablename__ = "regulation_document_requirement"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regulation_code = Column(String, ForeignKey("regulation_framework.regulation_code"))
    document_type_code = Column(String, ForeignKey("document_type.document_type_code"), nullable=False)
    is_mandatory = Column(Boolean, default=False)
    consequence_if_missing = Column(String, default="flag")

    document_type = relationship("DocumentTypeModel", backref="regulation_requirements")
