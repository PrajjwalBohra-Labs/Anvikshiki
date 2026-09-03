
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.infrastructure.database.models import (
    ConceptModel,
    ConceptRelationshipModel,
)


class ConceptService:
    """
    Manages philosophical and scientific concepts, original terminology preservation,
    transliteration, aliases, definitions, and inter-concept relationships.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_concept(
        self,
        name: str,
        definition: str,
        original_language_term: str | None = None,
        transliteration: str | None = None,
        aliases: list[str] | None = None
    ) -> ConceptModel:
        concept = ConceptModel(
            name=name,
            definition=definition,
            original_language_term=original_language_term,
            transliteration=transliteration,
            aliases=aliases or []
        )
        self.session.add(concept)
        await self.session.commit()
        await self.session.refresh(concept)
        return concept

    async def search_concepts(self, query: str) -> list[ConceptModel]:
        stmt = select(ConceptModel).where(
            (ConceptModel.name.ilike(f"%{query}%")) |
            (ConceptModel.original_language_term.ilike(f"%{query}%")) |
            (ConceptModel.transliteration.ilike(f"%{query}%"))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def link_concepts(self, source_id: str, target_id: str, relationship_type: str) -> ConceptRelationshipModel:
        relation = ConceptRelationshipModel(
            source_concept_id=source_id,
            target_concept_id=target_id,
            relationship_type=relationship_type
        )
        self.session.add(relation)
        await self.session.commit()
        await self.session.refresh(relation)
        return relation