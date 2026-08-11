"""
Prompt Service (§22 Prompt Orchestration). Pure assembly -- no LLM
calls happen here. Layers, in the exact §22 order:

    System -> Architecture policy -> Module policy -> Task
    instructions -> Retrieved knowledge -> Conversation -> User
    message

Each layer is its own function so templates stay "modular and
reusable" (§22). Empty layers are omitted entirely rather than
included blank.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.security.prompt_injection import sanitize_against_injection
from app.services.context.context_builder import SYSTEM_POLICIES
from app.services.reasoning.reasoning_engine import ReasoningObject

_LAYER_ORDER = (
    "system",
    "architecture_policy",
    "module_policy",
    "task_instructions",
    "retrieved_knowledge",
    "conversation",
    "user_message",
)


@dataclass
class AssembledPrompt:
    layers: list[tuple[str, str]] = field(default_factory=list)
    text: str = ""


def _system_layer() -> str:
    return (
        "You are Anvikshiki, a modular cognitive architecture. You reason "
        "before you speak, and you never present speculation as settled fact."
    )


def _architecture_policy_layer() -> str:
    return "\n".join(SYSTEM_POLICIES)


def _module_policy_layer(reasoning: ReasoningObject) -> str:
    policies = [
        "Ground every claim in the evidence provided below; do not introduce facts that aren't there.",
        "Attribute claims to their source document by title where possible.",
    ]
    if reasoning.assumptions:
        policies.append(f"Note these assumptions explicitly: {', '.join(reasoning.assumptions)}.")
    if reasoning.constraints:
        policies.append(f"Respect these constraints: {', '.join(reasoning.constraints)}.")
    if reasoning.confidence is not None:
        score = reasoning.confidence.overall
        policies.append(
            f"Your computed confidence score is exactly {score:.2f} out of 1.0. "
            f"If you state a confidence number in your response, it must be {score:.2f} -- "
            "never estimate, round, or invent a different number. It is safer to describe your "
            "certainty in words (e.g. \"fairly confident\", \"limited evidence\") than to state any "
            "other numeric confidence value."
        )
    if any(item.get("source_type") == "web" for item in reasoning.evidence):
        policies.append(
            "Some evidence below is marked WEB (external, unverified) rather than LOCAL "
            "(ingested knowledge base). Treat LOCAL evidence as more authoritative. When a "
            "claim relies on WEB evidence, say so explicitly rather than presenting it with "
            "the same confidence as LOCAL evidence."
        )
    return "\n".join(f"- {p}" for p in policies)


def _task_instructions_layer() -> str:
    return (
        "Using only the reasoning and evidence below, write a clear, direct answer to the "
        "user's question. If the evidence is insufficient or conflicting, say so plainly "
        "rather than filling gaps with speculation."
    )


def _retrieved_knowledge_layer(reasoning: ReasoningObject) -> str:
    if not reasoning.evidence:
        return "No evidence was retrieved for this query."
    fact_by_id = {fact["chunk_id"]: fact["text"] for fact in reasoning.facts}
    lines = []
    for item in reasoning.evidence:
        text = fact_by_id.get(item["chunk_id"], "")
        # Documents are an injection vector too (§27) -- their text is
        # about to be inserted verbatim into the prompt.
        text = sanitize_against_injection(text, source="retrieved_document")
        source = item.get("source_document_title") or item.get("source_document_id") or "unknown source"
        if item.get("source_type") == "web":
            url = item.get("source_url") or ""
            lines.append(f"WEB (external, unverified) [{source}]: {text} (source: {url})")
        else:
            lines.append(f"LOCAL (knowledge base) [{source}]: {text}")
    return "\n\n".join(lines)


def _conversation_layer(conversation_history: list[dict] | None) -> str:
    if not conversation_history:
        return ""
    return "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in conversation_history)


def _user_message_layer(query: str) -> str:
    return query.strip()


def build_prompt(
    reasoning: ReasoningObject,
    query: str,
    conversation_history: list[dict] | None = None,
) -> AssembledPrompt:
    layer_content = {
        "system": _system_layer(),
        "architecture_policy": _architecture_policy_layer(),
        "module_policy": _module_policy_layer(reasoning),
        "task_instructions": _task_instructions_layer(),
        "retrieved_knowledge": _retrieved_knowledge_layer(reasoning),
        "conversation": _conversation_layer(conversation_history),
        "user_message": _user_message_layer(query),
    }

    kept = [(name, layer_content[name]) for name in _LAYER_ORDER if layer_content[name]]
    text = "\n\n".join(f"### {name.upper()}\n{content}" for name, content in kept)

    return AssembledPrompt(layers=kept, text=text)
