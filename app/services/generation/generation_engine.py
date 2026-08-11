"""
Generation Engine (§6; wired to the Step 3 LLM adapter). Turns a
Step 8 ReasoningObject into a streamed natural-language response --
this is the one place in the system where prose actually gets
produced, deliberately separate from Reasoning (§13 "reasoning is
independent of language generation").

Prompt assembly lives in the Prompt Service (§22); this module only
wires that assembled prompt to LLMAdapter.stream()/.generate().
"""

from __future__ import annotations

from collections.abc import Iterator

from app.infrastructure.llm_adapter import LLMAdapter, get_llm_adapter
from app.services.prompt.prompt_builder import build_prompt
from app.services.reasoning.reasoning_engine import ReasoningObject


def generate_response(
    reasoning: ReasoningObject,
    query: str,
    conversation_history: list[dict] | None = None,
    llm_adapter: LLMAdapter | None = None,
) -> Iterator[str]:
    """Streams a coherent response grounded in the reasoning object."""
    llm_adapter = llm_adapter or get_llm_adapter()
    prompt = build_prompt(reasoning, query, conversation_history)
    yield from llm_adapter.stream(prompt.text)


def generate_response_text(
    reasoning: ReasoningObject,
    query: str,
    conversation_history: list[dict] | None = None,
    llm_adapter: LLMAdapter | None = None,
) -> str:
    """Non-streaming convenience wrapper -- collects the full response."""
    llm_adapter = llm_adapter or get_llm_adapter()
    prompt = build_prompt(reasoning, query, conversation_history)
    return llm_adapter.generate(prompt.text)
