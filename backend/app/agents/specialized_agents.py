from typing import Dict, Any, List
from backend.app.agents.state import InquiryState
from backend.app.domain.models.enums import SourceType, ClaimType, EvidenceStatus, PramanaType
from backend.app.domain.models.evidence import SourceProvenance
from backend.app.application.use_cases.research_planner import ResearchPlanner
from backend.app.application.use_cases.source_critic import SourceCritic
from backend.app.application.use_cases.evidence_graph import ContradictionDetector

class SpecializedAgentNodes:

    @staticmethod
    def research_node(state: InquiryState) -> Dict[str, Any]:
        plan = ResearchPlanner.plan_query(state["query"])
        sub_qs = [sq.question for sq in plan.sub_questions]
        return {
            "sub_questions": sub_qs,
            "current_step": "research_completed"
        }

    @staticmethod
    def evidence_and_critic_node(state: InquiryState) -> Dict[str, Any]:
        claims = state.get("extracted_claims", [])
        critique_findings = []

        # Run source criticism over passages
        for p in state.get("retrieved_passages", []):
            prov = SourceProvenance(
                author=p.get("author"),
                original_language=p.get("original_language"),
                translator=p.get("translator"),
                translation_year=p.get("translation_year"),
                citation_string=p.get("citation_string", "Citation")
            )
            s_type = SourceType(p.get("source_type", SourceType.UNVERIFIED))
            findings = SourceCritic.criticize_source(prov, p.get("content", ""), s_type)
            critique_findings.extend([f.model_dump() for f in findings])

        return {
            "critique_findings": critique_findings,
            "current_step": "critique_completed"
        }

    @staticmethod
    def philosophical_analyst_node(state: InquiryState) -> Dict[str, Any]:
        claims = state.get("extracted_claims", [])
        arguments = []

        if claims:
            # Reconstruct argument premises and conclusion
            premises = [c.get("statement", "") for c in claims[:2]]
            conclusion = f"Primary conclusion derived from {len(premises)} established premises."
            arguments.append({
                "id": "arg_1",
                "conclusion": conclusion,
                "premises": premises,
                "pramana": PramanaType.PRATYAKSHA.value if any("perception" in p.lower() or "pratyaksha" in p.lower() for p in premises) else PramanaType.ANUMANA.value,
                "confidence": 0.85
            })

        return {
            "reconstructed_arguments": arguments,
            "current_step": "analysis_completed"
        }

    @staticmethod
    def challenger_node(state: InquiryState) -> Dict[str, Any]:
        counters = []
        uncertainties = []

        # Analyze potential contradictions or limitations
        for finding in state.get("critique_findings", []):
            if finding.get("risk_level") in ["medium", "high"]:
                counters.append(f"Challenger note: {finding.get('description')}")

        if not state.get("retrieved_passages"):
            uncertainties.append("Insufficient primary empirical or textual evidence retrieved to conclusively resolve inquiry.")

        return {
            "counterarguments": counters,
            "uncertainties": uncertainties,
            "current_step": "challenge_completed"
        }

    @staticmethod
    def dialogue_node(state: InquiryState) -> Dict[str, Any]:
        # Synthesize without fabricating authority
        query = state["query"]
        args = state.get("reconstructed_arguments", [])
        counters = state.get("counterarguments", [])
        uncertainties = state.get("uncertainties", [])

        synthesis_parts = [f"Investigating query: '{query}'"]
        
        if args:
            synthesis_parts.append(f"Argued position: {args[0].get('conclusion')}")
            for idx, p in enumerate(args[0].get("premises", [])):
                synthesis_parts.append(f"  [Premise {idx+1}]: {p}")

        if counters:
            synthesis_parts.append("Points of Critical Examination:")
            for c in counters:
                synthesis_parts.append(f"  - {c}")

        if uncertainties:
            synthesis_parts.append("Uncertainties & Epistemic Boundaries:")
            for u in uncertainties:
                synthesis_parts.append(f"  - {u}")

        return {
            "final_synthesis": "\n".join(synthesis_parts),
            "current_step": "complete"
        }