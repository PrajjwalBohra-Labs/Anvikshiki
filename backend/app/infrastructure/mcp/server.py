from typing import Any, Dict, List, Optional
import structlog
from backend.app.infrastructure.database.session import AsyncSessionLocal
from backend.app.infrastructure.rag.reranker import AdvancedRetriever
from backend.app.application.use_cases.citation_service import CitationService
from backend.app.application.use_cases.reasoning_engine import ReasoningEngineService
from backend.app.application.use_cases.provenance import ProvenanceService

logger = structlog.get_logger(__name__)

class AnvikshikiMcpServer:
    """
    Exposes Anvikshiki's epistemic retrieval, citation, and reasoning engines
    as Model Context Protocol (MCP) tools.
    """
    
    @staticmethod
    async def tool_search_corpus(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches the verified text corpus using Advanced Hybrid RAG and cross-encoder reranking."""
        async with AsyncSessionLocal() as session:
            retriever = AdvancedRetriever(session)
            citation_service = CitationService(session)
            
            scored_passages = await retriever.retrieve_and_rerank(query=query, top_k=top_k)
            results = []
            
            for item in scored_passages:
                passage = item.passage
                source = passage.document.source
                citation = await citation_service.generate_citation(passage.id)
                
                results.append({
                    "passage_id": passage.id,
                    "source_title": source.title,
                    "author": source.author,
                    "content": passage.content,
                    "page_number": passage.page_number,
                    "relevance_score": item.score,
                    "citation": citation.citation_string
                })
            return results

    @staticmethod
    async def tool_synthesize_argument(query: str) -> Dict[str, Any]:
        """Synthesizes a formal Pramana argument and evidence map for a given research query."""
        async with AsyncSessionLocal() as session:
            engine = ReasoningEngineService(session)
            argument = await engine.synthesize_argument(query=query)
            
            return {
                "conclusion": argument.conclusion.statement,
                "claim_type": argument.conclusion.claim_type,
                "pramana_type": argument.pramana_type,
                "overall_status": argument.overall_status,
                "premises_count": len(argument.premises),
                "evidence_links_count": len(argument.evidence_links)
            }

    @staticmethod
    async def tool_trace_provenance(source_id: str) -> List[Dict[str, Any]]:
        """Traces a source's lineage back to its root primary text."""
        async with AsyncSessionLocal() as session:
            prov_service = ProvenanceService(session)
            lineage = await prov_service.trace_lineage(source_id)
            return lineage