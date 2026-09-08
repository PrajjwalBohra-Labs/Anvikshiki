import json

import pytest
from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter
from backend.app.infrastructure.database.models import DocumentModel, PassageModel, SourceModel
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine


class AdaptiveWorkflowLLM(BaseModelAdapter):
    def __init__(self, model_name: str = "adaptive-test"):
        super().__init__(model_name=model_name)
        self.relevant_passage_id = "p1"
        self.unrelated_passage_id = "p2"

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 512, temperature: float = 0.7):
        if "Analyze this inquiry before any research" in prompt:
            payload = {
                "literal_question": "Why do communities treat a river as a legal person?",
                "central_problem": "The relation between legal status and communal practice",
                "requested_task": "explain why the status is adopted",
                "inquiry_mode": "institutional and causal explanation",
                "concepts": [
                    {"label": "legal personhood", "role": "institutional status"},
                    {"label": "communal practice", "role": "social mechanism"},
                ],
                "relationships": [{"source": "legal personhood", "relation": "shapes", "target": "communal practice"}],
                "research_requirements": [{
                    "requirement_id": "mechanism",
                    "question_component": "why the status is adopted",
                    "evidence_needed": "legal history and community accounts",
                    "search_queries": ["river legal personhood adoption community reasons"],
                }],
            }
        elif "Judge whether each retrieved passage" in prompt:
            payload = {
                "evaluations": [
                    {
                        "passage_id": self.relevant_passage_id,
                        "relevance": "direct",
                        "supports_requirements": ["mechanism"],
                        "supported_proposition": "Recognition changed communal duties toward the river.",
                        "evidence_role": "direct evidence",
                        "use_for_synthesis": True,
                    },
                    {
                        "passage_id": self.unrelated_passage_id,
                        "relevance": "irrelevant",
                        "supports_requirements": [],
                        "evidence_role": "none",
                        "use_for_synthesis": False,
                    },
                ],
                "sufficiency": "partial",
                "satisfied_requirements": ["mechanism"],
                "missing_requirements": [],
            }
        elif "Reason over the relevant evidence" in prompt:
            payload = {
                "source_positions": [{
                    "source_id": "source-1",
                    "source_title": "River Law Study",
                    "position": "Legal recognition changes communal duties toward the river.",
                    "problem_addressed": "institutional adoption",
                    "reasoning_summary": "The passage links status to changed duties.",
                    "supporting_passage_ids": [self.relevant_passage_id],
                }],
                "relationships": [],
                "reasoning_chains": [{
                    "question_component": "why the status is adopted",
                    "claim": "Recognition changes communal duties toward the river.",
                    "evidence_passage_ids": [self.relevant_passage_id],
                    "analysis": "The passage supports a legal mechanism, not every possible social cause.",
                    "conclusion": "The evidence establishes a change in duties.",
                    "confidence": 0.8,
                    "inference_status": "direct",
                }],
                "gaps": [],
                "alternatives": [],
            }
        elif "Identify the most important limitations" in prompt:
            payload = {"objections": [{"objection": "The passage does not establish every reason a community adopted the status.", "type": "scope", "confidence": 0.8}]}
        elif "Audit this proposed answer" in prompt:
            payload = {
                "addresses_question": True,
                "covered_requirements": ["mechanism"],
                "uncovered_requirements": [],
                "evidence_alignment": [{"passage_id": self.relevant_passage_id, "supports": True, "reason": "The answer stays within the cited proposition."}],
                "irrelevant_or_unsupported_claims": [],
                "topic_drift": False,
                "sufficient_for_answer": True,
                "reason": "The answer addresses the question and is grounded in P1.",
            }
        else:
            return {"content": "The community adopts legal personhood because recognition changes communal duties toward the river. [P1]", "model": self.model_name}
        return {"content": json.dumps(payload), "model": self.model_name}

    async def stream_generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 512, temperature: float = 0.7):
        yield ""


@pytest.fixture
async def isolated_schema():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_adaptive_workflow_excludes_unrelated_substantive_evidence(monkeypatch, isolated_schema):
    async with AsyncSessionLocal() as session:
        source = SourceModel(title="River Law Study")
        unrelated_source = SourceModel(title="Memory Systems Study")
        session.add_all([source, unrelated_source])
        await session.flush()
        document = DocumentModel(source_id=source.id, checksum_sha256="adaptive-p1", mime_type="text/plain")
        unrelated_document = DocumentModel(source_id=unrelated_source.id, checksum_sha256="adaptive-p2", mime_type="text/plain")
        session.add_all([document, unrelated_document])
        await session.flush()
        passage = PassageModel(document_id=document.id, content="Legal recognition changed the community's duties toward the river.")
        unrelated = PassageModel(document_id=unrelated_document.id, content="Human memory depends on distributed neural processes.")
        session.add_all([passage, unrelated])
        await session.commit()

        async def retrieve(self, query, domain=None, source_type_filter=None, source_id_filter=None, top_k=5, owner_id=None):
            return [
                {"passage_id": "p1", "source_id": source.id, "source_title": source.title, "content": passage.content, "source_type": "PRIMARY", "rank": 1, "relevance_score": 1.0},
                {"passage_id": "p2", "source_id": unrelated_source.id, "source_title": unrelated_source.title, "content": unrelated.content, "source_type": "SCIENTIFIC", "rank": 2, "relevance_score": 0.9},
            ]

        # The workflow's provenance checks need real database passage IDs; map
        # the test labels to the persisted IDs while keeping model output labels stable.
        async def retrieve_with_ids(self, query, domain=None, source_type_filter=None, source_id_filter=None, top_k=5, owner_id=None):
            return [
                {"passage_id": passage.id, "source_id": source.id, "source_title": source.title, "content": passage.content, "source_type": "PRIMARY", "rank": 1, "relevance_score": 1.0},
                {"passage_id": unrelated.id, "source_id": unrelated_source.id, "source_title": unrelated_source.title, "content": unrelated.content, "source_type": "SCIENTIFIC", "rank": 2, "relevance_score": 0.9},
            ]

        monkeypatch.setattr("backend.app.application.orchestration.research_workflow.HybridRetrievalService.retrieve_evidence", retrieve_with_ids)
        llm = AdaptiveWorkflowLLM(model_name="adaptive-test")
        llm.relevant_passage_id = passage.id
        llm.unrelated_passage_id = unrelated.id
        result = await ResearchWorkflowEngine(session, llm_adapter=llm).execute_research(
            "Why do communities treat a river as a legal person?",
            "adaptive-user",
            domain="general",
            thread_id="adaptive-workflow",
            depth="standard",
        )

    assert result["validation_status"] == "APPROVED"
    assert [item["source_title"] for item in result["retrieved_passages"]] == ["River Law Study"]
    assert result["evidence_assessment"]["usable_passage_ids"] == [passage.id]
    assert result["semantic_audit"]["topic_drift"] is False
    assert "Memory Systems Study" not in result["final_response"]
