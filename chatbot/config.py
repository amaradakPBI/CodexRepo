from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


SYSTEM_PROMPT_PRESETS = {
    "General Assistant": "You are a helpful assistant.",
    "Data Analyst": "You are a precise data analyst who explains assumptions clearly.",
    "Code Helper": "You are a senior coding assistant focused on practical fixes.",
}


@dataclass(frozen=True)
class AppConfig:
    provider: str
    default_model: str
    default_temperature: float
    max_tokens: int
    streaming_enabled: bool
    api_base: str | None
    openai_api_key: str | None
    anthropic_api_key: str | None
    azure_endpoint: str | None
    azure_api_version: str | None
    azure_api_key: str | None
    max_upload_mb: int
    log_level: str
    persist_to_disk: bool
    storage_dir: Path
    log_file: Path
    min_submit_interval_ms: int


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def load_config(repo_root: Path) -> AppConfig:
    return AppConfig(
        provider=os.getenv("PROVIDER", "openai").lower(),
        default_model=os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),
        default_temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("MAX_TOKENS", "512")),
        streaming_enabled=env_bool("STREAMING_ENABLED", True),
        api_base=os.getenv("API_BASE"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        azure_api_key=os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("API_KEY"),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "1")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        persist_to_disk=env_bool("PERSIST_TO_DISK", True),
        storage_dir=repo_root / "data" / "conversations",
        log_file=repo_root / "logs" / "chatbot.log",
        min_submit_interval_ms=int(os.getenv("MIN_SUBMIT_INTERVAL_MS", "1000")),
    )
