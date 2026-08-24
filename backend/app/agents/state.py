from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from backend.app.domain.models.enums import SourceType, ClaimType, EvidenceStatus
from backend.app.domain.models.evidence import Claim
from backend.app.domain.models.argument import Argument
from backend.app.application.use_cases.source_critic import CritiqueFinding

class InquiryState(TypedDict):
    query: str
    user_id: str
    sub_questions: List[str]
    retrieved_passages: List[Dict[str, Any]]
    extracted_claims: List[Dict[str, Any]]
    critique_findings: List[Dict[str, Any]]
    reconstructed_arguments: List[Dict[str, Any]]
    counterarguments: List[str]
    uncertainties: List[str]
    final_synthesis: Optional[str]
    current_step: str