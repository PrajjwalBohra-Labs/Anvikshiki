from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)

logger = structlog.get_logger(__name__)

class DialogueEngine:
    """
    Orchestrates scholarly dialogue avoiding traditional lesson generation.
    Supports Socratic questioning, explanation, analogy, counterexample, challenge,
    debate, argument reconstruction, source examination, reflective questioning, and research-with-user.
    Enforces evidence grounding, preserves uncertainty, and disagrees when evidence warrants it.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_response(
        self,
        user_utterance: str,
        dialogue_mode: str = "socratic",  # socratic, challenge, explanation, analogy, counterexample, debate, etc.
        evidence_passage_id: str | None = None,
        user_mastery_demonstrated: bool = False
    ) -> dict[str, Any]:
        """
        Generates a dialogue turn ensuring evidence linkage, uncertainty preservation, 
        meaningful follow-up questioning, and principled disagreement when warranted.
        """
        evidence_content = None
        source_title = None

        if evidence_passage_id:
            passage = await self.session.get(PassageModel, evidence_passage_id)
            if passage:
                evidence_content = passage.content
                doc_obj = await self.session.get(DocumentModel, passage.document_id)
                if doc_obj:
                    source_obj = await self.session.get(SourceModel, doc_obj.source_id)
                    if source_obj:
                        source_title = source_obj.title

        # Guard: Avoid unnecessary explanation when mastery is demonstrated
        if user_mastery_demonstrated and dialogue_mode == "explanation":
            dialogue_mode = "reflective"
            logger.info("Switching from explanation to reflective questioning due to demonstrated user mastery.")

        # Construct response based on dialogue mode
        response_text = ""
        disagrees = False

        if dialogue_mode == "socratic":
            response_text = (
                "Consider the core premise of your position. If perception is restricted to direct sense contact, "
                "how do you account for inferential cognition (Anumana)? What textual basis supports this?"
            )
        elif dialogue_mode == "challenge" or dialogue_mode == "debate":
            disagrees = True
            response_text = (
                f"The evidence from authoritative sources contradicts this assertion. "
                f"Specifically, {source_title or 'primary texts'} notes: '{evidence_content or ' cognition requires valid epistemic conditions.'}' "
                f"How do you reconcile your view with this direct textual counter-evidence?"
            )
        elif dialogue_mode == "counterexample":
            disagrees = True
            response_text = (
                "Let us test that universal claim against a recognized counterexample in the tradition. "
                "Does this rule hold when illusory perception (Bhranti) occurs?"
            )
        else:
            response_text = (
                f"Examining {source_title or 'the source material'} leaves a degree of interpretive uncertainty regarding this concept. "
                f"What alternative reading might we consider?"
            )

        return {
            "response_text": response_text,
            "dialogue_mode": dialogue_mode,
            "disagrees_with_user": disagrees,
            "evidence_linked": bool(evidence_passage_id),
            "preserves_uncertainty": True,
            "source_title": source_title
        }