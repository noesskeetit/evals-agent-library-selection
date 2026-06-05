from evals_agent.runners.judge_config import (
    CLOUDRU_FM_DEFAULT_BASE_URL,
    CLOUDRU_FM_DEFAULT_MAX_TOKENS,
    CLOUDRU_FM_DEFAULT_MODEL,
    CLOUDRU_FM_DEFAULT_REASONING_EFFORT,
    cloudru_host_is_in_no_proxy,
    load_dotenv,
    resolve_judge_config,
)


def test_cloudru_config_uses_fm_api_key_alias_and_reasoning_defaults(monkeypatch):
    monkeypatch.setenv("EVALS_JUDGE_PROVIDER", "cloudru_fm")
    monkeypatch.setenv("FM_API_KEY", "secret-value")
    monkeypatch.delenv("CLOUDRU_FM_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDRU_FM_MODEL", raising=False)
    monkeypatch.setenv("no_proxy", "localhost,foundation-models.api.cloud.ru")
    monkeypatch.delenv("CLOUDRU_FM_BASE_URL", raising=False)

    config = resolve_judge_config()

    assert config.provider == "cloudru_fm"
    assert config.base_url == CLOUDRU_FM_DEFAULT_BASE_URL
    assert config.model == CLOUDRU_FM_DEFAULT_MODEL
    assert config.api_key == "secret-value"
    assert config.max_tokens == CLOUDRU_FM_DEFAULT_MAX_TOKENS
    assert config.reasoning_effort == CLOUDRU_FM_DEFAULT_REASONING_EFFORT
    assert "api_key" not in config.redacted_dict()
    assert config.missing_reason() is None


def test_cloudru_config_requires_key_and_auto_sets_no_proxy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVALS_JUDGE_PROVIDER", "cloudru_fm")
    monkeypatch.delenv("FM_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDRU_FM_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDRU_FM_MODEL", raising=False)
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")

    config = resolve_judge_config()

    assert "FM_API_KEY/CLOUDRU_FM_API_KEY is missing" in config.missing_reason()
    assert "foundation-models.api.cloud.ru is not in no_proxy" not in config.missing_reason()


def test_cloudru_no_proxy_accepts_parent_domain(monkeypatch):
    monkeypatch.setenv("no_proxy", "localhost,.api.cloud.ru")
    monkeypatch.delenv("NO_PROXY", raising=False)

    assert cloudru_host_is_in_no_proxy("https://foundation-models.api.cloud.ru/v1")


def test_load_dotenv_reads_fm_key_without_overriding_existing_env(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "FM_API_KEY=from-dotenv",
                "CLOUDRU_FM_MODEL=deepseek-ai/DeepSeek-V4-Pro",
                "CLOUDRU_FM_MAX_TOKENS=50000",
                "QUOTED_VALUE='keeps spaces'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FM_API_KEY", "from-process")
    monkeypatch.delenv("CLOUDRU_FM_MODEL", raising=False)
    monkeypatch.delenv("CLOUDRU_FM_MAX_TOKENS", raising=False)
    monkeypatch.delenv("QUOTED_VALUE", raising=False)

    loaded = load_dotenv(env_path)

    assert loaded["FM_API_KEY"] == "skipped"
    assert loaded["CLOUDRU_FM_MODEL"] == "set"
    assert loaded["CLOUDRU_FM_MAX_TOKENS"] == "set"
    assert loaded["QUOTED_VALUE"] == "set"
    assert "from-dotenv" not in repr(loaded)
    assert "from-process" not in repr(loaded)
    assert resolve_judge_config().api_key == "from-process"


def test_resolve_cloudru_config_loads_dotenv_and_sets_no_proxy(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("FM_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVALS_JUDGE_PROVIDER", "cloudru_fm")
    monkeypatch.delenv("FM_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDRU_FM_API_KEY", raising=False)
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
    monkeypatch.delenv("NO_PROXY", raising=False)

    config = resolve_judge_config()

    assert config.api_key == "from-dotenv"
    assert config.missing_reason() is None
    assert cloudru_host_is_in_no_proxy(CLOUDRU_FM_DEFAULT_BASE_URL)
