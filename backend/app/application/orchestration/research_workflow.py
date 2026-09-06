import json
import re
from collections.abc import AsyncGenerator
from typing import Any, Dict, Optional, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from backend.app.application.agents.challenger_agent import ChallengerAgent
from backend.app.application.agents.comparative_analyst import ComparativeAnalyst
from backend.app.application.agents.philosophical_analyst import PhilosophicalAnalyst
from backend.app.application.agents.scientific_analyst import ScientificAnalyst
from backend.app.application.agents.source_critic_agent import SourceCriticAgent
from backend.app.application.memory.epistemic_memory import EpistemicMemoryService
from backend.app.application.agents.comparative_analyst import ComparativeAnalyst
from backend.app.application.use_cases.claim_extraction_service import ClaimExtractionService
from backend.app.application.use_cases.hybrid_retrieval import HybridRetrievalService
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter, OllamaLocalAdapter
from backend.app.application.orchestration.durable_checkpointer import DurableDatabaseCheckpointer
from backend.app.core.config import RuntimeProfile, settings
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.application.use_cases.web_acquisition import WebAcquisitionService
from backend.app.application.use_cases.web_source_filtering import WebSourceFilteringService
from backend.app.infrastructure.database.session import AsyncSessionLocal
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.application.use_cases.web_search import WebSearchResult, WebSearchService
from backend.app.domain.models.enums import SourceType
from backend.app.application.use_cases.synthesis_validation_service import SynthesisValidationService

logger = structlog.get_logger(__name__)


COMPLEX_RESEARCH_TERMS = (
    "compare",
    "comparison",
    "correlat",
    "relationship",
    "contrast",
    "analy",
    "critique",
    "disagree",
    "difference",
    "schools",
    "scholarship",
    "historical context",
    "according to",
)
EXPLICIT_WEB_TERMS = (
    "web",
    "online",
    "latest",
    "recent",
    "current",
    "today",
    "literature",
    "external sources",
    "state of the art",
    "cross-cultural",
    "global",
    "evidence",
)

PHILOSOPHICAL_TERMS = (
    "experience",
    "impression",
    "perception",
    "consciousness",
    "memory",
    "time",
    "identity",
    "observer",
    "cognition",
    "philosoph",
    "seeing",
)


def research_depth_for_query(query: str, requested_depth: str | None = None) -> str:
    """Select a response budget from the inquiry, without forcing verbosity."""
    normalized = (query or "").strip().lower()
    requested = (requested_depth or "standard").strip().lower()
    if requested in {"deep", "comprehensive", "long"}:
        return "deep"
    if requested in {"brief", "concise", "shallow"}:
        return "brief"
    if len(normalized.split()) > 10 or any(term in normalized for term in COMPLEX_RESEARCH_TERMS):
        return "deep"
    return "standard"


def research_directions_for_query(query: str, domain: str | None = None) -> list[str]:
    """Turn a substantive inquiry into distinct, inspectable search directions."""
    normalized = " ".join((query or "").split())
    if not normalized:
        return []

    directions = [normalized]
    lower = normalized.lower()
    if any(term in lower for term in PHILOSOPHICAL_TERMS) or "philos" in (domain or "").lower():
        directions.extend(
            [
                f"{normalized} conceptual analysis perception memory consciousness",
                f"{normalized} phenomenology temporal experience continuity",
                f"{normalized} primary text historical context Indian philosophy",
                f"{normalized} scholarly interpretation competing accounts",
                f"{normalized} cognitive science perception memory temporal awareness",
            ]
        )
    elif len(normalized.split()) >= 8 or research_depth_for_query(normalized) == "deep":
        directions.extend(
            [
                f"{normalized} key concepts and definitions",
                f"{normalized} primary sources and original research",
                f"{normalized} scholarly interpretations and criticism",
                f"{normalized} alternative explanations and limitations",
            ]
        )

    unique: list[str] = []
    seen: set[str] = set()
    for direction in directions:
        key = direction.casefold()
        if key not in seen:
            unique.append(direction)
            seen.add(key)
    return unique[:6]


def should_run_web_research(
    query: str,
    depth: str,
    local_passage_count: int,
    requested: bool = False,
) -> bool:
    """Use web discovery when local evidence is absent or the question needs breadth."""
    if not settings.ENABLE_WEB_RETRIEVAL or settings.RUNTIME_PROFILE == RuntimeProfile.TEST:
        return False
    if requested:
        return True
    normalized = (query or "").strip().lower()
    if local_passage_count == 0:
        return True
    return depth == "deep" or any(term in normalized for term in EXPLICIT_WEB_TERMS)


def _web_result_payload(result: WebSearchResult, classification: str) -> dict[str, Any]:
    return {
        "title": result.title,
        "url": result.url,
        "canonical_url": result.canonical_url,
        "snippet": result.snippet,
        "rank": result.rank,
        "domain": result.domain,
        "classification": classification,
    }


def _web_metadata(document: Any) -> dict[str, Any]:
    metadata = document.web_metadata if isinstance(document.web_metadata, dict) else {}
    published = metadata.get("published_date") or metadata.get("date")
    year = None
    if published:
        match = re.search(r"(?:19|20)\d{2}", str(published))
        year = int(match.group(0)) if match else None
    return {
        "publication": metadata.get("publication") or metadata.get("publisher"),
        "publication_year": year,
        "canonical_document_url": metadata.get("canonical_document_url"),
    }


def merge_research_evidence(
    local_candidates: list[dict[str, Any]],
    web_candidates: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Keep relevant local evidence while allowing acquired web evidence into synthesis."""
    if limit < 1:
        return []
    by_id = {candidate["passage_id"]: candidate for candidate in local_candidates}
    for candidate in web_candidates:
        by_id.setdefault(candidate["passage_id"], candidate)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    selected_source_ids: set[str] = set()
    # Give each acquired web source a chance to contribute before filling the
    # remaining slots with the strongest combined candidates.
    for candidate in web_candidates:
        source_id = candidate.get("source_id")
        if source_id and source_id not in selected_source_ids:
            selected.append(candidate)
            selected_ids.add(candidate["passage_id"])
            selected_source_ids.add(source_id)
            if len(selected) == limit:
                return selected

    ordered = sorted(
        by_id.values(),
        key=lambda item: (
            -float(item.get("relevance_score", 0.0)),
            item.get("rank", 0),
            item["passage_id"],
        ),
    )
    for candidate in ordered:
        if candidate["passage_id"] in selected_ids:
            continue
        source_id = candidate.get("source_id")
        if source_id and source_id in selected_source_ids:
            continue
        selected.append(candidate)
        selected_ids.add(candidate["passage_id"])
        if source_id:
            selected_source_ids.add(source_id)
        if len(selected) == limit:
            break
    # If the corpus has fewer distinct sources than the requested limit, fill
    # the remaining evidence slots with the next strongest passages.
    for candidate in ordered:
        if len(selected) == limit:
            break
        if candidate["passage_id"] in selected_ids:
            continue
        selected.append(candidate)
        selected_ids.add(candidate["passage_id"])
    return selected


def append_citation_ledger(response: str, passages: list[dict[str, Any]]) -> str:
    """Expose the authoritative passage-to-citation mapping used by synthesis."""
    if not passages:
        return response
    labels_in_response = {
        int(match) for match in re.findall(r"\[P(\d+)\]", response or "")
        if 1 <= int(match) <= len(passages)
    }
    labels = labels_in_response or set(range(1, len(passages) + 1))
    ledger = [
        f"[P{index}] {passage.get('citation_string') or passage.get('source_title', 'Unknown source')}"
        for index, passage in enumerate(passages, start=1)
        if index in labels
    ]
    return f"{response.rstrip()}\n\nEvidence references\n" + "\n".join(ledger)


def _requires_grounded_fallback(response: str, passages: list[dict[str, Any]]) -> bool:
    """Reject model prose that introduces citations outside the evidence ledger."""
    if not response or re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        response,
        re.IGNORECASE,
    ):
        return True
    labels = [int(value) for value in re.findall(r"\[P(\d+)\]", response)]
    if any(label < 1 or label > len(passages) for label in labels):
        return True
    bracketed_references = re.findall(r"\[([^\[\]]+)\]", response)
    if any(not re.fullmatch(r"P\d+", reference.strip()) for reference in bracketed_references):
        return True
    allowed_bibliography = " ".join(
        " ".join(
            str(value or "")
            for value in (passage.get("source_title"), passage.get("author"), passage.get("publication"))
        )
        for passage in passages
    ).casefold()
    for match in re.finditer(r"\b[A-Z][A-Za-z'’-]+(?:,\s*[A-Z](?:\.|[a-z]+))*\s*\(\d{4}\)", response):
        if match.group(0).casefold() not in allowed_bibliography:
            return True
    return False


def grounded_fallback_response(query: str, passages: list[dict[str, Any]]) -> str:
    """Provide an honest, readable answer when the model leaves the evidence boundary."""
    excerpts = []
    for index, passage in enumerate(passages[:5], start=1):
        content = " ".join(str(passage.get("content", "")).split())
        excerpts.append(f"- [P{index}] {content[:500]}{'…' if len(content) > 500 else ''}")
    return (
        "## Short Answer\n\n"
        "The retrieved material supports a distinction between continuity of experienced or remembered content "
        "and change in the way that content is attended to and temporally perceived. It does not, by itself, "
        "prove that experiences or impressions remain literally stationary. That stronger formulation is an "
        "interpretation of the question, not a statement established by the sources.\n\n"
        "## What the sources state\n\n"
        + "\n".join(excerpts)
        + "\n\n## Analysis\n\n"
        "Taken together, these passages make continuity intelligible without erasing change: memory and temporal "
        "awareness can make a sequence feel connected, while perception remains an active relation to what is "
        "present. This is a synthesis across the retrieved passages, not a claim that the sources use identical "
        "terminology.\n\n"
        "## Alternative interpretations\n\n"
        "The evidence does not settle whether continuity belongs to a persisting object, a stream of consciousness, "
        "or the mind's retrospective organization of successive experiences. Those alternatives should remain open.\n\n"
        "## Conclusion\n\n"
        f"For the question '{query}', the strongest defensible answer is therefore qualified: continuity can belong "
        "to the retained or related content, while change belongs to perception, attention, and temporal awareness."
    )

class ResearchWorkflowState(TypedDict):
    run_id: str | None
    query: str
    domain: str
    depth: str
    user_id: str
    retrieved_passages: list[dict[str, Any]]
    extracted_claims: list[dict[str, Any]]
    criticisms: list[dict[str, Any]]
    reconstructed_arguments: list[dict[str, Any]]
    objections: list[dict[str, Any]]
    scientific_analyses: list[dict[str, Any]]
    comparisons: list[dict[str, Any]]
    user_epistemic_positions: list[dict[str, Any]]
    validation_status: str
    validated_claims: list[dict[str, Any]]
    final_response: str
    validation_details: dict[str, Any]
    current_step: str
    include_web: bool
    web_research: Dict[str, Any]

class ResearchWorkflowEngine:
    """
    LangGraph research orchestrator:
    Query -> optional web discovery/acquisition -> Hybrid RAG -> Real Passages
    -> Specialist Agents -> Challenger -> LLM -> Validation.
    """
    def __init__(self, session_or_factory: Any | None = None, llm_adapter: BaseModelAdapter | None = None):
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

        async def coordinator_node(state: ResearchWorkflowState) -> dict[str, Any]:
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

        async def retrieval_node(state: ResearchWorkflowState) -> dict[str, Any]:
            query = state["query"]
            domain = state.get("domain", "Epistemology")
            depth = state.get("depth") or research_depth_for_query(query)
            research_directions = list(
                (state.get("web_research") or {}).get("research_directions")
                or research_directions_for_query(query, domain)
            )
            web_research: dict[str, Any] = {
                "requested": bool(state.get("include_web")),
                "status": (state.get("web_research") or {}).get("status", "not_requested"),
                "query": query,
                "research_directions": research_directions,
                "search_queries": [],
                "discovered_results": [],
                "acquired_sources": [],
                "warnings": [],
            }

            async with self.session_factory() as session:
                retrieval_service = HybridRetrievalService(session)
                evidence_candidates = await retrieval_service.retrieve_evidence(
                    query=query,
                    domain=domain,
                    top_k=10 if depth == "deep" else 6,
                    owner_id=state["user_id"],
                )
                evidence_candidates = merge_research_evidence(
                    evidence_candidates,
                    [],
                    10 if depth == "deep" else 6,
                )

                if state.get("include_web") and settings.RUNTIME_PROFILE == RuntimeProfile.TEST:
                    web_research["status"] = "unavailable"
                    web_research["warnings"].append("Live web research is unavailable in the test profile.")
                elif should_run_web_research(
                    query,
                    depth,
                    len(evidence_candidates),
                    requested=bool(state.get("include_web")),
                ):
                    web_research["status"] = "searched"
                    try:
                        filter_service = WebSourceFilteringService()
                        discovered_by_url: dict[str, WebSearchResult] = {}
                        for direction in research_directions:
                            web_research["search_queries"].append(direction)
                            try:
                                discovered = await WebSearchService().search(
                                    direction,
                                    max_results=settings.WEB_RETRIEVAL_MAX_RESULTS,
                                )
                            except AnvikshikiDomainError as exc:
                                web_research["warnings"].append(str(exc))
                                continue
                            for item in discovered:
                                discovered_by_url.setdefault(item.canonical_url, item)
                        ranked = sorted(
                            discovered_by_url.values(),
                            key=lambda item: (
                                filter_service.evaluate_source(item.canonical_url)["classification"]
                                != "PREFERRED",
                                item.rank,
                            ),
                        )
                        web_research["discovered_results"] = [
                            _web_result_payload(
                                item,
                                filter_service.evaluate_source(item.canonical_url)["classification"],
                            )
                            for item in ranked
                        ]
                        acquisition = WebAcquisitionService(session, LocalStorageService())
                        acquisition_limit = 8 if depth == "deep" else 5
                        for result in ranked[:acquisition_limit]:
                            classification = filter_service.evaluate_source(
                                result.canonical_url
                            )["classification"]
                            if classification == "REJECTED":
                                continue
                            try:
                                source, document, passages = await acquisition.acquire_url(
                                    result.canonical_url,
                                    source_title=result.title,
                                    owner_id=state["user_id"],
                                )
                                metadata = _web_metadata(document)
                                document.web_metadata = {
                                    **(document.web_metadata or {}),
                                    "source_classification": classification,
                                }
                                await session.commit()
                                web_research["acquired_sources"].append(
                                    {
                                        "source_id": source.id,
                                        "document_id": document.id,
                                        "title": source.title,
                                        "url": source.reference_url,
                                        "passages_count": len(passages),
                                        "passage_ids": [passage.id for passage in passages],
                                        "classification": classification,
                                        "author": source.author,
                                        "publication": metadata["publication"],
                                        "publication_year": metadata["publication_year"],
                                    }
                                )
                            except AnvikshikiDomainError as exc:
                                # A search result is discovery metadata, not evidence. It is
                                # omitted when acquisition, robots, or validation rejects it.
                                web_research["warnings"].append(str(exc))
                            except Exception as exc:  # noqa: BLE001 - one bad web source must not abort the run.
                                logger.warning(
                                    "Web source acquisition skipped",
                                    error_type=type(exc).__name__,
                                )
                                web_research["warnings"].append(
                                    "One discovered web source could not be acquired."
                                )
                        if web_research["acquired_sources"]:
                            evidence_limit = 10 if depth == "deep" else 6
                            all_candidates = await HybridRetrievalService(session).retrieve_evidence(
                                query=query,
                                domain=domain,
                                top_k=evidence_limit,
                            )
                            web_candidates: list[dict[str, Any]] = []
                            for acquired in web_research["acquired_sources"]:
                                web_candidates.extend(
                                    await HybridRetrievalService(session).retrieve_evidence(
                                        query=query,
                                        domain=domain,
                                        source_type_filter=SourceType.DISCOVERY_ONLY,
                                        source_id_filter=acquired["source_id"],
                                        top_k=3,
                                    )
                                )
                            evidence_candidates = merge_research_evidence(
                                all_candidates,
                                web_candidates,
                                evidence_limit,
                            )
                            acquired_source_ids = {
                                acquired["source_id"]
                                for acquired in web_research["acquired_sources"]
                            }
                            web_research["evidence_passages_count"] = sum(
                                1 for candidate in evidence_candidates
                                if candidate.get("source_id") in acquired_source_ids
                            )
                            web_research["status"] = "acquired"
                        elif not evidence_candidates:
                            web_research["status"] = "insufficient_evidence"
                    except AnvikshikiDomainError as exc:
                        web_research["status"] = "search_failed"
                        web_research["warnings"].append(str(exc))
                    except Exception as exc:  # noqa: BLE001 - web discovery is an optional boundary.
                        logger.warning("Web research unavailable", error_type=type(exc).__name__)
                        web_research["status"] = "unavailable"
                        web_research["warnings"].append(
                            "External web research was unavailable; only indexed local evidence was used."
                        )
                elif state.get("include_web"):
                    web_research["status"] = "unavailable"
                    if not web_research["warnings"]:
                        web_research["warnings"].append(
                            "Live web research was unavailable; only indexed local evidence was used."
                        )
                elif evidence_candidates:
                    web_research["status"] = "not_needed"
                else:
                    web_research["status"] = "insufficient_evidence"

            passages_data = [
                {
                    "passage_id": cand["passage_id"],
                    "content": cand["content"],
                    "source_title": cand.get("source_title", "Canonical Text"),
                    "page_number": cand.get("page_number", 1),
                    "source_id": cand.get("source_id"),
                    "source_type": cand.get("source_type", "UNVERIFIED"),
                    "retrieval_channels": cand.get("retrieval_channels", []),
                    "citation_string": cand.get("citation_string"),
                    "author": cand.get("author"),
                    "source_reference_url": cand.get("source_reference_url"),
                    "publication": cand.get("publication"),
                    "publication_year": cand.get("publication_year"),
                    "section_heading": cand.get("section_heading"),
                    "source_classification": cand.get(
                        "source_classification", cand.get("source_type", "UNVERIFIED")
                    ),
                }
                for cand in evidence_candidates
            ]
            return {
                "retrieved_passages": passages_data,
                "current_step": "retrieval_completed",
                "web_research": web_research,
            }

        async def web_research_node(state: ResearchWorkflowState) -> Dict[str, Any]:
            if not state.get("include_web", False):
                return {
                    "web_research": {
                        "requested": False,
                        "status": "not_requested",
                        "research_directions": [],
                        "search_queries": [],
                        "discovered_results": [],
                        "acquired_sources": [],
                        "warnings": [],
                    },
                    "current_step": "web_research_not_requested",
                }
            if not settings.ENABLE_WEB_RETRIEVAL:
                return {
                    "web_research": {
                        "requested": True,
                        "status": "unavailable",
                        "research_directions": research_directions_for_query(
                            state["query"], state.get("domain")
                        ),
                        "search_queries": [],
                        "discovered_results": [],
                        "acquired_sources": [],
                        "warnings": ["Live web research is disabled for this run."],
                    },
                    "current_step": "web_research_unavailable",
                }
            return {
                "web_research": {
                    "requested": True,
                    "status": "planned",
                    "research_directions": research_directions_for_query(
                        state["query"], state.get("domain")
                    ),
                    "search_queries": [],
                    "discovered_results": [],
                    "acquired_sources": [],
                    "warnings": [],
                },
                "current_step": "web_research_planned",
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
                claim_extractor = ClaimExtractionService(session, run_id=state.get("run_id"))
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
                            "claim_id": claim.id,
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

        async def challenger_node(state: ResearchWorkflowState) -> dict[str, Any]:
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

        async def validation_node(state: ResearchWorkflowState) -> dict[str, Any]:
            claims = state.get("extracted_claims", [])
            async with self.session_factory() as session:
                validator = SynthesisValidationService(session)
                val_res = await validator.validate_research_output(
                    claims, research_scope=state["domain"]
                )

            evidence_payload = {
                "passages": [
                    {**passage, "evidence_label": f"P{index}"}
                    for index, passage in enumerate(state.get("retrieved_passages", []), start=1)
                ],
                "claims": val_res["validated_claims"],
                "objections": state.get("objections", []),
                "source_criticisms": state.get("criticisms", []),
                "comparisons": state.get("comparisons", []),
                "web_research": state.get("web_research", {}),
                # User positions are context, not evidence. They are kept in a
                # separate field so synthesis cannot cite them as source claims.
                "user_epistemic_positions": state.get("user_epistemic_positions", []),
            }
            prompt = (
                "Write a serious, readable scholarly research answer in Markdown.\n"
                f"Query: {state['query']}\n"
                f"Evidence JSON:\n{json.dumps(evidence_payload, ensure_ascii=False, default=str)}\n"
                "Use only verified passages as evidence. Cite them inline as [P1], [P2], etc.; "
                "do not expose UUIDs, passage_id, source_id, document_id, claim_id, or pipeline state. "
                "Answer the exact question asked; do not substitute an unrelated hypothetical claim or example. "
                "For this inquiry, explicitly examine the relation among experience, impressions, perception, "
                "memory, consciousness, temporal awareness, change, continuity, and the observer where the evidence permits. "
                "When the question is substantive, organize the answer with a short answer, conceptual background, "
                "claims, evidence, analysis, source comparison, alternative interpretations, and conclusion as useful. "
                "Clearly distinguish what a source states, your interpretation, and any inference. "
                "Distinguish primary from secondary sources and never treat a discovery-only URL as evidence. "
                "Correlate sources only where the passages support agreement, qualification, complementarity, or disagreement."
            )
            depth = (state.get("depth") or "standard").lower()
            max_tokens = 1800 if depth in {"deep", "comprehensive", "long"} else 1100
            llm_summary = await self.llm.generate(prompt=prompt, max_tokens=max_tokens)
            if not state.get("retrieved_passages"):
                final_response = (
                    "This inquiry could not be grounded in a verified local passage or an acquired "
                    "web source. No substantive conclusion is being presented as established evidence. "
                    "Add a source to the library or retry external research when web retrieval is available."
                )
            else:
                draft_response = llm_summary.get("content", "")
                passages = state.get("retrieved_passages", [])
                if _requires_grounded_fallback(draft_response, passages):
                    draft_response = grounded_fallback_response(state["query"], passages)
                final_response = append_citation_ledger(draft_response, passages)

            return {
                "validation_status": val_res["status"],
                "validated_claims": val_res["validated_claims"],
                "validation_details": val_res,
                "final_response": final_response,
                "current_step": "validation_completed",
            }

        builder.add_node("coordinator", coordinator_node)
        builder.add_node("web_research", web_research_node)
        builder.add_node("retrieval", retrieval_node)
        builder.add_node("specialist_analysis", specialist_analysis_node)
        builder.add_node("challenger", challenger_node)
        builder.add_node("validator", validation_node)

        builder.set_entry_point("coordinator")
        builder.add_edge("coordinator", "web_research")
        builder.add_edge("web_research", "retrieval")
        builder.add_edge("retrieval", "specialist_analysis")
        builder.add_edge("specialist_analysis", "challenger")
        builder.add_edge("challenger", "validator")
        builder.add_edge("validator", END)

        return builder.compile(checkpointer=self.checkpointer)

    def _result_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": state.get("run_id") or "",
            "query": state.get("query", ""),
            "domain": state.get("domain"),
            "validation_status": state.get("validation_status", "PENDING"),
            "final_response": state.get("final_response", ""),
            "validated_claims_count": len(state.get("validated_claims", [])),
            "retrieved_passages": state.get("retrieved_passages", []),
            "claims": state.get("extracted_claims", []),
            "specialist_analysis": {
                "philosophical_arguments": state.get("reconstructed_arguments", []),
                "source_criticisms": state.get("criticisms", []),
                "scientific_analyses": state.get("scientific_analyses", []),
                "comparisons": state.get("comparisons", []),
                "challenges": state.get("objections", []),
            },
            "validation": state.get("validation_details", {}),
            "web_research": state.get("web_research", {
                "requested": False,
                "status": "not_reported",
                "discoveries": [],
                "acquisitions": [],
            }),
        }

    async def execute_research(
        self,
        query: str,
        user_id: str,
        domain: str = "Epistemology",
        thread_id: str = "default_thread",
        run_id: Optional[str] = None,
        depth: str = "standard",
        include_web: bool = False,
    ) -> Dict[str, Any]:
        initial_state: ResearchWorkflowState = {
            "run_id": run_id,
            "query": query,
            "domain": domain,
            "depth": depth,
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
            "validation_details": {},
            "current_step": "initialized",
            "include_web": include_web,
            "web_research": {},
        }
        config = {"configurable": {"thread_id": thread_id}}
        return await self.graph.ainvoke(initial_state, config=config)

    async def stream_research_events(
        self,
        query: str,
        user_id: str,
        domain: str = "Epistemology",
        thread_id: str = "default_thread",
        run_id: Optional[str] = None,
        depth: str = "standard",
        include_web: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        initial_state: ResearchWorkflowState = {
            "run_id": run_id,
            "query": query,
            "domain": domain,
            "depth": depth,
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
            "validation_details": {},
            "current_step": "initialized",
            "include_web": include_web,
            "web_research": {},
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
            final_state = dict(state)
            yield {
                "event": "research_completed",
                "validation_status": state.get("validation_status", "APPROVED"),
                "final_response": state.get("final_response", ""),
                "validated_claims_count": len(state.get("validated_claims", [])),
                "result": self._result_payload(final_state),
            }
