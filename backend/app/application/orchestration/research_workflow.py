import json
from typing import TypedDict, List, Dict, Any, Optional, AsyncGenerator
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph import StateGraph, END

from backend.app.infrastructure.database.session import AsyncSessionLocal
from backend.app.application.use_cases.hybrid_retrieval import HybridRetrievalService
from backend.app.application.agents.philosophical_analyst import PhilosophicalAnalyst
from backend.app.application.agents.scientific_analyst import ScientificAnalyst
from backend.app.application.agents.source_critic_agent import SourceCriticAgent
from backend.app.application.agents.challenger_agent import ChallengerAgent
from backend.app.application.use_cases.synthesis_validation_service import SynthesisValidationService
from backend.app.application.use_cases.claim_extraction_service import ClaimExtractionService
from backend.app.application.memory.epistemic_memory import EpistemicMemoryService
from backend.app.application.agents.comparative_analyst import ComparativeAnalyst
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter, OllamaLocalAdapter
from backend.app.application.orchestration.durable_checkpointer import DurableDatabaseCheckpointer
from backend.app.core.config import settings

logger = structlog.get_logger(__name__)

class ResearchWorkflowState(TypedDict):
    query: str
    domain: str
    user_id: str
    retrieved_passages: List[Dict[str, Any]]
    extracted_claims: List[Dict[str, Any]]
    criticisms: List[Dict[str, Any]]
    reconstructed_arguments: List[Dict[str, Any]]
    objections: List[Dict[str, Any]]
    scientific_analyses: List[Dict[str, Any]]
    comparisons: List[Dict[str, Any]]
    user_epistemic_positions: List[Dict[str, Any]]
    validation_status: str
    validated_claims: List[Dict[str, Any]]
    final_response: str
    current_step: str

class ResearchWorkflowEngine:
    """
    LangGraph research orchestrator:
    Query -> Hybrid RAG -> Real Passages -> Specialist Agents -> Challenger -> LLM -> Validation.
    """
    def __init__(self, session_or_factory: Optional[Any] = None, llm_adapter: Optional[BaseModelAdapter] = None):
        if session_or_factory is not None and callable(session_or_factory):
            self.session_factory = session_or_factory
        else:
            self.session_factory = AsyncSessionLocal

        self.llm = llm_adapter or OllamaLocalAdapter(
            model_name=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
        self.checkpointer = DurableDatabaseCheckpointer(self.session_factory)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ResearchWorkflowState)

        async def coordinator_node(state: ResearchWorkflowState) -> Dict[str, Any]:
            logger.info("Coordinator query planning", query=state["query"])
            async with self.session_factory() as session:
                positions = await EpistemicMemoryService(session).get_user_positions(
                    state["user_id"]
                )
            positions = json.loads(json.dumps(positions, default=str))
            return {
                "user_epistemic_positions": positions,
                "current_step": "coordinator_completed",
            }

        async def retrieval_node(state: ResearchWorkflowState) -> Dict[str, Any]:
            query = state["query"]
            domain = state.get("domain", "Epistemology")
            
            async with self.session_factory() as session:
                retrieval_service = HybridRetrievalService(session)
                evidence_candidates = await retrieval_service.retrieve_evidence(
                    query=query,
                    domain=domain,
                    top_k=5
                )

            passages_data = [
                {
                    "passage_id": cand["passage_id"],
                    "content": cand["content"],
                    "source_title": cand.get("source_title", "Canonical Text"),
                    "page_number": cand.get("page_number", 1),
                    "source_id": cand.get("source_id"),
                    "source_type": cand.get("source_type", "UNVERIFIED"),
                    "retrieval_channels": cand.get("retrieval_channels", []),
                }
                for cand in evidence_candidates
            ]
            return {
                "retrieved_passages": passages_data,
                "current_step": "retrieval_completed"
            }

        async def specialist_analysis_node(state: ResearchWorkflowState) -> Dict[str, Any]:
            passages = state.get("retrieved_passages", [])
            claims = []
            arguments = []
            criticisms = []
            scientific_analyses = []
            comparisons = []

            async with self.session_factory() as session:
                phil_analyst = PhilosophicalAnalyst(session)
                claim_extractor = ClaimExtractionService(session)
                source_critic = SourceCriticAgent(session)
                seen_sources = set()
                for p in passages:
                    extracted = await claim_extractor.extract_claims_from_passage(
                        passage_id=p["passage_id"],
                        passage_content=p["content"],
                        source_title=p["source_title"],
                        source_type=p.get("source_type", "UNVERIFIED"),
                    )
                    for claim in extracted:
                        claims.append({
                            "statement": claim.statement,
                            "claim_type": claim.claim_type.value,
                            "passage_id": claim.provenance_id,
                            "confidence": claim.confidence,
                            "source_title": p["source_title"],
                        })
                    claim_stmt = extracted[0].statement if extracted else p["content"]
                    arg = await phil_analyst.reconstruct_argument(
                        title=f"Argument from {p['source_title']}",
                        conclusion_statement=claim_stmt,
                        premises=[{"statement": p["content"], "passage_id": p["passage_id"]}]
                    )
                    arguments.append({"argument_id": arg.id, "title": arg.title})

                    source_id = p.get("source_id")
                    if source_id and source_id not in seen_sources:
                        criticisms.append(await source_critic.evaluate_source(source_id))
                        seen_sources.add(source_id)

                    if state.get("domain", "").lower() in {"science", "scientific", "empirical"}:
                        scientific_analyses.append(
                            await ScientificAnalyst(session).analyze_study(
                                {"study_type": "PASSAGE", "methodology": p["content"]}
                            )
                        )

                source_ids = list(seen_sources)
                if len(source_ids) >= 2:
                    comparisons.append(
                        await ComparativeAnalyst(session).compare_perspectives(
                            primary_source_id=source_ids[0],
                            secondary_source_id=source_ids[1],
                            claims_to_compare=claims,
                            interpretations=[],
                            terminology_map={},
                            methodological_notes=[],
                        )
                    )

            return {
                "extracted_claims": claims,
                "reconstructed_arguments": arguments,
                "criticisms": criticisms,
                "scientific_analyses": scientific_analyses,
                "comparisons": comparisons,
                "current_step": "specialist_analysis_completed"
            }

        async def challenger_node(state: ResearchWorkflowState) -> Dict[str, Any]:
            claims = state.get("extracted_claims", [])
            objections = []

            async with self.session_factory() as session:
                challenger = ChallengerAgent(session)
                for c in claims:
                    ch_res = await challenger.challenge_claim(c["statement"])
                    if ch_res.get("objections"):
                        objections.extend(ch_res["objections"])
                    else:
                        objections.append({"objection": f"Examine non-erroneous conditions for: {c['statement'][:60]}..."})

            return {
                "objections": objections,
                "current_step": "challenger_completed"
            }

        async def validation_node(state: ResearchWorkflowState) -> Dict[str, Any]:
            claims = state.get("extracted_claims", [])
            async with self.session_factory() as session:
                validator = SynthesisValidationService(session)
                val_res = await validator.validate_research_output(
                    claims, research_scope=state["domain"]
                )

            evidence_payload = {
                "passages": state.get("retrieved_passages", []),
                "claims": val_res["validated_claims"],
                "objections": state.get("objections", []),
                "source_criticisms": state.get("criticisms", []),
                "comparisons": state.get("comparisons", []),
                # User positions are context, not evidence. They are kept in a
                # separate field so synthesis cannot cite them as source claims.
                "user_epistemic_positions": state.get("user_epistemic_positions", []),
            }
            prompt = (
                "Synthesize this research inquiry strictly from the verified evidence below.\n"
                f"Query: {state['query']}\n"
                f"Evidence JSON:\n{json.dumps(evidence_payload, ensure_ascii=False, default=str)}\n"
                "Preserve passage IDs and source provenance in the answer."
            )
            llm_summary = await self.llm.generate(prompt=prompt, max_tokens=150)

            return {
                "validation_status": val_res["status"],
                "validated_claims": val_res["validated_claims"],
                "final_response": llm_summary["content"],
                "current_step": "validation_completed"
            }

        builder.add_node("coordinator", coordinator_node)
        builder.add_node("retrieval", retrieval_node)
        builder.add_node("specialist_analysis", specialist_analysis_node)
        builder.add_node("challenger", challenger_node)
        builder.add_node("validator", validation_node)

        builder.set_entry_point("coordinator")
        builder.add_edge("coordinator", "retrieval")
        builder.add_edge("retrieval", "specialist_analysis")
        builder.add_edge("specialist_analysis", "challenger")
        builder.add_edge("challenger", "validator")
        builder.add_edge("validator", END)

        return builder.compile(checkpointer=self.checkpointer)

    async def execute_research(self, query: str, user_id: str, domain: str = "Epistemology", thread_id: str = "default_thread") -> Dict[str, Any]:
        initial_state: ResearchWorkflowState = {
            "query": query,
            "domain": domain,
            "user_id": user_id,
            "retrieved_passages": [],
            "extracted_claims": [],
            "criticisms": [],
            "reconstructed_arguments": [],
            "objections": [],
            "scientific_analyses": [],
            "comparisons": [],
            "user_epistemic_positions": [],
            "validation_status": "PENDING",
            "validated_claims": [],
            "final_response": "",
            "current_step": "initialized"
        }
        config = {"configurable": {"thread_id": thread_id}}
        return await self.graph.ainvoke(initial_state, config=config)

    async def stream_research_events(self, query: str, user_id: str, domain: str = "Epistemology", thread_id: str = "default_thread") -> AsyncGenerator[Dict[str, Any], None]:
        initial_state: ResearchWorkflowState = {
            "query": query,
            "domain": domain,
            "user_id": user_id,
            "retrieved_passages": [],
            "extracted_claims": [],
            "criticisms": [],
            "reconstructed_arguments": [],
            "objections": [],
            "scientific_analyses": [],
            "comparisons": [],
            "user_epistemic_positions": [],
            "validation_status": "PENDING",
            "validated_claims": [],
            "final_response": "",
            "current_step": "initialized"
        }
        config = {"configurable": {"thread_id": thread_id}}

        yield {"event": "research_started", "query": query, "thread_id": thread_id}

        async for chunk in self.graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_update in chunk.items():
                step_status = node_update.get("current_step", f"{node_name}_completed")
                yield {
                    "event": f"{node_name}_event",
                    "node": node_name,
                    "status": step_status,
                    "summary": f"Executed {node_name} with verified outputs"
                }

        tuple_state = await self.checkpointer.aget_tuple(config)
        if tuple_state:
            state = tuple_state.checkpoint.get("channel_values", tuple_state.checkpoint)
            yield {
                "event": "research_completed",
                "validation_status": state.get("validation_status", "APPROVED"),
                "final_response": state.get("final_response", ""),
                "validated_claims_count": len(state.get("validated_claims", []))
            }
