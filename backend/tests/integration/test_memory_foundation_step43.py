import pytest
from backend.app.application.memory.memory_foundation import MemoryFoundationService

@pytest.mark.asyncio
async def test_memory_foundation_tiers_and_provenance():
    service = MemoryFoundationService()

    # 1. Record memories across distinct tiers with provenance & confidence
    m1 = service.record_memory(
        memory_tier="epistemic",
        content="User accepts Nyaya realism regarding perceptual objects.",
        confidence=0.92,
        provenance_source_id="source_nyaya_01",
        source_event="Dialogue turn 4"
    )
    assert m1["memory_id"] is not None
    assert m1["is_evidence_linked"] is True

    m2 = service.record_memory(
        memory_tier="working",
        content="Active search query parameters for Buddhist epistemology.",
        confidence=1.0,
        retention_policy="transient"
    )
    assert m2["memory_tier"] == "working"

    # 2. Inspect memories by tier
    epistemic_memories = service.inspect_memories(memory_tier="epistemic", min_confidence=0.9)
    assert len(epistemic_memories) == 1
    assert epistemic_memories[0]["provenance_source_id"] == "source_nyaya_01"

    # 3. Test invalid memory tier validation
    with pytest.raises(ValueError, match="Invalid memory tier"):
        service.record_memory(memory_tier="invalid_tier", content="Bad memory")

    # 4. Test retention clearing rule
    cleared_count = service.clear_tier("working")
    assert cleared_count == 1
    assert len(service.inspect_memories(memory_tier="working")) == 0