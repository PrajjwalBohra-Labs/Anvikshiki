from typing import Optional, Dict, Any, AsyncIterator, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from backend.app.infrastructure.database.models import DurableGraphCheckpointModel
import structlog

logger = structlog.get_logger(__name__)

class DurableDatabaseCheckpointer(BaseCheckpointSaver):
    """
    Persists LangGraph execution snapshots into authoritative PostgreSQL / database tables.
    Survives backend process termination and process restarts.
    """
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session

    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")

        stmt = select(DurableGraphCheckpointModel).where(DurableGraphCheckpointModel.thread_id == thread_id)
        if checkpoint_id:
            stmt = stmt.where(DurableGraphCheckpointModel.checkpoint_id == checkpoint_id)
        else:
            stmt = stmt.order_by(DurableGraphCheckpointModel.created_at.desc())

        result = await self.session.execute(stmt)
        record = result.scalars().first()
        if not record:
            return None

        checkpoint = record.state_payload
        metadata = record.metadata_payload or {}
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_id": record.checkpoint_id}},
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config={"configurable": {"thread_id": thread_id, "checkpoint_id": record.parent_checkpoint_id}} if record.parent_checkpoint_id else None
        )

    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        record = DurableGraphCheckpointModel(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
            state_payload=dict(checkpoint),
            metadata_payload=dict(metadata) if metadata else {}
        )
        self.session.add(record)
        await self.session.commit()
        logger.info("Durable checkpoint committed to database", thread_id=thread_id, checkpoint_id=checkpoint_id)
        return {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}

    async def alist(self, config: Optional[Dict[str, Any]] = None, *, filter: Optional[Dict[str, Any]] = None, before: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        if not config or "configurable" not in config:
            return
        thread_id = config["configurable"]["thread_id"]
        stmt = select(DurableGraphCheckpointModel).where(DurableGraphCheckpointModel.thread_id == thread_id).order_by(DurableGraphCheckpointModel.created_at.desc())
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        for record in result.scalars().all():
            yield CheckpointTuple(
                config={"configurable": {"thread_id": thread_id, "checkpoint_id": record.checkpoint_id}},
                checkpoint=record.state_payload,
                metadata=record.metadata_payload or {},
                parent_config=None
            )

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        raise NotImplementedError("Use async `aget_tuple`")

    def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError("Use async `aput`")

    def list(self, config: Optional[Dict[str, Any]] = None, *, filter: Optional[Dict[str, Any]] = None, before: Optional[Dict[str, Any]] = None, limit: Optional[int] = None):
        raise NotImplementedError("Use async `alist`")