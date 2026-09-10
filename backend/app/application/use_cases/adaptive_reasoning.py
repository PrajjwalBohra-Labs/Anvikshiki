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
  "concepts": [{{"label":"...", "role":"...", "contextual_meaning":"..."}}],
  "relationships": [{{"source":"...", "relation":"...", "target":"...", "why_it_matters":"..."}}],
  "assumptions": [{{"assumption":"...", "materiality":"..."}}],
  "interpretations": [{{"reading":"...", "material_difference":"...", "confidence":0.0}}],
  "research_requirements": [{{
    "requirement_id":"stable short id",
    "question_component":"the exact part this serves",
    "why_needed":"...",
    "evidence_needed":"...",
    "source_preferences":["only source kinds justified by this question"],
    "search_queries":["focused query"],
    "sufficiency_test":"what would count as enough evidence",
    "required":true
  }}],
  "research_needed": true,
  "answer_strategy": {{"depth":"...", "order":["..."], "must_address":["..."], "omit":["..."]}}
}}

Only include ambiguities, perspectives, and research requirements that
materially affect this particular question. Do not fill fields with generic
philosophical categories.
"""


def fallback_question_analysis(query: str, domain: str | None, depth: str) -> dict[str, Any]:
    """Minimal non-semantic fallback; it never supplies concepts or theories."""
    normalized = _as_text(query)
    return {
        "literal_question": normalized,
        "central_problem": normalized,
        "requested_task": normalized,
        "inquiry_mode": "undetermined",
        "concepts": [],
        "relationships": [],
        "assumptions": [],
        "interpretations": [],
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
    for key in ("concepts", "relationships", "assumptions", "interpretations"):
        normalized[key] = _as_list(data.get(key))[:24]

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
            "required": item.get("required", True),
        })
    return plan


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
  "source_positions":[{{"source_id":"...", "source_title":"...", "position":"...", "problem_addressed":"...", "reasoning_summary":"...", "assumptions":["..."], "qualifications":["..."], "supporting_passage_ids":["..."]}}],
  "relationships":[{{"source_a":"...", "source_b":"...", "relation":"agreement|qualification|complementarity|contradiction|framework_difference|unresolved", "explanation":"...", "passage_ids":["..."]}}],
  "reasoning_chains":[{{"question_component":"...", "claim":"...", "evidence_passage_ids":["..."], "analysis":"...", "conclusion":"...", "confidence":0.0, "inference_status":"direct|interpretation|inference|synthesis"}}],
  "gaps":["..."],
  "alternatives":["..."]
}}

Every source position and claim must cite one or more exact passage IDs. Do
not call sources contradictory unless their supported propositions conflict
after accounting for scope, terminology, and assumptions.
"""


def _valid_passage_ids(items: Any, known: set[str]) -> list[str]:
    return [str(item) for item in _as_list(items) if str(item) in known]


def normalize_evidence_reasoning(raw: dict[str, Any] | None, passages: list[dict[str, Any]], claims: list[dict[str, Any]]) -> dict[str, Any]:
    known = {str(item.get("passage_id")) for item in passages if item.get("passage_id")}
    if not raw:
        return {"source_positions": [], "relationships": [], "chains": [], "gaps": ["The model could not produce an evidence-linked reasoning record."], "alternatives": [], "status": "unavailable"}
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
            "assumptions": [_as_text(value) for value in _as_list(item.get("assumptions")) if _as_text(value)],
            "qualifications": [_as_text(value) for value in _as_list(item.get("qualifications")) if _as_text(value)],
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
        })
    return {
        "source_positions": positions,
        "relationships": relationships,
        "chains": chains,
        "gaps": [_as_text(value) for value in _as_list(raw.get("gaps")) if _as_text(value)],
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
  "sufficient_for_answer":true,
  "reason":"brief audit explanation"
}}

Judge meaning and relationships compositionally. Shared words are not enough.
Reject an answer that discusses a true but unrelated topic. Do not approve
metadata, URLs, retrieval status, or source descriptions as an answer.
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
        "sufficient_for_answer": _as_bool(raw.get("sufficient_for_answer")),
        "reason": _as_text(raw.get("reason")),
        "status": "llm",
    }


def challenge_prompt(query: str, analysis: dict[str, Any], chains: dict[str, Any]) -> str:
    return f"""Identify the most important limitations or counter-considerations for this evidence-grounded answer.
Question: {query}
Question analysis: {json.dumps(analysis, ensure_ascii=False)}
Reasoning summaries: {json.dumps(chains, ensure_ascii=False)}

Return JSON {{"objections":[{{"objection":"...", "target":"question component or claim", "type":"assumption|scope|evidence|interpretation", "confidence":0.0}}]}}.
Only identify objections supported by the supplied reasoning summaries. Do not
invent a competing theory or source.
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
                "confidence": float(item.get("confidence", 0.0) or 0.0),
            })
    return result[:24]
