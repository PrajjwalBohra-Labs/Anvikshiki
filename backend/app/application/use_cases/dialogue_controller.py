from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import PassageModel, DocumentModel, SourceModel
from backend.app.infrastructure.rag.retriever import HybridRetriever
from backend.app.agents.supervisor import create_inquiry_graph
from backend.app.application.use_cases.conduct_research import ResearchCoordinator
from backend.app.application.use_cases.memory_service import MemoryService

class DialogueResponse:
    def __init__(
        self,
        inquiry_summary: str,
        arguments_examined: List[Dict[str, Any]],
        critical_challenges: List[str],
        uncertainties: List[str],
        unresolved_question: Optional[str] = None
    ):
        self.inquiry_summary = inquiry_summary
        self.arguments_examined = arguments_examined
        self.critical_challenges = critical_challenges
        self.uncertainties = uncertainties
        self.unresolved_question = unresolved_question

class DialogueController:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.research_coordinator = ResearchCoordinator(session)
        self.memory_service = MemoryService(session)
        self.inquiry_graph = create_inquiry_graph()

    async def process_user_turn(
        self,
        user_id: str,
        user_message: str,
        user_position: Optional[str] = None,
        confidence: float = 0.5
    ) -> DialogueResponse:
        # 1. Update/Record Epistemic State
        if user_position:
            await self.memory_service.record_or_update_epistemic_position(
                user_id=user_id,
                claim_statement=user_message,
                position=user_position,
                confidence=confidence,
                status="under_investigation"
            )

        # 2. Hybrid Research
        research_result = await self.research_coordinator.conduct_research(user_message)

        # 3. Retrieve Rich Metadata for Passages
        passages_payload = []
        for sp in research_result.scored_passages:
            p = sp.passage
            # Query source metadata via document
            doc_res = await self.session.execute(select(DocumentModel).filter(DocumentModel.id == p.document_id))
            doc = doc_res.scalars().first()
            source = None
            if doc:
                src_res = await self.session.execute(select(SourceModel).filter(SourceModel.id == doc.source_id))
                source = src_res.scalars().first()

            passages_payload.append({
                "id": p.id,
                "content": p.content,
                "source_type": p.source_type.value,
                "author": source.author if source else None,
                "translator": source.translator if source else None,
                "original_language": source.original_language if source else None,
                "translation_year": 1900 if source and source.translator else None,
                "citation_string": source.citation_string if source else f"Page {p.page_number or 'N/A'}"
            })

        claims_payload = [
            {"id": c.id, "statement": c.statement}
            for c in research_result.claims
        ]

        agent_state = {
            "query": user_message,
            "user_id": user_id,
            "sub_questions": [sq.question for sq in research_result.plan.sub_questions],
            "retrieved_passages": passages_payload,
            "extracted_claims": claims_payload,
            "critique_findings": [],
            "reconstructed_arguments": [],
            "counterarguments": [],
            "uncertainties": [],
            "final_synthesis": None,
            "current_step": "init"
        }

        # 4. Multi-Agent LangGraph Execution
        final_graph_state = self.inquiry_graph.invoke(agent_state)

        # 5. Formulate Socratic Inquiry Question
        unresolved = "What further empirical or textual evidence would help clarify the boundaries of this claim?"
        if final_graph_state.get("counterarguments"):
            unresolved = f"How can this position address the identified counterpoint: '{final_graph_state['counterarguments'][0]}'?"

        return DialogueResponse(
            inquiry_summary=final_graph_state.get("final_synthesis", ""),
            arguments_examined=final_graph_state.get("reconstructed_arguments", []),
            critical_challenges=final_graph_state.get("counterarguments", []),
            uncertainties=final_graph_state.get("uncertainties", []),
            unresolved_question=unresolved
        )