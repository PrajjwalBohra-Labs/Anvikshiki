from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.app.infrastructure.database.models import (
    ClaimModel,
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    SourceModel,
    SourceRelationshipModel,
)

class ProvenanceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def link_sources(self, source_id: str, target_id: str, relationship_type: str) -> SourceRelationshipModel:
        """Link a derivative source to its parent original source."""
        rel = SourceRelationshipModel(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type
        )
        self.session.add(rel)
        await self.session.commit()
        return rel

    async def trace_lineage(self, source_id: str) -> List[Dict]:
        """
        Recursively trace a source's lineage back to the primary text.
        Returns a list describing the chain from derivative to original.
        """
        lineage = []
        current_id = source_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            
            # Fetch current source and its outgoing targets (what it is derived from)
            stmt = select(SourceModel).where(SourceModel.id == current_id).options(
                selectinload(SourceModel.targets).selectinload(SourceRelationshipModel.target)
            )
            result = await self.session.execute(stmt)
            source = result.scalars().first()
            
            if not source:
                break
                
            lineage.append({
                "source_id": source.id,
                "title": source.title,
                "type": source.source_type
            })
            
            # Follow the first target upward (simplifying for linear lineage)
            if source.targets:
                primary_target = source.targets[0]
                lineage[-1]["derived_via"] = primary_target.relationship_type
                current_id = primary_target.target_id
            else:
                current_id = None
                
        return lineage

    async def trace_run(self, run_id: str) -> List[Dict]:
        """Return public source-to-passage traces for claims produced by a run."""
        stmt = (
            select(EvidenceLinkModel)
            .join(ClaimModel, ClaimModel.id == EvidenceLinkModel.claim_id)
            .where(ClaimModel.research_run_id == run_id)
            .options(
                selectinload(EvidenceLinkModel.passage)
                .selectinload(PassageModel.document)
                .selectinload(DocumentModel.source)
            )
            .order_by(EvidenceLinkModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        traces = []
        for link in result.scalars().all():
            passage = link.passage
            document = passage.document
            source = document.source
            traces.append(
                {
                    "evidence_link_id": link.id,
                    "claim_id": link.claim_id,
                    "premise_id": link.premise_id,
                    "relation_type": link.relation_type.value,
                    "confidence_weight": link.confidence_weight,
                    "passage": {
                        "passage_id": passage.id,
                        "document_id": passage.document_id,
                        "page_number": passage.page_number,
                        "content": passage.content,
                        "ocr_confidence": passage.ocr_confidence,
                        "extraction_uncertainty": passage.extraction_uncertainty,
                        "language": passage.language,
                    },
                    "document": {
                        "document_id": document.id,
                        "source_id": document.source_id,
                        "checksum_sha256": document.checksum_sha256,
                        "mime_type": document.mime_type,
                        "original_filename": document.original_filename,
                        "total_pages": document.total_pages,
                    },
                    "source": {
                        "source_id": source.id,
                        "title": source.title,
                        "author": source.author,
                        "historical_era": source.historical_era,
                        "original_language": source.original_language,
                        "source_type": source.source_type.value,
                        "reference_url": source.reference_url,
                    },
                    "source_lineage": await self.trace_lineage(source.id),
                }
            )
        return traces
