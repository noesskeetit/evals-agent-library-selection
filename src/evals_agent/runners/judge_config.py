from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


CLOUDRU_FM_DEFAULT_BASE_URL = "https://foundation-models.api.cloud.ru/v1"
CLOUDRU_FM_DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
CLOUDRU_FM_DEFAULT_MAX_TOKENS = 50_000
CLOUDRU_FM_DEFAULT_REASONING_EFFORT = "high"
CLOUDRU_FM_HOST = "foundation-models.api.cloud.ru"


def _strip_dotenv_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_dotenv(path: str | Path = ".env") -> dict[str, str]:
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()

        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if key in os.environ:
            loaded[key] = "skipped"
            continue

        os.environ[key] = _strip_dotenv_value(value)
        loaded[key] = "set"
    return loaded


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    return int(raw)


def _no_proxy_entries() -> list[str]:
    raw = ",".join(
        value
        for value in (os.environ.get("no_proxy"), os.environ.get("NO_PROXY"))
        if value
    )
    return [entry.strip().lower() for entry in raw.split(",") if entry.strip()]


def _append_env_csv(name: str, value: str) -> None:
    current = os.environ.get(name)
    if not current:
        os.environ[name] = value
        return
    entries = [entry.strip() for entry in current.split(",") if entry.strip()]
    if value not in entries:
        os.environ[name] = ",".join([*entries, value])


def _host_matches_no_proxy(host: str, entry: str) -> bool:
    normalized_entry = entry.lstrip(".")
    return host == normalized_entry or host.endswith(f".{normalized_entry}")


def cloudru_host_is_in_no_proxy(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    if not host:
        return False
    return any(
        entry == "*" or _host_matches_no_proxy(host, entry)
        for entry in _no_proxy_entries()
    )


def ensure_cloudru_host_in_no_proxy(base_url: str) -> None:
    if cloudru_host_is_in_no_proxy(base_url):
        return
    host = (urlparse(base_url).hostname or "").lower()
    if host != CLOUDRU_FM_HOST:
        return
    _append_env_csv("no_proxy", host)
    _append_env_csv("NO_PROXY", host)


@dataclass(frozen=True)
class JudgeConfig:
    provider: str
    api_key: str | None
    base_url: str | None
    model: str
    max_tokens: int
    reasoning_effort: str | None

    def missing_reason(self) -> str | None:
        reasons: list[str] = []
        if self.provider == "cloudru_fm":
            if not self.api_key:
                reasons.append("FM_API_KEY/CLOUDRU_FM_API_KEY is missing")
            if not self.base_url:
                reasons.append("CLOUDRU_FM_BASE_URL is missing")
            elif not cloudru_host_is_in_no_proxy(self.base_url):
                reasons.append("foundation-models.api.cloud.ru is not in no_proxy")
        elif not self.api_key:
            reasons.append("OPENAI_API_KEY is missing")
        return "; ".join(reasons) if reasons else None

    def redacted_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "reasoning_effort": self.reasoning_effort,
            "cloudru_host_in_no_proxy": (
                cloudru_host_is_in_no_proxy(self.base_url)
                if self.provider == "cloudru_fm" and self.base_url
                else None
            ),
        }


def resolve_judge_config() -> JudgeConfig:
    load_dotenv()
    provider = os.environ.get("EVALS_JUDGE_PROVIDER")
    if provider is None:
        provider = "cloudru_fm"
    provider = provider.lower()

    if provider == "cloudru_fm":
        base_url = os.environ.get("CLOUDRU_FM_BASE_URL", CLOUDRU_FM_DEFAULT_BASE_URL)
        ensure_cloudru_host_in_no_proxy(base_url)
        return JudgeConfig(
            provider="cloudru_fm",
            api_key=os.environ.get("FM_API_KEY") or os.environ.get("CLOUDRU_FM_API_KEY"),
            base_url=base_url,
            model=os.environ.get("CLOUDRU_FM_MODEL", CLOUDRU_FM_DEFAULT_MODEL),
            max_tokens=_env_int("CLOUDRU_FM_MAX_TOKENS", CLOUDRU_FM_DEFAULT_MAX_TOKENS),
            reasoning_effort=os.environ.get(
                "CLOUDRU_FM_REASONING_EFFORT",
                CLOUDRU_FM_DEFAULT_REASONING_EFFORT,
            ),
        )

    return JudgeConfig(
        provider="openai",
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        max_tokens=_env_int("OPENAI_MAX_TOKENS", 4096),
        reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT"),
    )
