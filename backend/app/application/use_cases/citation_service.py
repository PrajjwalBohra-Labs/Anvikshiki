from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.app.infrastructure.database.models import PassageModel, DocumentModel
from backend.app.domain.models.source import Citation
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.domain.models.enums import SourceType

class CitationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_citation(self, passage_id: str) -> Citation:
        """Resolves a passage ID into a fully formatted canonical citation object."""
        stmt = select(PassageModel).where(PassageModel.id == passage_id).options(
            selectinload(PassageModel.document).selectinload(DocumentModel.source)
        )
        result = await self.session.execute(stmt)
        passage = result.scalars().first()
        
        if not passage:
            raise AnvikshikiDomainError(f"Cannot generate citation: passage {passage_id} does not exist.", status_code=404)
            
        source = passage.document.source
        
        # Format citation string based on source type and metadata
        citation_parts = [source.title]
        
        if source.author:
            citation_parts.append(f"by {source.author}")
            
        if source.source_type == SourceType.DISCOVERY_ONLY and source.reference_url:
            citation_parts.append(f"(Retrieved from {source.reference_url})")
            
        if passage.page_number:
            citation_parts.append(f"p. {passage.page_number}")
            
        citation_string = ", ".join(citation_parts)
        
        return Citation(
            passage_id=passage.id,
            source_id=source.id,
            citation_string=citation_string
        )

    async def validate_ai_citation(self, passage_id: str, claimed_source_id: str) -> bool:
        """
        Anti-Hallucination Guardrail: 
        Verifies that the LLM-claimed passage actually belongs to the claimed source.
        """
        stmt = select(PassageModel).where(PassageModel.id == passage_id).options(
            selectinload(PassageModel.document)
        )
        result = await self.session.execute(stmt)
        passage = result.scalars().first()
        
        if not passage:
            return False
            
        return passage.document.source_id == claimed_source_id