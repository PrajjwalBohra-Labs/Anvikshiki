import os
import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.app.infrastructure.database.models import DocumentModel, PassageModel, SourceModel
from backend.app.infrastructure.ai.embedding_reranker_adapters import LocalSentenceTransformerEmbeddingAdapter
from backend.app.domain.models.enums import SourceType

logger = structlog.get_logger(__name__)

class DocumentIngestionService:
    """
    Orchestrates file ingestion, checksum calculation, passage chunking,
    and automatic 384-dimensional pgvector embedding generation.
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.embedder = LocalSentenceTransformerEmbeddingAdapter()

    async def ingest_document(
        self,
        source_id: str,
        content: str,
        filename: str,
        mime_type: str = "text/plain",
        chunk_size: int = 500
    ) -> DocumentModel:
        # 1. Compute SHA-256 Checksum
        sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()

        # 2. Persist Document Record
        doc = DocumentModel(
            source_id=source_id,
            checksum_sha256=sha256,
            mime_type=mime_type,
            total_pages=max(1, len(content) // chunk_size)
        )
        self.session.add(doc)
        await self.session.flush()

        # 3. Create Page-Aware Passages & Auto-Generate Embeddings
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
        embeddings = await self.embedder.embed_texts(chunks)

        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            passage = PassageModel(
                document_id=doc.id,
                page_number=idx + 1,
                content=chunk.strip(),
                embedding_model=self.embedder.model_version,
                embedding=emb
            )
            self.session.add(passage)

        await self.session.commit()
        await self.session.refresh(doc)
        logger.info("Document ingested and embedded into pgvector", document_id=doc.id, passages=len(chunks))
        return doc