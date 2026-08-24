import pytest
from backend.app.domain.models.enums import SourceType, ClaimType, RelationType, PramanaType
from backend.app.domain.models.source import Source, Document, Passage
from backend.app.domain.models.reasoning import Claim, Evidence, Argument

def test_source_and_passage_creation():
    source = Source(title="Nyaya Sutras", source_type=SourceType.PRIMARY)
    doc = Document(source_id=source.id, checksum_sha256="abc123", mime_type="application/pdf")
    passage = Passage(document_id=doc.id, content="Perception is direct cognition.", page_number=4)
    
    assert source.id != ""
    assert doc.source_id == source.id
    assert passage.document_id == doc.id
    assert passage.ocr_confidence == 1.0

def test_argument_reconstruction_model():
    premise = Claim(statement="Sense-object contact occurred.", claim_type=ClaimType.DIRECT_SOURCE_CLAIM)
    conclusion = Claim(statement="Cognition is valid.", claim_type=ClaimType.INFERENCE)
    
    arg = Argument(
        conclusion_claim_id=conclusion.id,
        premise_claim_ids=[premise.id],
        pramana_type=PramanaType.PRATYAKSHA
    )
    
    assert arg.conclusion_claim_id == conclusion.id
    assert len(arg.premise_claim_ids) == 1

def test_evidence_relation_model():
    claim = Claim(statement="Perception is infallible.", claim_type=ClaimType.SCHOLARLY_INTERPRETATION)
    passage = Passage(document_id="doc_1", content="Perception can be erroneous in poor light.")
    
    evidence = Evidence(
        claim_id=claim.id,
        passage_id=passage.id,
        relation_type=RelationType.CONTRADICTS
    )
    
    assert evidence.relation_type == RelationType.CONTRADICTS