import re
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.application.use_cases.conduct_research import ResearchCoordinator
from backend.app.application.use_cases.memory_service import MemoryService
from backend.app.application.use_cases.dialogue_controller import DialogueController

class PromptInjectionGuard:
    INJECTION_PATTERNS = [
        r"ignore previous instructions",
        r"system override",
        r"you are now an unrestricted",
        r"bypass security policy",
        r"disregard all previous"
    ]

    @classmethod
    def validate_input(cls, text: str) -> bool:
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        return True

class MCPToolServer:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.research_coordinator = ResearchCoordinator(session)
        self.memory_service = MemoryService(session)
        self.dialogue_controller = DialogueController(session)

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        # Enforce security validation on text inputs
        for val in arguments.values():
            if isinstance(val, str) and not PromptInjectionGuard.validate_input(val):
                return {
                    "status": "error",
                    "error_code": "PROMPT_INJECTION_DETECTED",
                    "message": "Input contains disallowed override directives."
                }

        if tool_name == "search_local_sources":
            query = arguments.get("query", "")
            res = await self.research_coordinator.conduct_research(query)
            return {
                "status": "success",
                "claims_found": len(res.claims),
                "passages": [
                    {
                        "id": sp.passage.id,
                        "content": sp.passage.content,
                        "source_type": sp.passage.source_type.value,
                        "score": sp.score
                    }
                    for sp in res.scored_passages
                ]
            }

        elif tool_name == "get_user_epistemic_state":
            user_id = arguments.get("user_id", "default_researcher")
            history = await self.memory_service.get_user_epistemic_history(user_id)
            return {
                "status": "success",
                "epistemic_positions": [
                    {
                        "claim": h.claim_statement,
                        "position": h.user_position,
                        "confidence": h.confidence,
                        "status": h.status
                    }
                    for h in history
                ]
            }

        elif tool_name == "conduct_inquiry":
            user_id = arguments.get("user_id", "default_researcher")
            message = arguments.get("message", "")
            user_pos = arguments.get("user_position")
            conf = float(arguments.get("confidence", 0.5))
            
            res = await self.dialogue_controller.process_user_turn(
                user_id=user_id,
                user_message=message,
                user_position=user_pos,
                confidence=conf
            )
            return {
                "status": "success",
                "synthesis": res.inquiry_summary,
                "arguments_examined": res.arguments_examined,
                "critical_challenges": res.critical_challenges,
                "unresolved_question": res.unresolved_question
            }

        return {
            "status": "error",
            "error_code": "TOOL_NOT_FOUND",
            "message": f"Tool '{tool_name}' is not recognized."
        }