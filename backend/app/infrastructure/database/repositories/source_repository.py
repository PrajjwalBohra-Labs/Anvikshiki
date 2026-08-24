from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.infrastructure.database.repositories.base import BaseRepository

class SourceRepository(BaseRepository[SourceModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(SourceModel, session)

    async def get_by_checksum(self, checksum: str) -> Optional[DocumentModel]:
        result = await self.session.execute(
            select(DocumentModel).filter(DocumentModel.checksum_sha256 == checksum)
        )
        return result.scalars().first()

class PassageRepository(BaseRepository[PassageModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(PassageModel, session)

    async def get_by_document(self, document_id: str) -> List[PassageModel]:
        result = await self.session.execute(
            select(PassageModel).filter(PassageModel.document_id == document_id)
        )
        return list(result.scalars().all())