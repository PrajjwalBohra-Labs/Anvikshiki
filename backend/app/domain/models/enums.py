from enum import Enum

class SourceType(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    TRANSLATION = "TRANSLATION"
    COMMENTARY = "COMMENTARY"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    UNVERIFIED = "UNVERIFIED"
    # Compatibility names used by older callers; they map to the existing
    # secondary-source database value and require no new PostgreSQL enum value.
    SCHOLARLY_SECONDARY = "SECONDARY"
    SCIENTIFIC_STUDY = "SECONDARY"

class SourceRelationshipType(str, Enum):
    TRANSLATION_OF = "TRANSLATION_OF"
    COMMENTARY_ON = "COMMENTARY_ON"
    INTERPRETATION_OF = "INTERPRETATION_OF"
    EDITION_OF = "EDITION_OF"

class ClaimType(str, Enum):
    DIRECT_SOURCE_CLAIM = "DIRECT_SOURCE_CLAIM"
    TRANSLATION = "TRANSLATION"
    SCHOLARLY_INTERPRETATION = "SCHOLARLY_INTERPRETATION"
    SCIENTIFIC_FINDING = "SCIENTIFIC_FINDING"
    MODEL_SYNTHESIS = "MODEL_SYNTHESIS"
    INFERENCE = "INFERENCE"
    ANALOGY = "ANALOGY"
    HYPOTHESIS = "HYPOTHESIS"
    SPECULATION = "SPECULATION"
    UNCERTAIN = "UNCERTAIN"

class PramanaType(str, Enum):
    PRATYAKSHA = "pratyaksha"  # Perception
    ANUMANA = "anumana"        # Inference
    UPAMANA = "upamana"        # Comparison
    SHABDA = "shabda"          # Testimony
    ARTHAPATTI = "arthapatti"  # Postulation
    ANUPALABDHI = "anupalabdhi"# Non-apprehension

class RelationType(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    QUALIFIES = "QUALIFIES"

class EvidenceStatus(str, Enum):
    SUPPORTED = "supported"
    PLAUSIBLE = "plausible"
    CONTESTED = "contested"
    WEAKLY_SUPPORTED = "weakly_supported"
    UNRESOLVED = "unresolved"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ProvenanceNodeType(str, Enum):
    SOURCE = "SOURCE"
    DOCUMENT = "DOCUMENT"
    DOCUMENT_VERSION = "DOCUMENT_VERSION"
    PAGE = "PAGE"
    PASSAGE = "PASSAGE"
    CLAIM = "CLAIM"
    EVIDENCE = "EVIDENCE"
    SPECIALIST_ANALYSIS = "SPECIALIST_ANALYSIS"
    VALIDATION = "VALIDATION"
    RESEARCH_RUN = "RESEARCH_RUN"
    SYNTHESIS = "SYNTHESIS"


class ProvenanceRelationType(str, Enum):
    CONTAINS = "CONTAINS"
    HAS_VERSION = "HAS_VERSION"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    QUALIFIES = "QUALIFIES"
    CITES = "CITES"
    DERIVES_FROM = "DERIVES_FROM"
    VALIDATED_BY = "VALIDATED_BY"
    CONTRIBUTES_TO = "CONTRIBUTES_TO"
    PRODUCES = "PRODUCES"
    HAS_ANALYSIS = "HAS_ANALYSIS"
    HAS_VALIDATION = "HAS_VALIDATION"
    HAS_EVIDENCE = "HAS_EVIDENCE"
    VALIDATES = "VALIDATES"
