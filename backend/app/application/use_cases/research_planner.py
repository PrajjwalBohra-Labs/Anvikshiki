from typing import List, Optional
from pydantic import BaseModel, Field

class SubQuestion(BaseModel):
    id: str
    question: str
    target_tradition: str = "general"
    focus_domain: str = "epistemology"

class ResearchPlan(BaseModel):
    original_query: str
    sub_questions: List[SubQuestion]
    depth: str = "standard"  # standard, deep_investigation

class ResearchPlanner:
    @staticmethod
    def plan_query(query: str) -> ResearchPlan:
        query_lower = query.lower()
        sub_questions = []

        # Analyze philosophical / epistemological keywords
        if "pratyaksha" in query_lower or "perception" in query_lower:
            sub_questions.append(
                SubQuestion(
                    id="sq_1",
                    question="How is direct perceptual cognition (pratyaksha) defined and justified?",
                    target_tradition="classical_indian",
                    focus_domain="epistemology"
                )
            )
            sub_questions.append(
                SubQuestion(
                    id="sq_2",
                    question="What empirical cognitive science models explain perceptual decision-making?",
                    target_tradition="modern_cognitive_science",
                    focus_domain="neuroscience"
                )
            )

        if "anumana" in query_lower or "inference" in query_lower or "logic" in query_lower:
            sub_questions.append(
                SubQuestion(
                    id="sq_3",
                    question="What constitutes invariable concomitance (vyapti) and valid inferential structure?",
                    target_tradition="classical_indian",
                    focus_domain="logic"
                )
            )

        # Fallback if no specific keyword matched
        if not sub_questions:
            sub_questions.append(
                SubQuestion(
                    id="sq_gen",
                    question=query,
                    target_tradition="comparative",
                    focus_domain="general_inquiry"
                )
            )

        return ResearchPlan(
            original_query=query,
            sub_questions=sub_questions,
            depth="deep_investigation" if len(sub_questions) > 1 else "standard"
        )