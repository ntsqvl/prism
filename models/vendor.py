from sqlalchemy import Column, String, Integer, Float, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base


class VendorModel(Base):
    __tablename__ = "vendor"
    vendor_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_id = Column(UUID(as_uuid=True), nullable=False)
    vendor_name = Column(String, nullable=False)
    completeness_score = Column(Float, default=0.0)
    submission_status = Column(String, default="pending")

    documents = relationship("VendorDocumentModel", back_populates="vendor", cascade="all, delete-orphan")


class VendorDocumentModel(Base):
    __tablename__ = "vendor_document"
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendor.vendor_id"), nullable=False)
    file_path = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=True)
    extraction_status = Column(String, nullable=False, default="pending")
    page_count = Column(Integer, nullable=True)
    document_type_code = Column(String, nullable=True)

    vendor = relationship("VendorModel", back_populates="documents")
    chunks = relationship("DocumentChunkModel", back_populates="document", cascade="all, delete-orphan")


class DocumentChunkModel(Base):
    __tablename__ = "document_chunk"
    chunk_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("vendor_document.document_id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    section_heading = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # store JSON array or serialized vector
    embedded_at = Column(String, nullable=True)
    embedding_model = Column(String, nullable=True)

    document = relationship("VendorDocumentModel", back_populates="chunks")


class DocumentTypeModel(Base):
    __tablename__ = "document_type"
    document_type_code = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    is_baseline = Column(Boolean, default=False)
