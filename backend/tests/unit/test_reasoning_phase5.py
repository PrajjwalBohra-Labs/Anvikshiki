import pytest
from backend.app.domain.models.enums import SourceType, EvidenceStatus, PramanaType, ClaimType
from backend.app.domain.models.evidence import Claim, SourceProvenance
from backend.app.domain.models.argument import Argument, InferenceRelation, HetvabhasaType
from backend.app.application.use_cases.evidence_graph import ContradictionDetector, EvidenceGraph
from backend.app.application.use_cases.source_critic import SourceCritic

def test_contradiction_detection():
    claim1 = "Knowledge acquired through pratyaksha is inherently valid in all circumstances."
    claim2 = "Knowledge acquired through pratyaksha is inherently invalid until confirmed."
    claim3 = "Knowledge acquired through pratyaksha is valid only when sense organs are unimpaired."

    assert ContradictionDetector.evaluate_relation(claim1, claim2) == InferenceRelation.CONTRADICTS
    assert ContradictionDetector.evaluate_relation(claim1, claim3) == InferenceRelation.QUALIFIES

def test_source_criticism_translation_and_historical_era():
    prov = SourceProvenance(
        author="Badarayana",
        original_language="Sanskrit",
        translator="Max Muller",
        translation_year=1884,
        citation_string="Sacred Books of the East, Vol 34"
    )

    findings = SourceCritic.criticize_source(
        provenance=prov,
        text_content="The absolute spirit creates the world as an illusion.",
        source_type=SourceType.TRANSLATION
    )

    issue_types = [f.issue_type for f in findings]
    assert "TRANSLATION_MEDIATION" in issue_types
    assert "HISTORICAL_ERA_ASSUMPTION" in issue_types

def test_scientific_causation_criticism():
    prov = SourceProvenance(
        author="Neuroscience Lab",
        citation_string="Frontiers in Human Neuroscience 2022"
    )
    text = "The study observed neural activity was correlated with subjective perception, which proves that brain region X causes consciousness."
    findings = SourceCritic.criticize_source(
        provenance=prov,
        text_content=text,
        source_type=SourceType.SCIENTIFIC_STUDY
    )

    issue_types = [f.issue_type for f in findings]
    assert "CAUSATION_OVERREACH" in issue_types
    assert any(f.epistemic_status == EvidenceStatus.WEAKLY_SUPPORTED for f in findings)