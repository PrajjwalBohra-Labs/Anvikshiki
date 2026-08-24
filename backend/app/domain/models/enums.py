from enum import Enum

class SourceType(str, Enum):
    PRIMARY = "PRIMARY"
    TRANSLATION = "TRANSLATION"
    TRADITIONAL_COMMENTARY = "TRADITIONAL_COMMENTARY"
    SCHOLARLY_SECONDARY = "SCHOLARLY_SECONDARY"
    SCIENTIFIC_STUDY = "SCIENTIFIC_STUDY"
    REVIEW_OR_META_ANALYSIS = "REVIEW_OR_META_ANALYSIS"
    INSTITUTIONAL = "INSTITUTIONAL"
    GENERAL_REFERENCE = "GENERAL_REFERENCE"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    UNVERIFIED = "UNVERIFIED"

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

class EvidenceStatus(str, Enum):
    SUPPORTED = "supported"
    PLAUSIBLE = "plausible"
    CONTESTED = "contested"
    WEAKLY_SUPPORTED = "weakly_supported"
    UNRESOLVED = "unresolved"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"

class PramanaType(str, Enum):
    PRATYAKSHA = "pratyaksha"  # Perception
    ANUMANA = "anumana"        # Inference
    UPAMANA = "upamana"        # Analogy/Comparison
    SHABDA = "shabda"          # Verbal/Authoritative Testimony
    ARTHAPATTI = "arthapatti"  # Postulation/Presumption
    ANUPALABDHI = "anupalabdhi"# Non-perception
