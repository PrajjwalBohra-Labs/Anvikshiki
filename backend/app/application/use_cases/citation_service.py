from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.core.errors import AnvikshikiDomainError
from backend.app.domain.models.enums import SourceType
from backend.app.domain.models.source import Citation
from backend.app.infrastructure.database.models import DocumentModel, PassageModel


class CitationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _format_citation(passage: PassageModel) -> Citation:
        """Build the public citation value from an already-loaded passage."""
        source = passage.document.source
        citation_parts = [source.title]
        if source.author:
            citation_parts.append(f"by {source.author}")
        if source.source_type == SourceType.DISCOVERY_ONLY and source.reference_url:
            citation_parts.append(f"(Retrieved from {source.reference_url})")
        if passage.page_number:
            citation_parts.append(f"p. {passage.page_number}")
        return Citation(
            passage_id=passage.id,
            source_id=source.id,
            citation_string=", ".join(citation_parts),
        )

    async def generate_citation(self, passage_id: str) -> Citation:
        """Resolve a passage ID into one canonical citation object."""
        citations = await self.generate_citations([passage_id])
        citation = citations.get(passage_id)
        if citation is None:
            raise AnvikshikiDomainError(
                f"Cannot generate citation: passage {passage_id} does not exist.",
                status_code=404,
            )
        return citation

    async def generate_citations(self, passage_ids: Iterable[str]) -> dict[str, Citation]:
        """Resolve many citations with one authoritative database read."""
        requested_ids = list(dict.fromkeys(passage_ids))
        if not requested_ids:
            return {}
        stmt = (
            select(PassageModel)
            .where(PassageModel.id.in_(requested_ids))
            .options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
        )
        result = await self.session.execute(stmt)
        passages = result.scalars().all()
        return {passage.id: self._format_citation(passage) for passage in passages}

    async def validate_ai_citation(self, passage_id: str, claimed_source_id: str) -> bool:
        """Verify that a claimed passage belongs to the claimed source."""
        stmt = select(PassageModel).where(PassageModel.id == passage_id).options(
            selectinload(PassageModel.document)
        )
        result = await self.session.execute(stmt)
        passage = result.scalars().first()
        if not passage:
            return False
        return passage.document.source_id == claimed_source_id
