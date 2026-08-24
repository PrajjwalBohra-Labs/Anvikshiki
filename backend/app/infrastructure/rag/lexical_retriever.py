from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
from sqlalchemy.orm import selectinload
from backend.app.infrastructure.database.models import PassageModel, DocumentModel, SourceModel
from backend.app.domain.models.enums import SourceType

class ScoredPassage:
    def __init__(self, passage: PassageModel, score: float):
        self.passage = passage
        self.score = score

class LexicalRetriever:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self, 
        query: str, 
        source_type: Optional[SourceType] = None, 
        language: Optional[str] = None, 
        limit: int = 10, 
        offset: int = 0
    ) -> List[ScoredPassage]:
        """
        Performs a deterministic lexical search across passage contents.
        Includes metadata filtering and basic Term-Frequency (TF) ranking.
        """
        # 1. Sanitize and tokenize query (ignoring very short stop words)
        terms = [t.lower() for t in query.split() if len(t) > 2]
        if not terms:
            return []

        # 2. Build the cross-database compatible query
        # (Matches passages containing AT LEAST ONE of the query terms)
        conditions = [PassageModel.content.ilike(f"%{term}%") for term in terms]
        
        stmt = select(PassageModel).join(PassageModel.document).join(DocumentModel.source)
        stmt = stmt.where(or_(*conditions))
        
        # 3. Apply Metadata Filters
        if source_type:
            stmt = stmt.where(SourceModel.source_type == source_type)
        if language:
            stmt = stmt.where(PassageModel.language == language)
            
        # Eagerly load provenance data to prevent N+1 queries during serialization
        stmt = stmt.options(selectinload(PassageModel.document).selectinload(DocumentModel.source))
        stmt = stmt.offset(offset).limit(limit * 2) # Fetch extra to allow for ranking before final limit

        result = await self.session.execute(stmt)
        passages = result.scalars().all()

        # 4. Rank results by simple Term Frequency (TF) score
        scored_results = []
        for passage in passages:
            content_lower = passage.content.lower()
            # Calculate score based on how many times the search terms appear
            score = sum(content_lower.count(term) for term in terms)
            
            # Bonus points if the exact original phrase appears intact
            if query.lower() in content_lower:
                score += 5.0
                
            scored_results.append(ScoredPassage(passage=passage, score=float(score)))

        # 5. Sort descending by score and apply exact limit
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:limit]