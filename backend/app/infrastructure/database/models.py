import uuid
from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.infrastructure.database.session import Base
from backend.app.domain.models.enums import SourceType, SourceRelationshipType, ClaimType, RelationType, EvidenceStatus

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    conversations: Mapped[List["ConversationModel"]] = relationship("ConversationModel", back_populates="user", cascade="all, delete-orphan")

class SourceModel(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(256))
    historical_era: Mapped[Optional[str]] = mapped_column(String(128))
    original_language: Mapped[Optional[str]] = mapped_column(String(64))
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), default=SourceType.UNVERIFIED)
    reference_url: Mapped[Optional[str]] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    documents: Mapped[List["DocumentModel"]] = relationship("DocumentModel", back_populates="source", cascade="all, delete-orphan")
    targets: Mapped[List["SourceRelationshipModel"]] = relationship(
        "SourceRelationshipModel", foreign_keys="[SourceRelationshipModel.source_id]", back_populates="source", cascade="all, delete-orphan"
    )
    criticisms: Mapped[List["SourceCriticismModel"]] = relationship("SourceCriticismModel", back_populates="source", cascade="all, delete-orphan")

class SourceRelationshipModel(Base):
    __tablename__ = "source_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"), nullable=False, index=True)
    relationship_type: Mapped[SourceRelationshipType] = mapped_column(SQLEnum(SourceRelationshipType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    __table_args__ = (UniqueConstraint('source_id', 'target_id', 'relationship_type', name='uix_source_target_rel'),)
    
    source: Mapped["SourceModel"] = relationship("SourceModel", foreign_keys=[source_id], back_populates="targets")
    target: Mapped["SourceModel"] = relationship("SourceModel", foreign_keys=[target_id])

class DocumentModel(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mime_type: Mapped[str] = mapped_column(String(128))
    total_pages: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source: Mapped["SourceModel"] = relationship("SourceModel", back_populates="documents")
    passages: Mapped[List["PassageModel"]] = relationship("PassageModel", back_populates="document", cascade="all, delete-orphan")

class PassageModel(Base):
    __tablename__ = "passages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, default=1.0)
    extraction_uncertainty: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(16), default="en")
    
    embedding_model: Mapped[Optional[str]] = mapped_column(String(128))
    embedding: Mapped[Optional[List[float]]] = mapped_column(JSON)
    
    document: Mapped["DocumentModel"] = relationship("DocumentModel", back_populates="passages")

class ClaimModel(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[ClaimType] = mapped_column(SQLEnum(ClaimType), nullable=False)
    provenance_id: Mapped[Optional[str]] = mapped_column(String(36))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    evidence_links: Mapped[List["EvidenceLinkModel"]] = relationship("EvidenceLinkModel", back_populates="claim", cascade="all, delete-orphan")

class EvidenceLinkModel(Base):
    __tablename__ = "evidence_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    claim_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("claims.id"), nullable=True)
    premise_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("premises.id"), nullable=True)
    passage_id: Mapped[str] = mapped_column(String(36), ForeignKey("passages.id"), nullable=False)
    relation_type: Mapped[RelationType] = mapped_column(SQLEnum(RelationType), nullable=False)
    confidence_weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    claim: Mapped[Optional["ClaimModel"]] = relationship("ClaimModel", back_populates="evidence_links")
    premise: Mapped[Optional["PremiseModel"]] = relationship("PremiseModel", back_populates="evidence_links")
    passage: Mapped["PassageModel"] = relationship("PassageModel")

class ArgumentModel(Base):
    __tablename__ = "arguments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    conclusion_statement: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    premises: Mapped[List["PremiseModel"]] = relationship("PremiseModel", back_populates="argument", cascade="all, delete-orphan")
    objections: Mapped[List["ObjectionModel"]] = relationship("ObjectionModel", back_populates="argument", cascade="all, delete-orphan")
    assumptions: Mapped[List["AssumptionModel"]] = relationship("AssumptionModel", back_populates="argument", cascade="all, delete-orphan")

class PremiseModel(Base):
    __tablename__ = "premises"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    argument_id: Mapped[str] = mapped_column(String(36), ForeignKey("arguments.id"), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    argument: Mapped["ArgumentModel"] = relationship("ArgumentModel", back_populates="premises")
    evidence_links: Mapped[List["EvidenceLinkModel"]] = relationship("EvidenceLinkModel", back_populates="premise", cascade="all, delete-orphan")

class ObjectionModel(Base):
    __tablename__ = "objections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    argument_id: Mapped[str] = mapped_column(String(36), ForeignKey("arguments.id"), nullable=False)
    objection_statement: Mapped[str] = mapped_column(Text, nullable=False)
    reply_statement: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    argument: Mapped["ArgumentModel"] = relationship("ArgumentModel", back_populates="objections")

class AssumptionModel(Base):
    __tablename__ = "assumptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    argument_id: Mapped[str] = mapped_column(String(36), ForeignKey("arguments.id"), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    
    argument: Mapped["ArgumentModel"] = relationship("ArgumentModel", back_populates="assumptions")

class SourceCriticismModel(Base):
    __tablename__ = "source_criticisms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"), nullable=False)
    finding: Mapped[str] = mapped_column(Text, nullable=False)
    basis: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[EvidenceStatus] = mapped_column(SQLEnum(EvidenceStatus), default=EvidenceStatus.PLAUSIBLE)
    supporting_evidence_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    contradicting_evidence_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    source: Mapped["SourceModel"] = relationship("SourceModel", back_populates="criticisms")

class ConversationModel(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="conversations")
    messages: Mapped[List["MessageModel"]] = relationship("MessageModel", back_populates="conversation", cascade="all, delete-orphan")

class MessageModel(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    conversation: Mapped["ConversationModel"] = relationship("ConversationModel", back_populates="messages")

class ResearchRunModel(Base):
    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    steps: Mapped[List["ResearchStepModel"]] = relationship("ResearchStepModel", back_populates="run", cascade="all, delete-orphan")

class ResearchStepModel(Base):
    __tablename__ = "research_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_runs.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    run: Mapped["ResearchRunModel"] = relationship("ResearchRunModel", back_populates="steps")