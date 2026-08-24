import pytest
from pydantic import ValidationError
from backend.app.core.config import Settings, RuntimeProfile

def test_default_configuration_loads():
    settings = Settings()
    assert settings.PROJECT_NAME == "Anvikshiki"
    assert settings.RUNTIME_PROFILE in [RuntimeProfile.DEVELOPMENT, RuntimeProfile.CPU, RuntimeProfile.GPU, RuntimeProfile.TEST]
    # Ensure secrets/DB URLs are not accidentally logged by validating the repr
    assert "password" not in str(settings.model_dump(exclude={"DATABASE_URL"}))

def test_hardware_degradation_validation():
    # Should pass normally
    gpu_settings = Settings(RUNTIME_PROFILE=RuntimeProfile.GPU, OLLAMA_MODEL="llama3:70b")
    assert gpu_settings.OLLAMA_MODEL == "llama3:70b"

    # Should fail due to CPU limitations on large models
    with pytest.raises(ValidationError) as exc_info:
        Settings(RUNTIME_PROFILE=RuntimeProfile.CPU, OLLAMA_MODEL="llama3:70b")
    
    assert "CPU profile active" in str(exc_info.value)

def test_invalid_profile_raises_error():
    with pytest.raises(ValidationError):
        Settings(RUNTIME_PROFILE="quantum_computer")