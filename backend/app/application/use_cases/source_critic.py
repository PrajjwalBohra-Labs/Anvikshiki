from typing import List, Optional
from pydantic import BaseModel
from backend.app.domain.models.enums import SourceType, EvidenceStatus
from backend.app.domain.models.evidence import SourceProvenance

class CritiqueFinding(BaseModel):
    issue_type: str
    description: str
    risk_level: str  # low, medium, high
    epistemic_status: EvidenceStatus

class SourceCritic:
    @staticmethod
    def criticize_source(provenance: SourceProvenance, text_content: str, source_type: SourceType) -> List[CritiqueFinding]:
        findings: List[CritiqueFinding] = []

        # 1. Translation Distance & Intervention Check
        if provenance.translator and provenance.original_language:
            if provenance.original_language.lower() in ["sanskrit", "prakrit", "greek"]:
                findings.append(
                    CritiqueFinding(
                        issue_type="TRANSLATION_MEDIATION",
                        description=f"Text mediated via translation by {provenance.translator}. Conceptual alignment must be cross-verified against original {provenance.original_language} terms.",
                        risk_level="medium",
                        epistemic_status=EvidenceStatus.PLAUSIBLE
                    )
                )

        # 2. Historical & Institutional Context Check (e.g., 19th Century Colonial Historiography)
        if provenance.translation_year and provenance.translation_year < 1920:
            findings.append(
                CritiqueFinding(
                    issue_type="HISTORICAL_ERA_ASSUMPTION",
                    description="19th/early 20th-century philological framing. Must check for Christian theological or Eurocentric conceptual substitutions (e.g., translating Ishvara as God or Maya as Illusion).",
                    risk_level="medium",
                    epistemic_status=EvidenceStatus.CONTESTED
                )
            )

        # 3. Scientific Finding vs Causation Risk
        if source_type == SourceType.SCIENTIFIC_STUDY:
            content_lower = text_content.lower()
            if "proves that" in content_lower and ("correlated" in content_lower or "associated" in content_lower):
                findings.append(
                    CritiqueFinding(
                        issue_type="CAUSATION_OVERREACH",
                        description="Correlation or statistical association conflated with causal proof.",
                        risk_level="high",
                        epistemic_status=EvidenceStatus.WEAKLY_SUPPORTED
                    )
                )

        return findings