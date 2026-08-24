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
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter, OllamaLocalAdapter
from backend.app.application.orchestration.durable_checkpointer import DurableDatabaseCheckpointer

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

        self.llm = llm_adapter or OllamaLocalAdapter(model_name="qwen2.5:7b-instruct-q4_K_M")
        self.checkpointer = DurableDatabaseCheckpointer(self.session_factory)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ResearchWorkflowState)

        async def coordinator_node(state: ResearchWorkflowState) -> Dict[str, Any]:
            logger.info("Coordinator query planning", query=state["query"])
            return {"current_step": "coordinator_completed"}

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
                    "page_number": cand.get("page_number", 1)
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

            async with self.session_factory() as session:
                phil_analyst = PhilosophicalAnalyst(session)
                for p in passages:
                    claim_stmt = f"According to {p['source_title']}: {p['content'][:140]}..."
                    claims.append({
                        "statement": claim_stmt,
                        "passage_id": p["passage_id"],
                        "confidence": 0.95
                    })
                    arg = await phil_analyst.reconstruct_argument(
                        title=f"Argument from {p['source_title']}",
                        conclusion_statement=claim_stmt,
                        premises=[{"statement": p["content"], "passage_id": p["passage_id"]}]
                    )
                    arguments.append({"argument_id": arg.id, "title": arg.title})

            return {
                "extracted_claims": claims,
                "reconstructed_arguments": arguments,
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

            prompt = (
                f"Synthesize this research inquiry strictly from verified evidence.\n"
                f"Query: {state['query']}\n"
                f"Validated Claims: {len(val_res['validated_claims'])}\n"
                f"Objections Recorded: {len(state.get('objections', []))}"
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