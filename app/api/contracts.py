"""
Engine Contract (§21): every engine exposed through the API Gateway
implements initialize/execute/validate/shutdown and communicates
through structured objects -- Python dicts of named fields -- never a
raw prompt string passed between layers. Scoped to the genuine
cognitive engines exposed via API (Conversation, Search, Research,
Document Ingestion); CRUD-style endpoints are plain data access, not
engines, and stay as thin routes without this wrapper.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.infrastructure.llm_adapter import LLMAdapter
from app.services.conversation.conversation_controller import handle_message
from app.services.knowledge.ingestion import ingest_document
from app.services.knowledge.retrieval import retrieve
from app.services.memory.memory_engine import MemoryEngine
from app.services.research.research_engine import research


class EngineContract(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def execute(self, request: dict) -> dict: ...

    @abstractmethod
    def validate(self, response: dict) -> bool: ...

    @abstractmethod
    def shutdown(self) -> None: ...


class ConversationEngine(EngineContract):
    def __init__(self, llm_adapter: LLMAdapter, memory_engine: MemoryEngine):
        self._llm_adapter = llm_adapter
        self._memory_engine = memory_engine
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    def execute(self, request: dict) -> dict:
        if not self._initialized:
            raise RuntimeError("ConversationEngine.initialize() must be called before execute()")
        result = handle_message(
            query=request["query"],
            session_id=request.get("session_id"),
            conversation_history=request.get("conversation_history"),
            project_id=request.get("project_id"),
            use_web_search=request.get("use_web_search", False),
            llm_adapter=self._llm_adapter,
            memory_engine=self._memory_engine,
        )
        verification = None
        context_summary = None
        if result.reasoning is not None:
            contradictions = sum(1 for c in result.reasoning.comparisons if c["relation"] == "divergence")
            verification = {
                "sources_checked": len(result.reasoning.evidence),
                "evidence_count": len(result.reasoning.facts),
                "contradictions_detected": contradictions,
                "agreement_score": (
                    result.reasoning.confidence.agreement_among_sources if result.reasoning.confidence else None
                ),
                "confidence": result.reasoning.confidence.overall if result.reasoning.confidence else None,
            }
            distinct_docs = {
                e.get("source_document_id") for e in result.reasoning.evidence if e.get("source_document_id")
            }
            context_summary = {
                "retrieved_chunk_count": len(result.reasoning.facts),
                "document_count": len(distinct_docs),
                "concept_relationship_count": len(result.reasoning.relationships),
            }

        return {
            "session_id": result.session_id,
            "response": result.response,
            "delivered": result.delivered,
            "confidence": result.reasoning.confidence.overall if result.reasoning and result.reasoning.confidence else None,
            "state_trace": [s.value for s in result.state_trace],
            "verification": verification,
            "context": context_summary,
        }

    def validate(self, response: dict) -> bool:
        return "response" in response and "delivered" in response

    def shutdown(self) -> None:
        self._initialized = False


class SearchEngine(EngineContract):
    def __init__(self, llm_adapter: LLMAdapter):
        self._llm_adapter = llm_adapter
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    def execute(self, request: dict) -> dict:
        if not self._initialized:
            raise RuntimeError("SearchEngine.initialize() must be called before execute()")
        chunks = retrieve(
            request["query"],
            top_k=request.get("top_k", 5),
            document_id=request.get("document_id"),
            llm_adapter=self._llm_adapter,
        )
        return {
            "results": [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "document_title": c.document_title,
                    "chunk_text": c.chunk_text,
                    "score": c.score,
                }
                for c in chunks
            ]
        }

    def validate(self, response: dict) -> bool:
        return "results" in response

    def shutdown(self) -> None:
        self._initialized = False


class ResearchEngineContract(EngineContract):
    def __init__(self, llm_adapter: LLMAdapter, memory_engine: MemoryEngine):
        self._llm_adapter = llm_adapter
        self._memory_engine = memory_engine
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    def execute(self, request: dict) -> dict:
        if not self._initialized:
            raise RuntimeError("ResearchEngineContract.initialize() must be called before execute()")
        result = research(
            request["question"],
            top_k=request.get("top_k", 5),
            use_web_search=request.get("use_web_search", False),
            llm_adapter=self._llm_adapter,
            memory_engine=self._memory_engine,
        )
        return {
            "question": result.question,
            "sub_questions": result.sub_questions,
            "synthesized_answer": result.synthesized_answer,
            "references": result.references,
            "comparisons": result.comparisons,
            "delivered": result.delivered,
            "validation_violations": result.validation_violations,
        }

    def validate(self, response: dict) -> bool:
        return "synthesized_answer" in response and "references" in response

    def shutdown(self) -> None:
        self._initialized = False


class DocumentEngine(EngineContract):
    def __init__(self, llm_adapter: LLMAdapter):
        self._llm_adapter = llm_adapter
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    def execute(self, request: dict) -> dict:
        if not self._initialized:
            raise RuntimeError("DocumentEngine.initialize() must be called before execute()")
        result = ingest_document(
            filename=request["filename"],
            raw_bytes=request["content_bytes"],
            title=request.get("title"),
            project_id=request.get("project_id"),
            llm_adapter=self._llm_adapter,
        )
        return {
            "document_id": result.document_id,
            "concept_id": result.concept_id,
            "chunk_count": result.chunk_count,
        }

    def validate(self, response: dict) -> bool:
        return "document_id" in response and response.get("chunk_count", 0) >= 0

    def shutdown(self) -> None:
        self._initialized = False




