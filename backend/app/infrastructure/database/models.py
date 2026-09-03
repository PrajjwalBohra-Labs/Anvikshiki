import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.config import RuntimeProfile, settings
from backend.app.domain.models.enums import (
    ClaimType,
    EmbeddingIndexStatus,
    EvidenceStatus,
    ProvenanceNodeType,
    ProvenanceRelationType,
    RelationType,
    SourceRelationshipType,
    SourceType,
)
from backend.app.infrastructure.database.session import Base

try:
    from pgvector.sqlalchemy import Vector
    from sqlalchemy.dialects.postgresql import TSVECTOR
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None
    TSVECTOR = None

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    conversations: Mapped[list["ConversationModel"]] = relationship("ConversationModel", back_populates="user", cascade="all, delete-orphan")
    auth_sessions: Mapped[list["AuthSessionModel"]] = relationship("AuthSessionModel", back_populates="user", cascade="all, delete-orphan")


class BackgroundJobModel(Base):
    """Durable, user-owned work item for the Step 63 worker."""

    __tablename__ = "background_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    research_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    result_payload: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(String(256))
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "job_type", "idempotency_key", name="uix_background_job_idempotency"),
    )


class AuthSessionModel(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="auth_sessions")

class SourceModel(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[str | None] = mapped_column(String(256))
    historical_era: Mapped[str | None] = mapped_column(String(128))
    original_language: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), default=SourceType.UNVERIFIED)
    reference_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    documents: Mapped[list["DocumentModel"]] = relationship("DocumentModel", back_populates="source", cascade="all, delete-orphan")
    targets: Mapped[list["SourceRelationshipModel"]] = relationship(
        "SourceRelationshipModel", foreign_keys="[SourceRelationshipModel.source_id]", back_populates="source", cascade="all, delete-orphan"
    )
    criticisms: Mapped[list["SourceCriticismModel"]] = relationship("SourceCriticismModel", back_populates="source", cascade="all, delete-orphan")

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
    total_pages: Mapped[int | None] = mapped_column(Integer)
    original_filename: Mapped[str | None] = mapped_column(String(512))
    storage_path: Mapped[str | None] = mapped_column(String(1024))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(32))
    extraction_method: Mapped[str | None] = mapped_column(String(64))
    extraction_status: Mapped[str | None] = mapped_column(String(32))
    extraction_warnings: Mapped[list[str] | None] = mapped_column(JSON)
    web_metadata: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source: Mapped["SourceModel"] = relationship("SourceModel", back_populates="documents")
    versions: Mapped[list["DocumentVersionModel"]] = relationship(
        "DocumentVersionModel", back_populates="document", cascade="all, delete-orphan"
    )
    passages: Mapped[list["PassageModel"]] = relationship("PassageModel", back_populates="document", cascade="all, delete-orphan")


class DocumentVersionModel(Base):
    __tablename__ = "document_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    extraction_warnings: Mapped[list[str] | None] = mapped_column(JSON)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uix_document_version_number"),
        UniqueConstraint("checksum_sha256", name="uix_document_version_checksum"),
    )

    document: Mapped["DocumentModel"] = relationship("DocumentModel", back_populates="versions")
    pages: Mapped[list["PageModel"]] = relationship(
        "PageModel", back_populates="document_version", cascade="all, delete-orphan"
    )
    passages: Mapped[list["PassageModel"]] = relationship(
        "PassageModel", back_populates="document_version", cascade="all, delete-orphan"
    )


class PageModel(Base):
    __tablename__ = "pages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_versions.id"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_order: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    native_extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    extraction_warnings: Mapped[list[str] | None] = mapped_column(JSON)
    ocr_status: Mapped[str | None] = mapped_column(String(32))
    ocr_language: Mapped[str | None] = mapped_column(String(128))
    ocr_dpi: Mapped[int | None] = mapped_column(Integer)
    ocr_text_length: Mapped[int | None] = mapped_column(Integer)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ocr_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("document_version_id", "page_number", name="uix_page_version_number"),
        UniqueConstraint("document_version_id", "page_order", name="uix_page_version_order"),
    )

    document_version: Mapped["DocumentVersionModel"] = relationship(
        "DocumentVersionModel", back_populates="pages"
    )
    passages: Mapped[list["PassageModel"]] = relationship(
        "PassageModel", back_populates="page", cascade="all, delete-orphan"
    )


class PassageModel(Base):
    __tablename__ = "passages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    document_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("document_versions.id"), index=True
    )
    page_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("pages.id"), index=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    passage_order: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_method: Mapped[str | None] = mapped_column(String(64))
    section_heading: Mapped[str | None] = mapped_column(String(512))
    ocr_confidence: Mapped[float | None] = mapped_column(Float, default=1.0)
    extraction_uncertainty: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(16), default="en")
    
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    embedding_provider: Mapped[str | None] = mapped_column(String(64))
    embedding_model_version: Mapped[str | None] = mapped_column(String(128))
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    embedding_config_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    embedding_content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    embedding_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding_status: Mapped[EmbeddingIndexStatus] = mapped_column(
        # A row constructed by legacy callers with a vector is already a
        # usable derived index entry. Canonical ingestion explicitly sets
        # PENDING before invoking EmbeddingIndexService.
        SQLEnum(EmbeddingIndexStatus),
        default=EmbeddingIndexStatus.INDEXED,
        nullable=False,
        index=True,
    )
    embedding_error: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[Any | None] = mapped_column(
        Vector(384) if PGVECTOR_AVAILABLE and settings.RUNTIME_PROFILE != RuntimeProfile.TEST else JSON
    )
    # Derived search state. ``content`` remains authoritative. The 0010
    # migration maintains this tsvector with a PostgreSQL trigger; SQLite
    # test databases use text and the retriever's compatibility path.
    search_vector: Mapped[Any | None] = mapped_column(
        TSVECTOR() if PGVECTOR_AVAILABLE and settings.RUNTIME_PROFILE != RuntimeProfile.TEST else Text
    )

    __table_args__ = (
        Index(
            "ix_passages_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )
    
    document: Mapped["DocumentModel"] = relationship("DocumentModel", back_populates="passages")
    document_version: Mapped[Optional["DocumentVersionModel"]] = relationship(
        "DocumentVersionModel", back_populates="passages"
    )
    page: Mapped[Optional["PageModel"]] = relationship("PageModel", back_populates="passages")


# A number of isolated integration fixtures create tables directly from ORM
# metadata. Keep those PostgreSQL schemas equivalent to the Alembic schema so
# lexical retrieval does not silently operate on an unmaintained tsvector.
event.listen(
    PassageModel.__table__,
    "after_create",
    DDL(
        """
        CREATE OR REPLACE FUNCTION passages_search_vector_refresh() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple'::regconfig, coalesce(NEW.content, ''));
            RETURN NEW;
        END;
        $$;
        DROP TRIGGER IF EXISTS passages_search_vector_refresh_trigger ON passages;
        CREATE TRIGGER passages_search_vector_refresh_trigger
        BEFORE INSERT OR UPDATE OF content ON passages
        FOR EACH ROW EXECUTE FUNCTION passages_search_vector_refresh();
        """
    ).execute_if(dialect="postgresql"),
)


class MemoryRecordModel(Base):
    """Durable, user-owned record for the generic Step 43 memory tiers."""

    __tablename__ = "memory_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    memory_tier: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    provenance_source_id: Mapped[str | None] = mapped_column(
        String(256), index=True
    )
    source_event: Mapped[str] = mapped_column(
        String(256), nullable=False, default="interaction"
    )
    retention_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="durable"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ProvenanceNodeModel(Base):
    """Typed, stable graph nodes backed by existing domain identities."""

    __tablename__ = "provenance_nodes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    node_type: Mapped[ProvenanceNodeType] = mapped_column(
        SQLEnum(ProvenanceNodeType), nullable=False, index=True
    )
    entity_id: Mapped[str] = mapped_column(String(256), nullable=False)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("node_type", "entity_id", name="uix_provenance_node_identity"),
    )

    outgoing_edges: Mapped[list["ProvenanceEdgeModel"]] = relationship(
        "ProvenanceEdgeModel",
        foreign_keys="[ProvenanceEdgeModel.from_node_id]",
        back_populates="from_node",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list["ProvenanceEdgeModel"]] = relationship(
        "ProvenanceEdgeModel",
        foreign_keys="[ProvenanceEdgeModel.to_node_id]",
        back_populates="to_node",
        cascade="all, delete-orphan",
    )


class ProvenanceEdgeModel(Base):
    """Append-oriented typed relationship between two provenance nodes."""

    __tablename__ = "provenance_edges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    from_node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("provenance_nodes.id"), nullable=False, index=True
    )
    to_node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("provenance_nodes.id"), nullable=False, index=True
    )
    relationship_type: Mapped[ProvenanceRelationType] = mapped_column(
        SQLEnum(ProvenanceRelationType), nullable=False, index=True
    )
    metadata_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "from_node_id",
            "to_node_id",
            "relationship_type",
            name="uix_provenance_edge_identity",
        ),
    )

    from_node: Mapped["ProvenanceNodeModel"] = relationship(
        "ProvenanceNodeModel",
        foreign_keys=[from_node_id],
        back_populates="outgoing_edges",
    )
    to_node: Mapped["ProvenanceNodeModel"] = relationship(
        "ProvenanceNodeModel",
        foreign_keys=[to_node_id],
        back_populates="incoming_edges",
    )

class ClaimModel(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[ClaimType] = mapped_column(SQLEnum(ClaimType), nullable=False)
    provenance_id: Mapped[str | None] = mapped_column(String(36))
    research_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("research_runs.id"), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    evidence_links: Mapped[list["EvidenceLinkModel"]] = relationship("EvidenceLinkModel", back_populates="claim", cascade="all, delete-orphan")

class EvidenceLinkModel(Base):
    __tablename__ = "evidence_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    claim_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("claims.id"), nullable=True)
    premise_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("premises.id"), nullable=True)
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
    
    premises: Mapped[list["PremiseModel"]] = relationship("PremiseModel", back_populates="argument", cascade="all, delete-orphan")
    objections: Mapped[list["ObjectionModel"]] = relationship("ObjectionModel", back_populates="argument", cascade="all, delete-orphan")
    assumptions: Mapped[list["AssumptionModel"]] = relationship("AssumptionModel", back_populates="argument", cascade="all, delete-orphan")

class PremiseModel(Base):
    __tablename__ = "premises"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    argument_id: Mapped[str] = mapped_column(String(36), ForeignKey("arguments.id"), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    argument: Mapped["ArgumentModel"] = relationship("ArgumentModel", back_populates="premises")
    evidence_links: Mapped[list["EvidenceLinkModel"]] = relationship("EvidenceLinkModel", back_populates="premise", cascade="all, delete-orphan")

class ObjectionModel(Base):
    __tablename__ = "objections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    argument_id: Mapped[str] = mapped_column(String(36), ForeignKey("arguments.id"), nullable=False)
    objection_statement: Mapped[str] = mapped_column(Text, nullable=False)
    reply_statement: Mapped[str | None] = mapped_column(Text)
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
    supporting_evidence_payload: Mapped[dict | None] = mapped_column(JSON)
    contradicting_evidence_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    source: Mapped["SourceModel"] = relationship("SourceModel", back_populates="criticisms")

class ConceptModel(Base):
    __tablename__ = "concepts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    original_language_term: Mapped[str | None] = mapped_column(String(256))
    transliteration: Mapped[str | None] = mapped_column(String(256))
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class ConceptRelationshipModel(Base):
    __tablename__ = "concept_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_concept_id: Mapped[str] = mapped_column(String(36), ForeignKey("concepts.id"), nullable=False)
    target_concept_id: Mapped[str] = mapped_column(String(36), ForeignKey("concepts.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)

class ResearchQuestionModel(Base):
    __tablename__ = "research_questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # This may be an external identity supplied by an upstream auth system.
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    main_question: Mapped[str] = mapped_column(Text, nullable=False)
    subquestions: Mapped[list[str] | None] = mapped_column(JSON)
    scope: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(128))
    constraints: Mapped[list[str] | None] = mapped_column(JSON)
    user_position: Mapped[str | None] = mapped_column(Text)
    open_questions: Mapped[list[str] | None] = mapped_column(JSON)
    research_status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    research_history: Mapped[list[dict] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class ResearchRunModel(Base):
    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    research_question_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("research_questions.id"), index=True)
    thread_id: Mapped[str | None] = mapped_column(String(128), index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(128))
    depth: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    error_message: Mapped[str | None] = mapped_column(Text)
    output_references: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    steps: Mapped[list["ResearchStepModel"]] = relationship("ResearchStepModel", back_populates="run", cascade="all, delete-orphan")

class ResearchStepModel(Base):
    __tablename__ = "research_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_runs.id"), nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(192), index=True)
    event_sequence: Mapped[int | None] = mapped_column(Integer, index=True)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    step_type: Mapped[str] = mapped_column(String(64), default="GENERAL")
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint("run_id", "event_sequence", name="uix_research_step_run_sequence"),
    )
    
    run: Mapped["ResearchRunModel"] = relationship("ResearchRunModel", back_populates="steps")

class ConversationModel(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="conversations")
    messages: Mapped[list["MessageModel"]] = relationship("MessageModel", back_populates="conversation", cascade="all, delete-orphan")

class MessageModel(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    research_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("research_runs.id"), nullable=True)
    citations_payload: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    
    conversation: Mapped["ConversationModel"] = relationship("ConversationModel", back_populates="messages")
    research_run: Mapped[Optional["ResearchRunModel"]] = relationship("ResearchRunModel")

class EpistemicPositionModel(Base):
    __tablename__ = "epistemic_positions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    claim_statement: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    supporting_evidence_payload: Mapped[list | None] = mapped_column(JSON, nullable=True)
    counterarguments_payload: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="tentative")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    history: Mapped[list["EpistemicHistoryModel"]] = relationship("EpistemicHistoryModel", back_populates="position_ref", cascade="all, delete-orphan")

class EpistemicHistoryModel(Base):
    __tablename__ = "epistemic_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    position_id: Mapped[str] = mapped_column(String(36), ForeignKey("epistemic_positions.id"), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    position_ref: Mapped["EpistemicPositionModel"] = relationship("EpistemicPositionModel", back_populates="history")

class CognitiveObservationModel(Base):
    __tablename__ = "cognitive_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_detail: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    originating_interaction_id: Mapped[str] = mapped_column(String(36), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    @property
    def is_evidence_linked(self) -> bool:
        return bool(self.evidence_reference)

class DurableGraphCheckpointModel(Base):
    __tablename__ = "langgraph_checkpoints"
    thread_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    checkpoint_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_checkpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
