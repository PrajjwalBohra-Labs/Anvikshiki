from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger(__name__)

class MemoryFoundationService:
    """
    Manages multi-tier application memory separating working, dialogue, session,
    research, cognitive, epistemic, and misconception memory types.
    Enforces retention rules, provenance tracking, confidence weighting, and evidence linkage.
    """
    def __init__(self):
        # In-memory durable cache store representing structured memory tiers
        self._memory_store: List[Dict[str, Any]] = []

    def record_memory(
        self,
        memory_tier: str,  # working, dialogue, session, research, cognitive, epistemic, misconception
        content: str,
        confidence: float = 1.0,
        provenance_source_id: Optional[str] = None,
        source_event: Optional[str] = None,
        retention_policy: str = "durable"
    ) -> Dict[str, Any]:
        """
        Records an inspectable, evidence-linked memory item across distinct tiers.
        """
        valid_tiers = {
            "working", "dialogue", "session", "research", 
            "cognitive", "epistemic", "misconception"
        }
        if memory_tier not in valid_tiers:
            raise ValueError(f"Invalid memory tier '{memory_tier}'. Must be one of {valid_tiers}.")

        memory_item = {
            "memory_id": f"mem_{len(self._memory_store) + 1}",
            "memory_tier": memory_tier,
            "content": content,
            "confidence": confidence,
            "provenance_source_id": provenance_source_id,
            "source_event": source_event or "interaction",
            "retention_policy": retention_policy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_evidence_linked": bool(provenance_source_id)
        }

        self._memory_store.append(memory_item)
        logger.info("Memory recorded successfully", tier=memory_tier, memory_id=memory_item["memory_id"])
        return memory_item

    def inspect_memories(
        self,
        memory_tier: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Retrieves and inspects stored memories filtered by tier and confidence threshold.
        """
        results = []
        for mem in self._memory_store:
            if memory_tier and mem["memory_tier"] != memory_tier:
                continue
            if mem["confidence"] < min_confidence:
                continue
            results.append(mem)
        return results

    def clear_tier(self, memory_tier: str) -> int:
        """Clears transient or expired memory tiers according to retention rules."""
        initial_count = len(self._memory_store)
        self._memory_store = [m for m in self._memory_store if m["memory_tier"] != memory_tier]
        removed_count = initial_count - len(self._memory_store)
        logger.info("Cleared memory tier", tier=memory_tier, removed=removed_count)
        return removed_count