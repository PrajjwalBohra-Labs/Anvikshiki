from typing import List, Tuple
from backend.app.domain.models.argument import InferenceRelation
from backend.app.domain.models.evidence import Claim

class ContradictionDetector:
    # Key epistemological negation / conflict pairs
    CONTRADICTION_PAIRS = [
        ("inherently valid", "inherently invalid"),
        ("direct perception", "cannot perceive"),
        ("eternal", "non-eternal"),
        ("causation is real", "causation is illusion"),
        ("independent reality", "mind-only"),
        ("proves causation", "only correlation")
    ]

    @classmethod
    def evaluate_relation(cls, claim_a: str, claim_b: str) -> InferenceRelation:
        a_lower = claim_a.lower()
        b_lower = claim_b.lower()

        for term1, term2 in cls.CONTRADICTION_PAIRS:
            if (term1 in a_lower and term2 in b_lower) or (term2 in a_lower and term1 in b_lower):
                return InferenceRelation.CONTRADICTS

        # Check qualification markers
        qualifiers = ["partially", "only when", "under specific conditions", "qualified by", "with respect to"]
        if any(q in a_lower or q in b_lower for q in qualifiers):
            return InferenceRelation.QUALIFIES

        # Overlapping substantive keywords indicate support
        words_a = set(a_lower.split())
        words_b = set(b_lower.split())
        overlap = words_a.intersection(words_b)
        if len(overlap) >= 3:
            return InferenceRelation.SUPPORTS

        return InferenceRelation.INDEPENDENT

class EvidenceGraph:
    def __init__(self):
        self.nodes: Dict[str, Claim] = {}
        self.edges: List[Tuple[str, str, InferenceRelation]] = []

    def add_claim(self, claim: Claim):
        self.nodes[claim.id] = claim

    def build_relations(self):
        claim_list = list(self.nodes.values())
        for i in range(len(claim_list)):
            for j in range(i + 1, len(claim_list)):
                c1, c2 = claim_list[i], claim_list[j]
                rel = ContradictionDetector.evaluate_relation(c1.statement, c2.statement)
                if rel != InferenceRelation.INDEPENDENT:
                    self.edges.append((c1.id, c2.id, rel))