from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.infrastructure.database.models import NotebookModel


class NotebookService:
    """Persistence use case for authenticated, user-owned notebooks."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_owned(self, user_id: str, *, limit: int = 100, offset: int = 0) -> list[NotebookModel]:
        result = await self.session.execute(
            select(NotebookModel)
            .where(NotebookModel.user_id == user_id)
            .order_by(NotebookModel.updated_at.desc(), NotebookModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_owned(self, user_id: str, notebook_id: str) -> NotebookModel | None:
        result = await self.session.execute(
            select(NotebookModel).where(
                NotebookModel.id == notebook_id,
                NotebookModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: str, title: str, content: str) -> NotebookModel:
        notebook = NotebookModel(user_id=user_id, title=title, content=content)
        self.session.add(notebook)
        await self.session.commit()
        await self.session.refresh(notebook)
        return notebook

    async def update(
        self,
        user_id: str,
        notebook_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> NotebookModel | None:
        notebook = await self.get_owned(user_id, notebook_id)
        if notebook is None:
            return None
        if title is not None:
            notebook.title = title
        if content is not None:
            notebook.content = content
        notebook.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(notebook)
        return notebook

    async def delete(self, user_id: str, notebook_id: str) -> bool:
        result = await self.session.execute(
            delete(NotebookModel).where(
                NotebookModel.id == notebook_id,
                NotebookModel.user_id == user_id,
            )
        )
        await self.session.commit()
        return result.rowcount == 1
