from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select

from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    ArgumentModel,
    ClaimModel,
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    PremiseModel,
    SourceCriticismModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine


pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_scientific_and_comparative_branches_execute_with_grounded_evidence() -> None:
    """Exercise the specialist nodes after live PostgreSQL vector retrieval."""
    assert engine.dialect.name == "postgresql"
    await engine.dispose()

    marker = f"specialistworkflow{uuid4().hex}"
    contents = [
        (
            f"{marker} A randomized trial measures whether practice improves recall. "
            "The trial reports an association between practice and recall."
        ),
        (
            f"{marker} A longitudinal observational study reports that practice predicts recall. "
            "The observation does not by itself establish causation."
        ),
    ]
    embedder = LocalSentenceTransformerEmbeddingAdapter()
    vectors = await embedder.embed_texts(contents)
    source_ids: list[str] = []
    document_ids: list[str] = []
    passage_ids: list[str] = []
    statements: list[str] = []

    def capture_vector_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "<=>" in statement:
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
    try:
        async with AsyncSessionLocal() as session:
            for index, (content, vector) in enumerate(zip(contents, vectors)):
                source = SourceModel(title=f"Specialist source {index}")
                session.add(source)
                await session.flush()
                document = DocumentModel(
                    source_id=source.id,
                    checksum_sha256=f"{marker}-{index}",
                    mime_type="text/plain",
                )
                session.add(document)
                await session.flush()
                passage = PassageModel(
                    document_id=document.id,
                    content=content,
                    page_number=index + 1,
                    embedding_model=embedder.model_version,
                    embedding=vector,
                )
                session.add(passage)
                await session.flush()
                source_ids.append(source.id)
                document_ids.append(document.id)
                passage_ids.append(passage.id)
            await session.commit()

        workflow = ResearchWorkflowEngine()
        result = await workflow.execute_research(
            f"{marker} What does practice do to recall, and what evidence supports the conclusion?",
            f"{marker}-user",
            domain="science",
            thread_id=marker,
        )

        assert statements, "specialist workflow did not execute PostgreSQL cosine SQL"
        assert result["retrieved_passages"]
        assert result["extracted_claims"]
        assert result["reconstructed_arguments"]
        assert result["criticisms"]
        assert result["scientific_analyses"]
        assert result["comparisons"]
        assert result["objections"]
        assert all(claim["passage_id"] in passage_ids for claim in result["extracted_claims"])
        assert all(analysis["study_type"] == "PASSAGE" for analysis in result["scientific_analyses"])
        comparison = result["comparisons"][0]
        assert comparison["primary_source_id"] in source_ids
        assert comparison["secondary_source_id"] in source_ids
        assert comparison["is_evidence_linked"] is True
        assert result["validated_claims"]
        assert all(item["passage_id"] in passage_ids for item in result["validated_claims"])
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
        async with AsyncSessionLocal() as session:
            argument_ids = []
            if "result" in locals():
                argument_ids = [item["argument_id"] for item in result["reconstructed_arguments"]]
            if argument_ids:
                await session.execute(
                    delete(EvidenceLinkModel).where(
                        EvidenceLinkModel.premise_id.in_(
                            select(PremiseModel.id).where(PremiseModel.argument_id.in_(argument_ids))
                        )
                    )
                )
                await session.execute(delete(PremiseModel).where(PremiseModel.argument_id.in_(argument_ids)))
                await session.execute(delete(ArgumentModel).where(ArgumentModel.id.in_(argument_ids)))
            await session.execute(delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id.in_(passage_ids)))
            await session.execute(delete(ClaimModel).where(ClaimModel.provenance_id.in_(passage_ids)))
            await session.execute(delete(SourceCriticismModel).where(SourceCriticismModel.source_id.in_(source_ids)))
            await session.execute(delete(PassageModel).where(PassageModel.id.in_(passage_ids)))
            await session.execute(delete(DocumentModel).where(DocumentModel.id.in_(document_ids)))
            await session.execute(delete(SourceModel).where(SourceModel.id.in_(source_ids)))
            await session.commit()
        await engine.dispose()
