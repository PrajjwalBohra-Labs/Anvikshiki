from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import (
    ConceptModel, ConceptRelationshipModel,
    SourceModel, SourceRelationshipModel,
    EvidenceLinkModel, ClaimModel, PassageModel
)

class KnowledgeGraphService:
    """
    Provides graph querying, multi-hop traversal, related-concept retrieval,
    and related-source retrieval over authoritative PostgreSQL relationship tables.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_related_concepts(self, concept_id: str) -> List[Dict[str, Any]]:
        """Retrieves concepts connected via concept_relationships."""
        stmt = select(ConceptRelationshipModel).where(
            (ConceptRelationshipModel.source_concept_id == concept_id) |
            (ConceptRelationshipModel.target_concept_id == concept_id)
        )
        result = await self.session.execute(stmt)
        relations = result.scalars().all()

        related = []
        for rel in relations:
            target_id = rel.target_concept_id if rel.source_concept_id == concept_id else rel.source_concept_id
            target_concept = await self.session.get(ConceptModel, target_id)
            if target_concept:
                related.append({
                    "concept": target_concept,
                    "relationship_type": rel.relationship_type
                })
        return related

    async def get_related_sources(self, source_id: str) -> List[Dict[str, Any]]:
        """Retrieves sources connected via source_relationships (e.g., commentaries, translations)."""
        stmt = select(SourceRelationshipModel).where(
            (SourceRelationshipModel.source_id == source_id) |
            (SourceRelationshipModel.target_id == source_id)
        )
        result = await self.session.execute(stmt)
        relations = result.scalars().all()

        related = []
        for rel in relations:
            target_id = rel.target_id if rel.source_id == source_id else rel.source_id
            target_source = await self.session.get(SourceModel, target_id)
            if target_source:
                related.append({
                    "source": target_source,
                    "relationship_type": rel.relationship_type
                })
        return related

    async def traverse_evidence_subgraph(self, claim_id: str) -> List[Dict[str, Any]]:
        """Traverses from a claim through its evidence links to passages and sources."""
        stmt = select(EvidenceLinkModel).where(EvidenceLinkModel.claim_id == claim_id)
        result = await self.session.execute(stmt)
        links = result.scalars().all()

        subgraph = []
        for link in links:
            passage = await self.session.get(PassageModel, link.passage_id)
            document = passage.document if passage else None
            source = document.source if document else None
            subgraph.append({
                "evidence_link": link,
                "passage": passage,
                "document": document,
                "source": source
            })
        return subgraph