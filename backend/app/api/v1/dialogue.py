from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import get_db
from backend.app.application.use_cases.dialogue_engine import DialogueEngine
from backend.app.api.v1.schemas.dtos import DialogueTurnRequestDTO, DialogueTurnResponseDTO

router = APIRouter()

@router.post("/turn", response_model=DialogueTurnResponseDTO)
async def execute_dialogue_turn(payload: DialogueTurnRequestDTO, db: AsyncSession = Depends(get_db)):
    engine = DialogueEngine(db)
    result = await engine.generate_response(
        user_utterance=payload.user_utterance,
        dialogue_mode=payload.dialogue_mode,
        evidence_passage_id=payload.evidence_passage_id,
        user_mastery_demonstrated=payload.user_mastery_demonstrated
    )
    return DialogueTurnResponseDTO(
        response_text=result["response_text"],
        dialogue_mode=result["dialogue_mode"],
        disagrees_with_user=result["disagrees_with_user"],
        evidence_linked=result["evidence_linked"],
        preserves_uncertainty=result["preserves_uncertainty"],
        source_title=result.get("source_title")
    )