import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.infrastructure.database.session import Base
from backend.app.domain.models.enums import (
    SourceType, ClaimType, EvidenceStatus, PramanaType
)

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class SourceModel(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    historical_era: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    original_language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    translator: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), nullable=False, default=SourceType.UNVERIFIED)
    citation_string: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    documents: Mapped[List["DocumentModel"]] = relationship("DocumentModel", back_populates="source", cascade="all, delete-orphan")

class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    total_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ocr_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source: Mapped["SourceModel"] = relationship("SourceModel", back_populates="documents")
    passages: Mapped[List["PassageModel"]] = relationship("PassageModel", back_populates="document", cascade="all, delete-orphan")

class PassageModel(Base):
    __tablename__ = "passages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), nullable=False)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, default=1.0)
    extraction_uncertainty: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(16), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped["DocumentModel"] = relationship("DocumentModel", back_populates="passages")

class ClaimModel(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[ClaimType] = mapped_column(SQLEnum(ClaimType), nullable=False)
    pramana_type: Mapped[Optional[PramanaType]] = mapped_column(SQLEnum(PramanaType), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[EvidenceStatus] = mapped_column(SQLEnum(EvidenceStatus), default=EvidenceStatus.UNRESOLVED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class EpistemicStateModel(Base):
    __tablename__ = "epistemic_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(64), default="default_user", index=True)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("claims.id"), nullable=False)
    user_position: Mapped[str] = mapped_column(String(256), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="under_investigation")
    supporting_evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    counterarguments: Mapped[dict] = mapped_column(JSON, default=dict)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)