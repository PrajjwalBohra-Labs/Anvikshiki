from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.app.infrastructure.database.models import SourceModel, SourceRelationshipModel

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