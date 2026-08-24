from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domain.models.enums import ClaimType, EvidenceStatus, PramanaType, SourceType
from backend.app.domain.models.evidence import Claim
from backend.app.infrastructure.database.models import PassageModel, SourceModel
from backend.app.infrastructure.rag.retriever import HybridRetriever, ScoredPassage
from backend.app.application.use_cases.research_planner import ResearchPlan, ResearchPlanner

class EvidenceExtractionResult:
    def __init__(self, plan: ResearchPlan, claims: List[Claim], scored_passages: List[ScoredPassage]):
        self.plan = plan
        self.claims = claims
        self.scored_passages = scored_passages

class ResearchCoordinator:
    def __init__(self, session: AsyncSession, retriever: HybridRetriever | None = None):
        self.session = session
        self.retriever = retriever or HybridRetriever(session)

    async def conduct_research(self, query: str) -> EvidenceExtractionResult:
        plan = ResearchPlanner.plan_query(query)
        collected_passages: List[ScoredPassage] = []
        extracted_claims: List[Claim] = []

        for sq in plan.sub_questions:
            passages = await self.retriever.hybrid_retrieve(query=sq.question, top_k=3)
            collected_passages.extend(passages)

            for sp in passages:
                passage = sp.passage
                # Classify claim based on provenance
                if passage.source_type == SourceType.PRIMARY:
                    c_type = ClaimType.DIRECT_SOURCE_CLAIM
                elif passage.source_type == SourceType.SCIENTIFIC_STUDY:
                    c_type = ClaimType.SCIENTIFIC_FINDING
                elif passage.source_type == SourceType.TRANSLATION:
                    c_type = ClaimType.TRANSLATION
                else:
                    c_type = ClaimType.SCHOLARLY_INTERPRETATION

                # Infer pramana type if relevant
                pramana = None
                content_lower = passage.content.lower()
                if "pratyaksha" in content_lower or "perception" in content_lower:
                    pramana = PramanaType.PRATYAKSHA
                elif "anumana" in content_lower or "inference" in content_lower:
                    pramana = PramanaType.ANUMANA

                claim = Claim(
                    id=f"claim_{passage.id[:8]}",
                    statement=passage.content[:200],
                    claim_type=c_type,
                    pramana_type=pramana,
                    supporting_passage_ids=[passage.id],
                    confidence_score=round(sp.score, 4),
                    status=EvidenceStatus.SUPPORTED if not passage.extraction_uncertainty else EvidenceStatus.WEAKLY_SUPPORTED
                )
                extracted_claims.append(claim)

        return EvidenceExtractionResult(
            plan=plan,
            claims=extracted_claims,
            scored_passages=collected_passages
        )