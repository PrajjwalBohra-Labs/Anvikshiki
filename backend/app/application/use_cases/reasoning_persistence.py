"""Persistence boundary for inquiry-local reasoning artifacts.

The workflow may keep its working state in LangGraph, but completed artifacts
are written as typed run-scoped records here.  This prevents a generated
answer or user memory from silently becoming durable source knowledge.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.models.enums import ReasoningNodeType, ReasoningRelationType
from backend.app.infrastructure.database.models import (
    InferenceModel,
    InsightModel,
    ReasoningChallengeModel,
    ReasoningEdgeModel,
    ReasoningInterpretationModel,
    ReasoningNodeModel,
    ReasoningRelationshipModel,
    ResearchDirectionModel,
    ResearchQuestionModel,
    ResearchRunModel,
    SourcePositionModel,
    SynthesisModel,
)


def _bounded_confidence(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


async def persist_reasoning_artifacts(
    session: AsyncSession,
    run: ResearchRunModel,
    question: ResearchQuestionModel,
    result: dict[str, Any],
) -> None:
    """Persist a completed reasoning record once, transactionally.

    The function is idempotent for a run. It deliberately stores source
    positions and cross-source relationships separately from claims/evidence.
    """
    existing = await session.scalar(
        select(ReasoningInterpretationModel.id)
        .where(ReasoningInterpretationModel.run_id == run.id)
        .limit(1)
    )
    if existing:
        return

    understanding = result.get("reasoning", {}).get("question_understanding", {})
    plan = _list(result.get("reasoning", {}).get("research_plan"))
    positions = _list(result.get("reasoning", {}).get("source_positions"))
    relationships = _list(result.get("reasoning", {}).get("relationships"))
    chains = result.get("reasoning", {}).get("chains", [])
    if not isinstance(chains, list):
        chains = []

    concepts = _list(understanding.get("key_concepts")) or _list(understanding.get("concepts"))
    interpretations_data = _list(understanding.get("interpretations"))
    answer_strategy = understanding.get("answer_strategy") if isinstance(understanding.get("answer_strategy"), dict) else {}
    intellectual_tasks = _list(understanding.get("intellectual_tasks"))
    intellectual_tasks.extend(
        str(item) for item in _list(answer_strategy.get("must_address"))
        if str(item) not in intellectual_tasks
    )

    question.normalized_question = understanding.get("literal_question")
    question.interpreted_question = understanding.get("underlying_question") or understanding.get("central_problem")
    question.primary_intent = understanding.get("answer_type") or understanding.get("inquiry_mode")
    question.secondary_intents = _list(understanding.get("secondary_intents")) or [
        item.get("reading") for item in interpretations_data if isinstance(item, dict) and item.get("reading")
    ]
    question.intellectual_tasks = intellectual_tasks
    question.concepts = concepts
    question.traditions = _list(understanding.get("traditions"))
    question.schools = _list(understanding.get("schools"))
    question.disciplines = _list(understanding.get("disciplines"))
    question.assumptions = _list(understanding.get("assumptions"))
    question.presuppositions = _list(understanding.get("presuppositions"))
    question.ambiguities = _list(understanding.get("ambiguities")) or [
        item for item in interpretations_data
        if isinstance(item, dict) and item.get("material_difference")
    ]
    question.requested_depth = understanding.get("required_depth") or answer_strategy.get("depth")
    question.expected_answer_form = understanding.get("answer_type") or understanding.get("inquiry_mode")
    question.research_requirement = "; ".join(item.get("purpose", "") for item in plan if isinstance(item, dict))
    question.evidence_requirement = "; ".join(item.get("expected_evidence", "") for item in plan if isinstance(item, dict))
    question.interpretation_confidence = _bounded_confidence(understanding.get("interpretation_confidence"), 0.6)
    question.alternative_interpretations = interpretations_data

    interpretations = [
        ReasoningInterpretationModel(
            run_id=run.id,
            formulation=understanding.get("underlying_question") or understanding.get("central_problem") or run.query,
            interpretation_type="PRIMARY",
            assumptions=_list(understanding.get("assumptions")),
            concepts=concepts,
            implications=[understanding.get("central_problem", "")],
            confidence=question.interpretation_confidence or 0.0,
            epistemic_state="INTERPRETIVE",
            unresolved_issues=[
                item.get("reading", "") for item in interpretations_data
                if isinstance(item, dict) and item.get("material_difference")
            ],
        )
    ]
    for alternative in interpretations_data:
        if isinstance(alternative, dict):
            interpretations.append(
                ReasoningInterpretationModel(
                    run_id=run.id,
                    formulation=str(alternative.get("reading") or alternative.get("formulation") or run.query),
                    interpretation_type="ALTERNATIVE",
                    assumptions=[str(alternative.get("material_difference") or "")],
                    concepts=_list(alternative.get("concepts")) or concepts,
                    confidence=_bounded_confidence(alternative.get("confidence"), 0.45),
                    epistemic_state="UNRESOLVED",
                    unresolved_issues=_list(alternative.get("unresolved_questions")),
                )
            )
    session.add_all(interpretations)

    direction_models = []
    for index, item in enumerate(plan):
        if not isinstance(item, dict):
            continue
        direction_models.append(
            ResearchDirectionModel(
                run_id=run.id,
                research_question=str(item.get("question", run.query)),
                purpose=str(item.get("purpose", "")),
                expected_evidence=str(item.get("expected_evidence", "")),
                search_strategy=_list(item.get("search_terms")),
                traditions=_list(item.get("disciplines_traditions")) or _list(item.get("source_preferences")),
                concepts=concepts,
                completion_criteria=["Evidence is acquired and traceable to a passage."],
                evidence_gaps=(
                    _list(result.get("reasoning", {}).get("gaps"))
                    + _list(result.get("reasoning", {}).get("evidence_assessment", {}).get("missing_requirements"))
                ),
                priority=index,
                status="PLANNED",
            )
        )
    session.add_all(direction_models)

    position_models = []
    for item in positions:
        if not isinstance(item, dict):
            continue
        position_models.append(
            SourcePositionModel(
                run_id=run.id,
                source_id=item.get("source_id"),
                source_title=str(item.get("source_title", "Unknown source")),
                position_type="DIRECT_POSITION" if item.get("statement_status") == "direct_statement" else "RECONSTRUCTED_POSITION",
                central_thesis=str(item.get("central_position", "No source-level statement was extracted.")),
                propositions=_list(item.get("direct_statements")),
                arguments=[str(item.get("argument", ""))],
                evidence_passage_ids=_list(item.get("evidence_passage_ids")),
                assumptions=_list(item.get("assumptions")),
                qualifications=_list(item.get("qualifications")),
                limitations=_list(item.get("limitations")),
                interpretive_uncertainties=[str(item.get("interpretation_boundary", ""))],
                confidence=0.65 if item.get("direct_statements") else 0.25,
                epistemic_state="INTERPRETIVE" if item.get("direct_statements") else "INSUFFICIENT_EVIDENCE",
            )
        )
    session.add_all(position_models)

    relationship_models = []
    for item in relationships:
        if not isinstance(item, dict):
            continue
        relation = str(item.get("relation", "unresolved")).upper()
        relation = {"COMPLEMENTS": "COMPLEMENTS", "CONTRADICTS": "CONTRADICTS", "QUALIFIES": "QUALIFIES"}.get(relation, "LEAVES_UNRESOLVED")
        relationship_models.append(
            ReasoningRelationshipModel(
                run_id=run.id,
                source_a_id=next((p.get("source_id") for p in positions if p.get("source_title") == item.get("source_a")), None),
                source_b_id=next((p.get("source_id") for p in positions if p.get("source_title") == item.get("source_b")), None),
                source_a_label=str(item.get("source_a", "Unknown source")),
                source_b_label=str(item.get("source_b", "Unknown source")),
                relationship_type=relation,
                classification=str(item.get("relation", "unresolved")).upper(),
                justification=str(item.get("explanation", "")),
                supporting_passage_ids=_list(item.get("passage_ids"))
                or sorted({
                    passage_id
                    for position in positions
                    if position.get("source_title") in {item.get("source_a"), item.get("source_b")}
                    for passage_id in _list(position.get("evidence_passage_ids"))
                }),
                confidence=_bounded_confidence(item.get("confidence")),
                uncertainty="Lexical overlap does not by itself establish agreement or contradiction.",
            )
        )
    session.add_all(relationship_models)

    inference_models = []
    synthesis_models = []
    claim_ids = [str(item.get("claim_id")) for item in _list(result.get("claims")) if item.get("claim_id")]
    for chain in chains:
        if not isinstance(chain, dict):
            continue
        chain_type = str(chain.get("type", "")).upper()
        if chain_type == "SYNTHESIS":
            synthesis_models.append(SynthesisModel(
                run_id=run.id,
                statement=str(chain.get("claim", run.query)),
                contributing_claim_ids=claim_ids,
                contributing_source_position_ids=[],
                contributing_relationship_ids=[],
                reasoning_basis=str(chain.get("analysis", "")),
                unresolved_tensions=_list(result.get("reasoning", {}).get("gaps")),
                alternative_synthesis=_list(result.get("reasoning", {}).get("alternatives")),
                limitations=[str(chain.get("conclusion", ""))],
                confidence=_bounded_confidence(chain.get("confidence")),
                epistemic_state="INFERENTIAL",
            ))
        else:
            inference_models.append(InferenceModel(
                run_id=run.id,
                conclusion=str(chain.get("conclusion", "")),
                premise_claim_ids=claim_ids if chain.get("inference_status") != "direct_statement" else [],
                evidence_ids=_list(chain.get("evidence")),
                reasoning_basis=str(chain.get("analysis", "")),
                alternatives=_list(result.get("reasoning", {}).get("alternatives")),
                confidence=_bounded_confidence(chain.get("confidence")),
                epistemic_state="INFERENTIAL" if chain.get("inference_status") != "direct_statement" else "WELL_SUPPORTED",
            ))
    session.add_all(inference_models + synthesis_models)

    challenge_models = []
    for index, challenge in enumerate(_list(result.get("specialist_analysis", {}).get("challenges"))):
        if not isinstance(challenge, dict):
            continue
        challenge_models.append(ReasoningChallengeModel(
            run_id=run.id,
            target_type="CLAIM",
            target_id=challenge.get("target_claim_id") or (claim_ids[0] if claim_ids else None),
            issue_type=str(challenge.get("type", "claim_challenge")),
            statement=str(challenge.get("objection", "")),
            severity="MATERIAL" if index == 0 else "MODERATE",
            resolution="UNRESOLVED",
            confidence=_bounded_confidence(challenge.get("confidence")),
        ))
    session.add_all(challenge_models)

    await session.flush()
    for synthesis in synthesis_models:
        synthesis.contributing_source_position_ids = [item.id for item in position_models]
        synthesis.contributing_relationship_ids = [item.id for item in relationship_models]
    await session.flush()
    await _persist_graph(
        session,
        run,
        question,
        direction_models,
        interpretations,
        position_models,
        relationship_models,
        result=result,
        inference_models=inference_models,
        synthesis_models=synthesis_models,
        challenge_models=challenge_models,
    )
    await session.commit()


async def _persist_graph(
    session: AsyncSession,
    run: ResearchRunModel,
    question: ResearchQuestionModel,
    directions: list[Any],
    interpretations: list[Any],
    positions: list[Any],
    relationships: list[Any],
    *,
    result: dict[str, Any],
    inference_models: list[Any],
    synthesis_models: list[Any],
    challenge_models: list[Any],
) -> None:
    nodes: list[ReasoningNodeModel] = []
    node_by_key: dict[tuple[ReasoningNodeType, str], ReasoningNodeModel] = {}

    def add(node_type: ReasoningNodeType, entity_id: str, label: str, metadata: dict[str, Any] | None = None) -> ReasoningNodeModel:
        key = (node_type, str(entity_id))
        if key in node_by_key:
            return node_by_key[key]
        node = ReasoningNodeModel(run_id=run.id, node_type=node_type, entity_id=entity_id, label=label, metadata_payload=metadata or {})
        nodes.append(node)
        node_by_key[key] = node
        return node

    question_node = add(ReasoningNodeType.QUESTION, question.id, question.main_question)
    problem_node = add(ReasoningNodeType.PROBLEM, question.id, str(question.interpreted_question or question.main_question))
    direction_nodes = [add(ReasoningNodeType.RESEARCH_DIRECTION, item.id, item.research_question) for item in directions]
    interpretation_nodes = [add(ReasoningNodeType.INTERPRETATION, item.id, item.formulation) for item in interpretations]
    position_nodes = [add(ReasoningNodeType.POSITION, item.id, item.source_title) for item in positions]
    source_nodes = []
    for item in _list(result.get("retrieved_passages")):
        source_id = item.get("source_id")
        if source_id:
            source_nodes.append(add(ReasoningNodeType.SOURCE, str(source_id), str(item.get("source_title", "Source"))))
    passage_nodes = [
        add(ReasoningNodeType.PASSAGE, str(item.get("passage_id")), str(item.get("source_title", "Passage")), {"source_id": item.get("source_id")})
        for item in _list(result.get("retrieved_passages"))
        if item.get("passage_id")
    ]
    claims = [item for item in _list(result.get("claims")) if item.get("claim_id")]
    claim_nodes = [add(ReasoningNodeType.CLAIM, str(item["claim_id"]), str(item.get("statement", "Claim"))) for item in claims]
    evidence_nodes = [
        add(ReasoningNodeType.EVIDENCE, str(item.get("passage_id")), f"Evidence for {item.get('source_title', 'passage')}")
        for item in claims
        if item.get("passage_id")
    ]
    argument_nodes = [
        add(ReasoningNodeType.ARGUMENT, str(item.get("argument_id")), str(item.get("title", "Argument")))
        for item in _list(result.get("specialist_analysis", {}).get("philosophical_arguments"))
        if item.get("argument_id")
    ]
    inference_nodes = [add(ReasoningNodeType.INFERENCE, item.id, item.conclusion) for item in inference_models]
    synthesis_nodes = [add(ReasoningNodeType.SYNTHESIS, item.id, item.statement) for item in synthesis_models]
    challenge_nodes = [add(ReasoningNodeType.COUNTERARGUMENT, item.id, item.statement) for item in challenge_models]
    session.add_all(nodes)
    await session.flush()
    edges: list[ReasoningEdgeModel] = []
    edge_keys: set[tuple[str, str, ReasoningRelationType]] = set()
    def connect(left: ReasoningNodeModel, right: ReasoningNodeModel, relation: ReasoningRelationType, confidence: float = 0.8, justification: str | None = None) -> None:
        if left.id == right.id:
            return
        key = (str(left.id), str(right.id), relation)
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append(ReasoningEdgeModel(run_id=run.id, from_node_id=left.id, to_node_id=right.id, relationship_type=relation, confidence=confidence, justification=justification))

    connect(question_node, problem_node, ReasoningRelationType.REFINES, 1.0)
    for node in direction_nodes + interpretation_nodes:
        connect(question_node, node, ReasoningRelationType.CONTAINS, 1.0)
    for node in position_nodes:
        connect(question_node, node, ReasoningRelationType.INVOLVES)
    for node in direction_nodes:
        connect(node, question_node, ReasoningRelationType.ASKS)
    position_by_source = {node.label: node for node in position_nodes}
    source_by_id = {node.entity_id: node for node in source_nodes}
    passage_by_id = {node.entity_id: node for node in passage_nodes}
    claim_by_id = {node.entity_id: node for node in claim_nodes}
    for source_node in source_nodes:
        for passage in _list(result.get("retrieved_passages")):
            if str(passage.get("source_id")) == source_node.entity_id and passage.get("passage_id") in passage_by_id:
                connect(source_node, passage_by_id[str(passage["passage_id"])], ReasoningRelationType.CONTAINS)
    for item in _list(result.get("retrieved_passages")):
        if item.get("passage_id") in passage_by_id and item.get("source_id") in source_by_id:
            connect(passage_by_id[str(item["passage_id"])], source_by_id[str(item["source_id"])], ReasoningRelationType.APPEARS_IN)
    for claim in claims:
        if claim.get("passage_id") in passage_by_id:
            connect(passage_by_id[str(claim["passage_id"])], claim_by_id[str(claim["claim_id"])], ReasoningRelationType.SUPPORTS)
    for position in positions:
        source_node = source_by_id.get(str(position.source_id))
        position_node = position_by_source.get(position.source_title)
        if source_node and position_node:
            connect(position_node, source_node, ReasoningRelationType.BELONGS_TO)
    for index, item in enumerate(relationships):
        left = position_by_source.get(str(item.source_a_label))
        right = position_by_source.get(str(item.source_b_label))
        if left is None or right is None:
            continue
        relation = str(item.relationship_type).upper()
        edge_type = getattr(ReasoningRelationType, relation, ReasoningRelationType.LEAVES_UNRESOLVED)
        connect(left, right, edge_type, item.confidence, item.justification)
    for inference_node, inference in zip(inference_nodes, inference_models):
        for claim_id in _list(inference.premise_claim_ids):
            if str(claim_id) in claim_by_id:
                connect(inference_node, claim_by_id[str(claim_id)], ReasoningRelationType.INFERRED_FROM)
    for synthesis_node, synthesis in zip(synthesis_nodes, synthesis_models):
        for claim_id in _list(synthesis.contributing_claim_ids):
            if str(claim_id) in claim_by_id:
                connect(synthesis_node, claim_by_id[str(claim_id)], ReasoningRelationType.SYNTHESIZES)
        for position_id in _list(synthesis.contributing_source_position_ids):
            node = next((item for item in position_nodes if item.entity_id == str(position_id)), None)
            if node:
                connect(synthesis_node, node, ReasoningRelationType.SYNTHESIZES)
    for challenge_node, challenge in zip(challenge_nodes, challenge_models):
        target = claim_by_id.get(str(challenge.target_id))
        if target:
            connect(challenge_node, target, ReasoningRelationType.CHALLENGES)
    session.add_all(edges)


async def get_reasoning_artifacts(session: AsyncSession, run_id: str) -> dict[str, Any]:
    """Return persisted, auditable artifacts for the authenticated run."""
    queries = {
        "interpretations": select(ReasoningInterpretationModel).where(ReasoningInterpretationModel.run_id == run_id),
        "research_directions": select(ResearchDirectionModel).where(ResearchDirectionModel.run_id == run_id),
        "source_positions": select(SourcePositionModel).where(SourcePositionModel.run_id == run_id),
        "relationships": select(ReasoningRelationshipModel).where(ReasoningRelationshipModel.run_id == run_id),
        "inferences": select(InferenceModel).where(InferenceModel.run_id == run_id),
        "syntheses": select(SynthesisModel).where(SynthesisModel.run_id == run_id),
        "insights": select(InsightModel).where(InsightModel.run_id == run_id),
        "challenges": select(ReasoningChallengeModel).where(ReasoningChallengeModel.run_id == run_id),
        "nodes": select(ReasoningNodeModel).where(ReasoningNodeModel.run_id == run_id),
        "edges": select(ReasoningEdgeModel).where(ReasoningEdgeModel.run_id == run_id),
    }
    output: dict[str, Any] = {}
    for key, query in queries.items():
        rows = (await session.execute(query)).scalars().all()
        output[key] = [
            {column.name: getattr(row, column.name) for column in row.__table__.columns}
            for row in rows
        ]
    return output
