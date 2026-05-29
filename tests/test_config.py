from astra.config import AstraConfig


def test_provider_auto_uses_openai_when_key_exists(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("ASTRA_PROVIDER", raising=False)

    config = AstraConfig.load("missing-config.json")

    assert config.provider == "auto"
    assert config.active_provider == "openai"
    assert config.active_generation_model == "gpt-5-mini"


def test_provider_auto_uses_ollama_without_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ASTRA_PROVIDER", raising=False)

    config = AstraConfig.load("missing-config.json")

    assert config.provider == "auto"
    assert config.active_provider == "ollama"
    assert config.active_generation_model == "llama3.1:8b"
    assert config.generation_configured() is True


def test_explicit_ollama_provider(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ASTRA_PROVIDER", "ollama")
    monkeypatch.setenv("ASTRA_OLLAMA_MODEL", "llama3.1:8b")

    config = AstraConfig.load("missing-config.json")

    assert config.active_provider == "ollama"
    assert config.active_generation_model == "llama3.1:8b"
