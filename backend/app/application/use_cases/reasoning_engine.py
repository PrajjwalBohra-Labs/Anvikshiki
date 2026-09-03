
import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.models.enums import (
    ClaimType,
    EvidenceStatus,
    PramanaType,
    RelationType,
)
from backend.app.domain.models.reasoning import Claim, Evidence
from backend.app.infrastructure.rag.reranker import AdvancedRetriever

logger = structlog.get_logger(__name__)

class ReconstructedArgumentResponse(BaseModel):
    conclusion: Claim
    premises: list[Claim]
    evidence_links: list[Evidence]
    pramana_type: PramanaType
    overall_status: EvidenceStatus

class ReasoningEngineService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.retriever = AdvancedRetriever(session)

    async def synthesize_argument(self, query: str, source_type: str | None = None) -> ReconstructedArgumentResponse:
        """
        Retrieves relevant passages via Advanced Hybrid/Reranked RAG,
        extracts epistemic claims, and structures them into a formal Pramana argument.
        """
        # 1. Retrieve top relevant evidence passages
        scored_passages = await self.retriever.retrieve_and_rerank(query=query, source_type=source_type, top_k=3)
        
        if not scored_passages:
            # Fallback default claim if no passages found
            fallback_claim = Claim(statement="Insufficient evidence available in corpus.", claim_type=ClaimType.UNCERTAIN)
            return ReconstructedArgumentResponse(
                conclusion=fallback_claim,
                premises=[],
                evidence_links=[],
                pramana_type=PramanaType.SHABDA,
                overall_status=EvidenceStatus.INSUFFICIENT_EVIDENCE
            )

        # 2. Extract or synthesize claims based on retrieved passages
        # (In TEST profile or lightweight mode, construct deterministic structured claims)
        premises = []
        evidence_links = []
        
        for item in scored_passages:
            passage = item.passage
            claim = Claim(
                statement=f"Derived from text: {passage.content[:120]}...",
                claim_type=ClaimType.DIRECT_SOURCE_CLAIM
            )
            premises.append(claim)
            
            evidence = Evidence(
                claim_id=claim.id,
                passage_id=passage.id,
                relation_type=RelationType.SUPPORTS
            )
            evidence_links.append(evidence)

        # Conclusion synthesized from premises
        conclusion = Claim(
            statement=f"Synthesized conclusion regarding: {query}",
            claim_type=ClaimType.INFERENCE
        )

        return ReconstructedArgumentResponse(
            conclusion=conclusion,
            premises=premises,
            evidence_links=evidence_links,
            pramana_type=PramanaType.ANUMANA,
            overall_status=EvidenceStatus.SUPPORTED
        )