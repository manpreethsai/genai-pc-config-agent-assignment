"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH = PROJECT_ROOT.parent / "Computer_Components_Dataset-main" / "data" / "csv"


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    temperature: float
    max_tokens: int
    request_timeout: int
    max_retries: int
    max_input_chars: int
    dataset_path: Path
    log_dir: Path
    use_mock_llm: bool
    llm_provider: str

    @classmethod
    def from_env(cls) -> Settings:
        dataset_override = os.getenv("DATASET_PATH")
        dataset_path = Path(dataset_override) if dataset_override else DEFAULT_DATASET_PATH
        use_mock = os.getenv("USE_MOCK_LLM", "false").lower() in {"1", "true", "yes"}
        
        gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        
        has_groq = os.getenv("GROQ_API_KEY")
        has_openrouter = os.getenv("OPENROUTER_API_KEY")
        has_openai = os.getenv("OPENAI_API_KEY")
        has_anthropic = os.getenv("ANTHROPIC_API_KEY")
        
        detected_provider = "mock"
        if has_groq:
            detected_provider = "groq"
        elif has_openrouter:
            detected_provider = "openrouter"
        elif has_openai:
            detected_provider = "openai"
        elif has_anthropic:
            detected_provider = "anthropic"
        elif gemini_api_key:
            detected_provider = "gemini"

        if detected_provider == "mock" and not use_mock:
            use_mock = True

        return cls(
            gemini_api_key=gemini_api_key,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            max_input_chars=int(os.getenv("MAX_INPUT_CHARS", "8000")),
            dataset_path=dataset_path,
            log_dir=PROJECT_ROOT / "logs",
            use_mock_llm=use_mock,
            llm_provider=detected_provider,
        )


settings = Settings.from_env()
