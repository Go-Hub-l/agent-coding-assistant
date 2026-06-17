"""Configuration management — loads settings from .env and exposes typed config."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class AgentModelConfig:
    """Per-agent model configuration."""

    orchestrator: str = "deepseek-v4-pro"
    pm: str = "deepseek-v4-pro"
    architect: str = "deepseek-v4-pro"
    coder: str = "deepseek-v4-pro"
    reviewer: str = "deepseek-v4-pro"
    tester: str = "deepseek-v4-pro"


@dataclass
class Config:
    """Application configuration loaded from environment / .env."""

    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    models: AgentModelConfig = field(default_factory=AgentModelConfig)
    max_feedback_retries: int = 3


def load_config(env_path: Path | None = None) -> Config:
    """Load configuration from .env file and environment variables."""
    if env_path and env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

    return Config(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        models=AgentModelConfig(
            orchestrator=os.getenv("ORCHESTRATOR_MODEL", "deepseek-v4-pro"),
            pm=os.getenv("PM_MODEL", "deepseek-v4-pro"),
            architect=os.getenv("ARCHITECT_MODEL", "deepseek-v4-pro"),
            coder=os.getenv("CODER_MODEL", "deepseek-v4-pro"),
            reviewer=os.getenv("REVIEWER_MODEL", "deepseek-v4-pro"),
            tester=os.getenv("TESTER_MODEL", "deepseek-v4-pro"),
        ),
        max_feedback_retries=int(os.getenv("MAX_FEEDBACK_RETRIES", "3")),
    )
