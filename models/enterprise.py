from sqlalchemy import Column, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database import Base
import uuid

class EnterpriseModel(Base):
    __tablename__ = "enterprise"

    enterprise_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name          = Column(String(255), nullable=False)
    country_code  = Column(String(2),   nullable=False)
    industry_code = Column(String(50),  nullable=False)
    created_at    = Column(TIMESTAMP,   server_default=func.now())


class EnterpriseRegulationModel(Base):
    __tablename__ = "enterprise_regulation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(UUID(as_uuid=True), nullable=False)
    regulation_code = Column(String, nullable=False)