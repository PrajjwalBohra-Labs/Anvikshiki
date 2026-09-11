"""LLM-led inquiry analysis and evidence judgment.

The model is responsible for discovering the intellectual structure of an
inquiry.  This module only supplies the method, parses bounded JSON, and
removes claims that cannot be tied to real passages.  It intentionally has no
domain ontology, keyword map, or predetermined answer taxonomy.
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.app.application.use_cases.research_reasoning import is_substantive_passage


ADAPTIVE_SYSTEM_PROMPT = """You are Anvikshiki's adaptive intellectual research planner.

Treat each user question as a distinct inquiry. Discover its concepts,
relationships, assumptions, interpretations, research needs, evidence
standards, and answer strategy from the wording and context of that inquiry.
Do not apply a fixed philosophical ontology, keyword map, tradition list, or
answer template. Do not infer that a source is relevant merely because it
shares words with the question.

Return only valid JSON when a JSON response is requested. Do not include
private chain-of-thought. Return concise, auditable summaries of reasoning,
source claims, qualifications, and gaps instead.
"""


def _as_text(value: Any, default: str = "") -> str:
    return " ".join(str(value or default).split())


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0", ""}:
            return False
    return default


def _json_object(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content
    text = str(content or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.IGNORECASE | re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


async def generate_structured(llm: Any, prompt: str, max_tokens: int = 1600) -> dict[str, Any] | None:
    """Ask the configured model for bounded JSON without inventing fallback facts."""
    try:
        result = await llm.generate(
            prompt=prompt,
            system_prompt=ADAPTIVE_SYSTEM_PROMPT,
            max_tokens=max_tokens,
            temperature=0.15,
        )
    except Exception:  # noqa: BLE001 - unavailable semantic judgment must fail closed.
        return None
    return _json_object(result.get("content") if isinstance(result, dict) else result)


def question_analysis_prompt(query: str, domain: str | None, depth: str) -> str:
    return f"""Analyze this inquiry before any research.

Question:
{query}

User/application context:
- Declared domain: {domain or 'unspecified'}
- Requested depth: {depth}

Return one JSON object with exactly these top-level fields (arrays may be
empty):
{{
  "literal_question": "...",
  "central_problem": "...",
  "requested_task": "what the user needs answered",
  "inquiry_mode": "your own concise description, not a fixed enum",
  "subquestions": ["only material subquestions needed to answer the inquiry"],
  "explanatory_targets": ["what must be explained, interpreted, compared, or assessed"],
  "concepts": [{{"label":"...", "role":"...", "contextual_meaning":"..."}}],
  "relationships": [{{"source":"...", "relation":"...", "target":"...", "why_it_matters":"..."}}],
  "assumptions": [{{"assumption":"...", "materiality":"..."}}],
  "interpretations": [{{"reading":"...", "material_difference":"...", "confidence":0.0}}],
  "clarifications": [{{"ambiguity":"...", "why_material":"...", "working_interpretation":"..."}}],
  "intellectual_landscape": {{
    "knowledge_connections": ["only areas of knowledge the inquiry actually requires"],
    "perspectives_to_seek": ["relevant positions or competing explanations, without naming them unless justified"],
    "source_strategy": ["why primary, secondary, empirical, historical, or other source material is needed"]
  }},
  "tool_requests": [{{"capability":"existing backend capability that is materially needed", "purpose":"...", "supports_requirements":["requirement_id"]}}],
  "research_requirements": [{{
    "requirement_id":"stable short id",
    "question_component":"the exact part this serves",
    "why_needed":"...",
    "evidence_needed":"...",
    "source_preferences":["only source kinds justified by this question"],
    "search_queries":["focused query"],
    "sufficiency_test":"what would count as enough evidence",
    "required":true,
    "role":"direct evidence|context|interpretation|comparison|counterevidence|other"
  }}],
  "research_needed": true,
  "answer_strategy": {{"depth":"...", "order":["..."], "must_address":["..."], "omit":["..."]}}
}}

Only include subquestions, ambiguities, perspectives, connections, and
research requirements that materially affect this particular question. Do not
fill fields with generic philosophical categories. Do not name a tradition,
discipline, author, or explanatory factor merely because it could be related;
include it only when the inquiry itself makes it materially relevant.
"""


def fallback_question_analysis(query: str, domain: str | None, depth: str) -> dict[str, Any]:
    """Minimal non-semantic fallback; it never supplies concepts or theories."""
    normalized = _as_text(query)
    return {
        "literal_question": normalized,
        "central_problem": normalized,
        "requested_task": normalized,
        "inquiry_mode": "undetermined",
        "subquestions": [],
        "explanatory_targets": [normalized] if normalized else [],
        "concepts": [],
        "relationships": [],
        "assumptions": [],
        "interpretations": [],
        "clarifications": [],
        "intellectual_landscape": {
            "knowledge_connections": [],
            "perspectives_to_seek": [],
            "source_strategy": [],
        },
        "tool_requests": [],
        "research_requirements": [{
            "requirement_id": "question_scope",
            "question_component": normalized,
            "why_needed": "The question must be answered directly.",
            "evidence_needed": "Substantive evidence that addresses the question itself.",
            "source_preferences": [],
            "search_queries": [normalized] if normalized else [],
            "sufficiency_test": "At least one substantive source directly addresses the question.",
            "required": True,
        }],
        "research_needed": bool(normalized),
        "answer_strategy": {
            "depth": depth,
            "order": ["direct answer", "supporting evidence", "qualifications"],
            "must_address": [normalized] if normalized else [],
            "omit": [],
        },
        "domain_context": domain or "",
        "analysis_status": "fallback_unavailable",
    }


def normalize_question_analysis(raw: dict[str, Any] | None, query: str, domain: str | None, depth: str) -> dict[str, Any]:
    data = raw or fallback_question_analysis(query, domain, depth)
    normalized = fallback_question_analysis(query, domain, depth)
    normalized.update({
        "literal_question": _as_text(data.get("literal_question"), query),
        "central_problem": _as_text(data.get("central_problem"), query),
        "requested_task": _as_text(data.get("requested_task"), query),
        "inquiry_mode": _as_text(data.get("inquiry_mode"), "undetermined"),
        "research_needed": _as_bool(data.get("research_needed"), True),
        "answer_strategy": data.get("answer_strategy") if isinstance(data.get("answer_strategy"), dict) else normalized["answer_strategy"],
        "domain_context": domain or "",
        "analysis_status": "llm" if raw else "fallback_unavailable",
    })
    for key in (
        "subquestions",
        "explanatory_targets",
        "concepts",
        "relationships",
        "assumptions",
        "interpretations",
        "clarifications",
    ):
        normalized[key] = _as_list(data.get(key))[:24]
    landscape = data.get("intellectual_landscape")
    if isinstance(landscape, dict):
        normalized["intellectual_landscape"] = {
            key: [_as_text(value) for value in _as_list(landscape.get(key)) if _as_text(value)][:16]
            for key in ("knowledge_connections", "perspectives_to_seek", "source_strategy")
        }
    normalized["tool_requests"] = [
        {
            "capability": _as_text(item.get("capability")),
            "purpose": _as_text(item.get("purpose")),
            "supports_requirements": [_as_text(value) for value in _as_list(item.get("supports_requirements")) if _as_text(value)],
        }
        for item in _as_list(data.get("tool_requests"))
        if isinstance(item, dict) and _as_text(item.get("capability"))
    ][:12]

    requirements = []
    for index, item in enumerate(_as_list(data.get("research_requirements"))[:16], start=1):
        if not isinstance(item, dict):
            continue
        component = _as_text(item.get("question_component"))
        queries = [_as_text(query_item) for query_item in _as_list(item.get("search_queries")) if _as_text(query_item)]
        if not component and not queries:
            continue
        requirements.append({
            "requirement_id": _as_text(item.get("requirement_id"), f"requirement_{index}"),
            "question_component": component or query,
            "why_needed": _as_text(item.get("why_needed")),
            "evidence_needed": _as_text(item.get("evidence_needed")),
            "source_preferences": [_as_text(value) for value in _as_list(item.get("source_preferences")) if _as_text(value)],
            "search_queries": queries or [query],
            "sufficiency_test": _as_text(item.get("sufficiency_test")),
            "role": _as_text(item.get("role")),
            "required": _as_bool(item.get("required"), True),
        })
    normalized["research_requirements"] = requirements or normalized["research_requirements"]
    return normalized


def research_plan_from_analysis(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose the model's requirements as retrieval work, without adding topics."""
    plan = []
    for item in analysis.get("research_requirements", []):
        queries = [query for query in item.get("search_queries", []) if query]
        plan.append({
            "requirement_id": item.get("requirement_id"),
            "question": item.get("question_component"),
            "purpose": item.get("why_needed"),
            "search_terms": queries,
            "expected_evidence": item.get("evidence_needed"),
            "source_preferences": item.get("source_preferences", []),
            "sufficiency_test": item.get("sufficiency_test"),
            "role": item.get("role", ""),
            "required": item.get("required", True),
        })
    return plan


def inquiry_refinement_prompt(
    query: str,
    analysis: dict[str, Any],
    assessment: dict[str, Any],
    passages: list[dict[str, Any]],
) -> str:
    """Ask whether evidence materially changes the working inquiry model."""
    evidence = [
        {"passage_id": item.get("passage_id"), "source_title": item.get("source_title"), "content": item.get("content")}
        for item in passages
    ]
    return f"""Reconsider the working representation of this inquiry after reading the evidence.

Question:
{query}

Working inquiry representation:
{json.dumps(analysis, ensure_ascii=False)}

Evidence assessment:
{json.dumps(assessment, ensure_ascii=False, default=str)}

Relevant passages:
{json.dumps(evidence, ensure_ascii=False, default=str)}

Return JSON:
{{
  "changed": true,
  "revised_central_problem": "only if the evidence reveals a material refinement",
  "revised_requested_task": "only if the evidence changes what must be answered",
  "new_relationships":[{{"source":"...", "relation":"...", "target":"...", "why_it_matters":"...", "passage_ids":["exact ids"]}}],
  "changed_interpretations":[{{"reading":"...", "material_difference":"...", "confidence":0.0, "passage_ids":["exact ids"]}}],
  "research_implications":[{{
    "requirement_id":"existing id or a new id justified by the passages",
    "question_component":"material component of the original inquiry",
    "why_needed":"why this follows from the inquiry and evidence",
    "evidence_needed":"what is still needed",
    "search_queries":["focused query"],
    "sufficiency_test":"what would count as enough",
    "grounding_passage_ids":["exact ids for a new requirement"]
  }}],
  "synthesis_focus":["connections or distinctions that the final answer should consider"]
}}

Revise only when the evidence changes the understanding of the original
question or exposes a requirement needed to answer it. Do not turn an
interesting possibility into a requirement. New requirements must be tied to
exact supplied passage IDs and remain within the original inquiry. If nothing
material changed, return changed=false and empty arrays.
"""


def normalize_inquiry_refinement(
    raw: dict[str, Any] | None,
    analysis: dict[str, Any],
    passages: list[dict[str, Any]],
) -> dict[str, Any]:
    if not raw:
        return {"changed": False, "status": "unavailable", "research_implications": []}
    known_passages = {str(item.get("passage_id")) for item in passages if item.get("passage_id")}
    known_requirements = {
        str(item.get("requirement_id"))
        for item in analysis.get("research_requirements", [])
        if isinstance(item, dict) and item.get("requirement_id")
    }
    relationships = []
    for item in _as_list(raw.get("new_relationships")):
        if not isinstance(item, dict):
            continue
        passage_ids = [str(value) for value in _as_list(item.get("passage_ids")) if str(value) in known_passages]
        if passage_ids and _as_text(item.get("source")) and _as_text(item.get("target")):
            relationships.append({
                "source": _as_text(item.get("source")),
                "relation": _as_text(item.get("relation")),
                "target": _as_text(item.get("target")),
                "why_it_matters": _as_text(item.get("why_it_matters")),
                "passage_ids": passage_ids,
                "evidence_status": "llm_passage_linked",
            })
    implications = []
    for item in _as_list(raw.get("research_implications")):
        if not isinstance(item, dict):
            continue
        requirement_id = _as_text(item.get("requirement_id"))
        grounding = [str(value) for value in _as_list(item.get("grounding_passage_ids")) if str(value) in known_passages]
        if not requirement_id or not _as_text(item.get("question_component")):
            continue
        if requirement_id not in known_requirements and not grounding:
            continue
        implications.append({
            "requirement_id": requirement_id,
            "question_component": _as_text(item.get("question_component")),
            "why_needed": _as_text(item.get("why_needed")),
            "evidence_needed": _as_text(item.get("evidence_needed")),
            "search_queries": [_as_text(value) for value in _as_list(item.get("search_queries")) if _as_text(value)],
            "sufficiency_test": _as_text(item.get("sufficiency_test")),
            "grounding_passage_ids": grounding,
        })
    changed_interpretations = []
    for item in _as_list(raw.get("changed_interpretations")):
        if not isinstance(item, dict):
            continue
        passage_ids = [str(value) for value in _as_list(item.get("passage_ids")) if str(value) in known_passages]
        if not passage_ids or not _as_text(item.get("reading")):
            continue
        changed_interpretations.append({
            "reading": _as_text(item.get("reading")),
            "material_difference": _as_text(item.get("material_difference")),
            "confidence": float(item.get("confidence", 0.0) or 0.0),
            "passage_ids": passage_ids,
            "evidence_status": "llm_passage_linked",
        })
    return {
        "changed": _as_bool(raw.get("changed")),
        "revised_central_problem": _as_text(raw.get("revised_central_problem")),
        "revised_requested_task": _as_text(raw.get("revised_requested_task")),
        "new_relationships": relationships[:16],
        "changed_interpretations": changed_interpretations[:16],
        "research_implications": implications[:16],
        "synthesis_focus": [_as_text(value) for value in _as_list(raw.get("synthesis_focus")) if _as_text(value)][:16],
        "status": "llm",
    }


def apply_inquiry_refinement(analysis: dict[str, Any], refinement: dict[str, Any]) -> dict[str, Any]:
    """Merge only grounded model refinements into the working representation."""
    if not refinement.get("changed"):
        return analysis
    updated = dict(analysis)
    for key in ("central_problem", "requested_task"):
        value = refinement.get(f"revised_{key}")
        if value:
            updated[key] = value
    for key in ("relationships", "interpretations"):
        existing = list(updated.get(key) or [])
        additions = refinement.get("new_relationships" if key == "relationships" else "changed_interpretations") or []
        existing.extend(additions)
        updated[key] = existing[-32:]
    requirements = [dict(item) for item in updated.get("research_requirements", []) if isinstance(item, dict)]
    by_id = {str(item.get("requirement_id")): item for item in requirements if item.get("requirement_id")}
    for implication in refinement.get("research_implications", []):
        requirement = by_id.get(str(implication.get("requirement_id")))
        if requirement is None:
            requirement = {
                "requirement_id": implication.get("requirement_id"),
                "question_component": implication.get("question_component"),
                "why_needed": implication.get("why_needed"),
                "evidence_needed": implication.get("evidence_needed"),
                "source_preferences": [],
                "search_queries": implication.get("search_queries", []),
                "sufficiency_test": implication.get("sufficiency_test"),
                "required": True,
                "role": "refined_from_evidence",
            }
            requirements.append(requirement)
            by_id[str(requirement.get("requirement_id"))] = requirement
        else:
            for key in ("why_needed", "evidence_needed", "sufficiency_test"):
                if implication.get(key):
                    requirement[key] = implication[key]
            if implication.get("search_queries"):
                requirement["search_queries"] = implication["search_queries"]
    updated["research_requirements"] = requirements[:24]
    updated["synthesis_focus"] = refinement.get("synthesis_focus", [])
    updated["inquiry_refinement"] = refinement
    return updated


def adaptive_research_decision_prompt(
    query: str,
    analysis: dict[str, Any],
    candidates: list[dict[str, Any]],
    assessment: dict[str, Any] | None = None,
    research_round: int = 0,
) -> str:
    """Ask the model whether the current evidence warrants more research.

    This is deliberately separate from question planning.  A question can
    require research even when the initial plan did not predict that the
    local corpus would be empty, and a retrieved passage can still be
    irrelevant or insufficient after semantic evaluation.
    """
    evidence = [
        {
            "passage_id": item.get("passage_id"),
            "source_title": item.get("source_title"),
            "content": item.get("content") or item.get("passage_text"),
        }
        for item in candidates
    ]
    return f"""Decide whether this inquiry needs another evidence-gathering step.

Question:
{query}

Question-specific analysis:
{json.dumps(analysis, ensure_ascii=False)}

Current evidence candidates (empty means local retrieval found nothing usable):
{json.dumps(evidence, ensure_ascii=False, default=str)}

Current semantic evidence assessment:
{json.dumps(assessment or {}, ensure_ascii=False, default=str)}

Research round already attempted: {research_round}

Return JSON:
{{
  "research_required": true,
  "reason": "why another search is or is not material to this question",
  "missing_evidence":[{{
    "requirement_id":"exact id from the question analysis",
    "question_component":"the requirement this serves",
    "what_is_missing":"the evidence or explanation still needed",
    "why_material":"why this is necessary to answer the question",
    "search_queries":["focused query grounded in that requirement"]
  }}],
  "stop_reason":"evidence is sufficient|no material gap|research unavailable|other"
}}

Use only question requirements and gaps exposed by the supplied evidence
assessment. A possible topic is not an evidence gap merely because it could
be interesting. Do not invent a subject, theory, discipline, author, or
factor that is not connected to a stated question component. Distinguish
relevant from sufficient: further research is warranted when the available
evidence is relevant but does not establish a material explanation. Keep
search queries focused on the actual missing requirement.
"""


def normalize_adaptive_research_decision(
    raw: dict[str, Any] | None,
    analysis: dict[str, Any],
    candidates: list[dict[str, Any]],
    assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize the model decision without manufacturing new requirements."""
    requirements = {
        str(item.get("requirement_id")): item
        for item in analysis.get("research_requirements", [])
        if isinstance(item, dict) and item.get("requirement_id")
    }
    if raw is None:
        # When judgment is unavailable, an empty or explicitly insufficient
        # evidence set should still get an opportunity for external research.
        assessment_status = str((assessment or {}).get("sufficiency") or "").casefold()
        should_research = not candidates or assessment_status in {"insufficient", "partial", "unknown"}
        return {
            "research_required": should_research,
            "reason": "Semantic research decision was unavailable; evidence availability determines whether a retry is warranted.",
            "missing_evidence": [],
            "stop_reason": "decision_unavailable",
            "status": "unavailable",
        }

    missing = []
    for item in _as_list(raw.get("missing_evidence")):
        if not isinstance(item, dict):
            continue
        requirement_id = _as_text(item.get("requirement_id"))
        requirement = requirements.get(requirement_id)
        if not requirement:
            continue
        component = _as_text(item.get("question_component")) or _as_text(requirement.get("question_component"))
        missing.append({
            "requirement_id": requirement_id,
            "question_component": component,
            "what_is_missing": _as_text(item.get("what_is_missing")),
            "why_material": _as_text(item.get("why_material")),
            "search_queries": [
                _as_text(value) for value in _as_list(item.get("search_queries")) if _as_text(value)
            ],
        })
    research_required = _as_bool(raw.get("research_required"))
    if research_required and not missing:
        # A model may decide that the existing plan is the correct next step
        # without restating every requirement. Reuse only those plan queries.
        missing = [
            {
                "requirement_id": item.get("requirement_id"),
                "question_component": item.get("question_component"),
                "what_is_missing": item.get("evidence_needed"),
                "why_material": item.get("purpose"),
                "search_queries": list(item.get("search_terms") or []),
            }
            for item in research_plan_from_analysis(analysis)
            if item.get("requirement_id")
        ]
    return {
        "research_required": research_required and bool(missing or not candidates),
        "reason": _as_text(raw.get("reason")),
        "missing_evidence": missing[:12],
        "stop_reason": _as_text(raw.get("stop_reason")),
        "status": "llm",
    }


def evidence_relevance_prompt(query: str, analysis: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    evidence = []
    for candidate in candidates:
        evidence.append({
            "passage_id": candidate.get("passage_id"),
            "source_title": candidate.get("source_title"),
            "source_type": candidate.get("source_type"),
            "content": candidate.get("content") or candidate.get("passage_text"),
        })
    return f"""Judge whether each retrieved passage is intellectually relevant to the user's inquiry.

Question: {query}
Question-specific analysis:
{json.dumps(analysis, ensure_ascii=False)}

Retrieved passages (metadata identifies a passage; it is not evidence):
{json.dumps(evidence, ensure_ascii=False, default=str)}

Return JSON:
{{
  "evaluations": [{{
    "passage_id":"exact id",
    "relevance":"direct|indirect|contextual|irrelevant|unclear",
    "supports_requirements":["requirement_id"],
    "supported_proposition":"what this passage actually supports, if anything",
    "does_not_support":"important boundary",
    "evidence_role":"direct evidence|interpretation|context|none",
    "use_for_synthesis":true,
    "reason":"brief auditable reason"
  }}],
  "sufficiency":"sufficient|partial|insufficient|unknown",
  "satisfied_requirements":["requirement_id"],
  "missing_requirements":["requirement_id"],
  "next_research":[{{"requirement_id":"...", "query":"...", "reason":"..."}}]
}}

Use exact passage IDs. A passage is usable only when its content addresses a
question requirement, not merely because it shares vocabulary. Do not infer
facts that the passage does not state.
"""


def normalize_relevance_assessment(raw: dict[str, Any] | None, analysis: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(item.get("passage_id")): item for item in candidates if item.get("passage_id")}
    known_requirements = {
        str(item.get("requirement_id"))
        for item in analysis.get("research_requirements", [])
        if isinstance(item, dict) and item.get("requirement_id")
    }
    if not raw:
        return {
            "evaluations": [],
            "sufficiency": "unknown",
            "satisfied_requirements": [],
            "missing_requirements": [item.get("requirement_id") for item in analysis.get("research_requirements", [])],
            "next_research": [],
            "status": "unavailable",
            "usable_passage_ids": [],
        }
    evaluations = []
    usable = []
    for item in _as_list(raw.get("evaluations")):
        if not isinstance(item, dict):
            continue
        passage_id = str(item.get("passage_id") or "")
        passage = by_id.get(passage_id)
        if not passage or not is_substantive_passage(passage):
            continue
        relevance = _as_text(item.get("relevance"), "unclear").casefold()
        supports_requirements = [
            value for value in (
                _as_text(value) for value in _as_list(item.get("supports_requirements"))
            )
            if value and value in known_requirements
        ]
        supported_proposition = _as_text(item.get("supported_proposition"))
        use = (
            _as_bool(item.get("use_for_synthesis"))
            and relevance in {"direct", "indirect"}
            and bool(supports_requirements)
            and bool(supported_proposition)
        )
        normalized = {
            "passage_id": passage_id,
            "relevance": relevance,
            "supports_requirements": supports_requirements,
            "supported_proposition": supported_proposition,
            "does_not_support": _as_text(item.get("does_not_support")),
            "evidence_role": _as_text(item.get("evidence_role"), "none"),
            "use_for_synthesis": use,
            "reason": _as_text(item.get("reason")),
        }
        evaluations.append(normalized)
        if use and passage_id not in usable:
            usable.append(passage_id)
    return {
        "evaluations": evaluations,
        "sufficiency": _as_text(raw.get("sufficiency"), "unknown").casefold(),
        "satisfied_requirements": [
            value for value in (_as_text(value) for value in _as_list(raw.get("satisfied_requirements")))
            if value in known_requirements
        ],
        "missing_requirements": [
            value for value in (_as_text(value) for value in _as_list(raw.get("missing_requirements")))
            if value in known_requirements
        ],
        "next_research": [
            item for item in _as_list(raw.get("next_research"))
            if isinstance(item, dict) and _as_text(item.get("requirement_id")) in known_requirements
        ][:12],
        "status": "llm",
        "usable_passage_ids": usable,
    }


def evidence_reasoning_prompt(query: str, analysis: dict[str, Any], assessment: dict[str, Any], passages: list[dict[str, Any]], claims: list[dict[str, Any]]) -> str:
    compact_passages = [
        {"passage_id": item.get("passage_id"), "source_title": item.get("source_title"), "source_type": item.get("source_type"), "content": item.get("content")}
        for item in passages
    ]
    compact_claims = [
        {"claim_id": item.get("claim_id"), "passage_id": item.get("passage_id"), "statement": item.get("statement"), "claim_type": item.get("claim_type")}
        for item in claims
    ]
    return f"""Reason over the relevant evidence for this inquiry. Do not summarize unrelated passages.

Question: {query}
Question analysis:
{json.dumps(analysis, ensure_ascii=False)}
Evidence relevance judgments:
{json.dumps(assessment, ensure_ascii=False)}
Passages:
{json.dumps(compact_passages, ensure_ascii=False, default=str)}
Source-linked claims:
{json.dumps(compact_claims, ensure_ascii=False, default=str)}

Return JSON with concise, auditable artifacts only:
{{
  "source_positions":[{{"source_id":"...", "source_title":"...", "position":"...", "problem_addressed":"...", "premises":["..."], "conclusion":"...", "argument_form":"...", "reasoning_summary":"...", "assumptions":["..."], "qualifications":["..."], "epistemic_status":"established|well-supported|plausible|contested|uncertain", "supporting_passage_ids":["..."]}}],
  "relationships":[{{"source_a":"...", "source_b":"...", "relation":"agreement|qualification|complementarity|contradiction|framework_difference|different_question|term_scope_difference|unresolved", "explanation":"...", "question_significance":"...", "passage_ids":["..."]}}],
  "reasoning_chains":[{{"question_component":"...", "claim":"...", "evidence_passage_ids":["..."], "analysis":"...", "conclusion":"...", "confidence":0.0, "inference_status":"direct|interpretation|inference|synthesis", "epistemic_status":"established|well-supported|plausible|contested|uncertain"}}],
  "insights":[{{"insight":"a justified connection that helps answer the inquiry", "question_component":"...", "supporting_passage_ids":["..."], "why_justified":"...", "inference_status":"inference|synthesis", "confidence":0.0}}],
  "gaps":[{{"requirement_id":"exact id from the question analysis", "description":"material evidence gap grounded in that requirement"}}],
  "alternatives":["..."]
}}

Every source position and reasoning chain must cite one or more exact passage
IDs. Reconstruct premises and conclusions only when the passages warrant it.
Do not call sources contradictory unless their supported propositions conflict
after accounting for scope, terminology, assumptions, and whether they answer
the same question. A difference in framework or question is not a
contradiction.
"""


def _valid_passage_ids(items: Any, known: set[str]) -> list[str]:
    return [str(item) for item in _as_list(items) if str(item) in known]


def normalize_evidence_reasoning(
    raw: dict[str, Any] | None,
    passages: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    known = {str(item.get("passage_id")) for item in passages if item.get("passage_id")}
    if not raw:
        return {"source_positions": [], "relationships": [], "chains": [], "insights": [], "gaps": ["The model could not produce an evidence-linked reasoning record."], "alternatives": [], "status": "unavailable"}
    positions = []
    for item in _as_list(raw.get("source_positions")):
        if not isinstance(item, dict):
            continue
        passage_ids = _valid_passage_ids(item.get("supporting_passage_ids"), known)
        if not passage_ids:
            continue
        positions.append({
            "source_id": _as_text(item.get("source_id")),
            "source_title": _as_text(item.get("source_title")),
            "central_position": _as_text(item.get("position")),
            "problem_addressed": _as_text(item.get("problem_addressed")),
            "argument": _as_text(item.get("reasoning_summary")),
            "premises": [_as_text(value) for value in _as_list(item.get("premises")) if _as_text(value)],
            "conclusion": _as_text(item.get("conclusion")),
            "argument_form": _as_text(item.get("argument_form")),
            "assumptions": [_as_text(value) for value in _as_list(item.get("assumptions")) if _as_text(value)],
            "qualifications": [_as_text(value) for value in _as_list(item.get("qualifications")) if _as_text(value)],
            "source_epistemic_status": _as_text(item.get("epistemic_status"), "uncertain"),
            "evidence_passage_ids": passage_ids,
            "epistemic_status": "LLM_RECONSTRUCTION",
            "interpretation_boundary": "Concise model reconstruction constrained to cited passages.",
        })
    relationships = []
    for item in _as_list(raw.get("relationships")):
        if not isinstance(item, dict):
            continue
        passage_ids = _valid_passage_ids(item.get("passage_ids"), known)
        if not passage_ids:
            continue
        relationships.append({
            "source_a": _as_text(item.get("source_a")),
            "source_b": _as_text(item.get("source_b")),
            "relation": _as_text(item.get("relation"), "unresolved").casefold(),
            "explanation": _as_text(item.get("explanation")),
            "question_significance": _as_text(item.get("question_significance")),
            "passage_ids": passage_ids,
            "evidence_status": "llm_passage_linked",
        })
    chains = []
    for item in _as_list(raw.get("reasoning_chains")):
        if not isinstance(item, dict):
            continue
        passage_ids = _valid_passage_ids(item.get("evidence_passage_ids"), known)
        if not passage_ids or not _as_text(item.get("claim")):
            continue
        chains.append({
            "claim": _as_text(item.get("claim")),
            "evidence": passage_ids,
            "sources": [],
            "relationship": "question_aligned_reasoning",
            "confidence": float(item.get("confidence", 0.0) or 0.0),
            "type": "LLM_REASONING",
            "question_component": _as_text(item.get("question_component")),
            "analysis": _as_text(item.get("analysis")),
            "conclusion": _as_text(item.get("conclusion")),
            "inference_status": _as_text(item.get("inference_status"), "inference"),
            "epistemic_status": _as_text(item.get("epistemic_status"), "uncertain"),
        })
    insights = []
    for item in _as_list(raw.get("insights")):
        if not isinstance(item, dict):
            continue
        passage_ids = _valid_passage_ids(item.get("supporting_passage_ids"), known)
        if not passage_ids or not _as_text(item.get("insight")):
            continue
        insights.append({
            "insight": _as_text(item.get("insight")),
            "question_component": _as_text(item.get("question_component")),
            "evidence": passage_ids,
            "why_justified": _as_text(item.get("why_justified")),
            "inference_status": _as_text(item.get("inference_status"), "inference"),
            "confidence": float(item.get("confidence", 0.0) or 0.0),
        })
    requirements = {
        str(item.get("requirement_id")): item
        for item in (analysis or {}).get("research_requirements", [])
        if isinstance(item, dict) and item.get("requirement_id")
    }
    # Free-form gap text is not promoted to an unresolved issue.  Only retain
    # gaps with an explicit requirement link; possible explanatory factors are
    # not evidence gaps unless the question-specific plan made them material.
    grounded_gaps = []
    for item in _as_list(raw.get("gaps")):
        if not isinstance(item, dict):
            continue
        requirement_id = _as_text(item.get("requirement_id"))
        if requirement_id and requirement_id in requirements:
            grounded_gaps.append(_as_text(item.get("description") or item.get("gap")))
    return {
        "source_positions": positions,
        "relationships": relationships,
        "chains": chains,
        "insights": insights[:16],
        "gaps": [value for value in grounded_gaps if value],
        "alternatives": [_as_text(value) for value in _as_list(raw.get("alternatives")) if _as_text(value)],
        "status": "llm",
    }


def semantic_audit_prompt(query: str, analysis: dict[str, Any], assessment: dict[str, Any], response: str, passages: list[dict[str, Any]]) -> str:
    evidence = [{"passage_id": item.get("passage_id"), "content": item.get("content")} for item in passages]
    return f"""Audit this proposed answer against the user's actual question.

Question: {query}
Question-specific analysis:
{json.dumps(analysis, ensure_ascii=False)}
Evidence judgments:
{json.dumps(assessment, ensure_ascii=False)}
Proposed answer:
{response}
Substantive passages:
{json.dumps(evidence, ensure_ascii=False, default=str)}

Return JSON:
{{
  "addresses_question": true,
  "covered_requirements":["requirement_id"],
  "uncovered_requirements":["requirement_id"],
  "evidence_alignment":[{{"passage_id":"...", "supports":true, "reason":"..."}}],
  "irrelevant_or_unsupported_claims":["..."],
  "topic_drift":false,
  "conclusion_follows":true,
  "answer_is_source_summary":false,
  "epistemic_calibration":"established|well-supported|plausible|contested|uncertain|unsupported",
  "sufficient_for_answer":true,
  "reason":"brief audit explanation"
}}

Judge meaning and relationships compositionally. Shared words are not enough.
Reject an answer that discusses a true but unrelated topic, merely summarizes
sources without answering, or reaches a conclusion that does not follow from
the cited evidence. Do not approve metadata, URLs, retrieval status, or source
descriptions as an answer.
"""


def answer_repair_prompt(
    query: str,
    analysis: dict[str, Any],
    assessment: dict[str, Any],
    reasoning: dict[str, Any],
    draft: str,
    audit: dict[str, Any],
    passages: list[dict[str, Any]],
) -> str:
    evidence = [
        {"passage_id": item.get("passage_id"), "source_title": item.get("source_title"), "content": item.get("content")}
        for item in passages
    ]
    return f"""Repair the proposed answer so it answers the user's actual inquiry.

Question: {query}
Question-specific analysis:
{json.dumps(analysis, ensure_ascii=False)}
Evidence judgments:
{json.dumps(assessment, ensure_ascii=False)}
Auditable reasoning summaries:
{json.dumps(reasoning, ensure_ascii=False)}
Draft:
{draft}
Audit:
{json.dumps(audit, ensure_ascii=False)}
Substantive evidence:
{json.dumps(evidence, ensure_ascii=False, default=str)}

Write only the final answer in readable Markdown. Directly answer the
question, preserve only claims supported by the cited passages, distinguish
source statements from interpretation, and acknowledge unresolved requirements
when necessary. Cite evidence inline as [P#]. Do not mention this repair,
retrieval, metadata, pipeline state, hidden reasoning, or a source merely
because it is present. Do not force a conclusion when evidence is insufficient.
"""


def normalize_semantic_audit(raw: dict[str, Any] | None, passages: list[dict[str, Any]]) -> dict[str, Any]:
    known = {str(item.get("passage_id")) for item in passages if item.get("passage_id")}
    if not raw:
        return {
            "addresses_question": False,
            "covered_requirements": [],
            "uncovered_requirements": [],
            "evidence_alignment": [],
            "irrelevant_or_unsupported_claims": ["Semantic audit unavailable."],
            "topic_drift": True,
            "conclusion_follows": False,
            "answer_is_source_summary": False,
            "epistemic_calibration": "unsupported",
            "sufficient_for_answer": False,
            "reason": "The answer could not be semantically audited.",
            "status": "unavailable",
        }
    alignment = []
    for item in _as_list(raw.get("evidence_alignment")):
        if not isinstance(item, dict) or str(item.get("passage_id")) not in known:
            continue
        alignment.append({"passage_id": str(item.get("passage_id")), "supports": _as_bool(item.get("supports")), "reason": _as_text(item.get("reason"))})
    return {
        "addresses_question": _as_bool(raw.get("addresses_question")),
        "covered_requirements": [_as_text(value) for value in _as_list(raw.get("covered_requirements")) if _as_text(value)],
        "uncovered_requirements": [_as_text(value) for value in _as_list(raw.get("uncovered_requirements")) if _as_text(value)],
        "evidence_alignment": alignment,
        "irrelevant_or_unsupported_claims": [_as_text(value) for value in _as_list(raw.get("irrelevant_or_unsupported_claims")) if _as_text(value)],
        "topic_drift": _as_bool(raw.get("topic_drift")),
        "conclusion_follows": _as_bool(raw.get("conclusion_follows"), _as_bool(raw.get("addresses_question"))),
        "answer_is_source_summary": _as_bool(raw.get("answer_is_source_summary")),
        "epistemic_calibration": _as_text(raw.get("epistemic_calibration"), "uncertain"),
        "sufficient_for_answer": _as_bool(raw.get("sufficient_for_answer")),
        "reason": _as_text(raw.get("reason")),
        "status": "llm",
    }


def challenge_prompt(query: str, analysis: dict[str, Any], chains: dict[str, Any]) -> str:
    return f"""Identify only the most important, evidence-grounded limitations or counter-considerations for this inquiry.
Question: {query}
Question analysis: {json.dumps(analysis, ensure_ascii=False)}
Reasoning summaries: {json.dumps(chains, ensure_ascii=False)}

Return JSON {{"objections":[{{"objection":"...", "target":"question component, assumption, or claim", "type":"assumption|ambiguity|scope|evidence|interpretation|causal_leap", "why_material":"...", "confidence":0.0}}]}}.
Look for hidden assumptions, ambiguity, false dichotomies, unjustified causal
steps, overgeneralization, or an important competing interpretation only when
it materially improves the answer. Do not challenge the user for its own sake.
Every objection must be supported by the supplied analysis or reasoning
summaries; do not invent a competing theory or source.
"""


def normalize_challenges(raw: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    result = []
    for item in _as_list(raw.get("objections")):
        if isinstance(item, dict) and _as_text(item.get("objection")):
            result.append({
                "objection": _as_text(item.get("objection")),
                "target": _as_text(item.get("target")),
                "type": _as_text(item.get("type"), "scope"),
                "why_material": _as_text(item.get("why_material")),
                "confidence": float(item.get("confidence", 0.0) or 0.0),
            })
    return result[:24]
