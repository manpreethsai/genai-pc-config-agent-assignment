"""LLM client with retries, timeouts, and mock fallback. Supports multiple providers."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv

from src.config import Settings
from src.prompts.templates import FEW_SHOT_EXAMPLES, REQUIREMENT_EXTRACTION_PROMPT, SELF_CRITIQUE_PROMPT, SYSTEM_PROMPT

load_dotenv()


class LLMClient:
    """Wrapper supporting multiple LLM providers: OpenAI, Anthropic, Groq, OpenRouter, and Google Gemini."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.use_mock = settings.use_mock_llm
        self.provider = self._detect_provider()
        
        if not self.use_mock:
            self._initialize_client()

    def _detect_provider(self) -> str:
        """Detect which provider to use based on available API keys.
        
        Priority order (free providers first, then paid, Gemini last):
        1. Groq (free)
        2. OpenRouter (free)
        3. OpenAI (paid)
        4. Anthropic (paid)
        5. Gemini (deprioritized)
        6. Mock (fallback)
        """
        if os.environ.get("GROQ_API_KEY"):
            return "groq"
        if os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.environ.get("GEMINI_API_KEY") or self.settings.gemini_api_key:
            return "gemini"
        return "mock"

    def _initialize_client(self) -> None:
        """Initialize the appropriate LLM client based on provider."""
        if self.provider == "gemini":
            import google.genai as genai
            genai.configure(api_key=self.settings.gemini_api_key)
        elif self.provider == "openai":
            pass
        elif self.provider == "anthropic":
            pass
        elif self.provider in ("groq", "openrouter"):
            pass

    def _chat(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if self.use_mock:
            return self._mock_response(messages, tools)

        if self.provider == "gemini":
            return self._chat_gemini(messages)
        elif self.provider == "openai":
            return self._chat_openai(messages)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages)
        elif self.provider == "groq":
            return self._chat_groq(messages)
        elif self.provider == "openrouter":
            return self._chat_openrouter(messages)
        else:
            return self._mock_response(messages, tools)

    def _chat_gemini(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call Google Gemini API."""
        import google.genai as genai

        system_prompt = ""
        user_content = ""
        for message in messages:
            if message["role"] == "system":
                system_prompt = message["content"]
            elif message["role"] == "user":
                user_content = message["content"]

        model = genai.GenerativeModel(
            self.settings.gemini_model,
            system_instruction=system_prompt or None,
        )
        generation_config = genai.GenerationConfig(
            temperature=self.settings.temperature,
            max_output_tokens=self.settings.max_tokens,
            response_mime_type="application/json",
        )

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                response = model.generate_content(
                    user_content,
                    generation_config=generation_config,
                    request_options={"timeout": self.settings.request_timeout},
                )
                content = (response.text or "").strip()
                return {"content": content, "tool_calls": []}
            except Exception as exc:  # noqa: BLE001 - graceful API failure handling required
                last_error = exc
                if attempt < self.settings.max_retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Gemini request failed after retries: {last_error}")

    def _chat_openai(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call OpenAI API."""
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                    response_format={"type": "json_object"},
                    messages=messages,
                    timeout=self.settings.request_timeout,
                )
                content = response.choices[0].message.content or ""
                return {"content": content, "tool_calls": []}
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.settings.max_retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"OpenAI request failed after retries: {last_error}")

    def _chat_anthropic(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call Anthropic Claude API."""
        from anthropic import Anthropic

        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                response = client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                    messages=messages,
                    timeout=self.settings.request_timeout,
                )
                content = response.content[0].text or ""
                return {"content": content, "tool_calls": []}
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.settings.max_retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Anthropic request failed after retries: {last_error}")

    def _chat_groq(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call Groq API (free provider using OpenAI SDK)."""
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                    messages=messages,
                    timeout=self.settings.request_timeout,
                )
                content = response.choices[0].message.content or ""
                return {"content": content, "tool_calls": []}
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.settings.max_retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Groq request failed after retries: {last_error}")

    def _chat_openrouter(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call OpenRouter API (free provider using OpenAI SDK)."""
        from openai import OpenAI

        api_key = os.environ.get("OPENROUTER_DEFAULT_KEY") or os.environ["OPENROUTER_API_KEY"]
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model="openrouter/free",
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                    messages=messages,
                    timeout=self.settings.request_timeout,
                )
                content = response.choices[0].message.content or ""
                return {"content": content, "tool_calls": []}
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.settings.max_retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"OpenRouter request failed after retries: {last_error}")

    def extract_requirements(self, user_input: str) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": REQUIREMENT_EXTRACTION_PROMPT},
            {"role": "user", "content": user_input},
        ]
        result = self._chat(messages)
        parsed = self._parse_json(result.get("content", "{}"))
        return self._sanitize_requirements(parsed)

    @staticmethod
    def _sanitize_requirements(requirements: dict[str, Any]) -> dict[str, Any]:
        """Ensure preferences and constraints are always lists of strings.
        
        Fixes cases where LLM returns dicts or other types instead of lists.
        """
        if not isinstance(requirements, dict):
            return requirements
        
        # Fix preferences
        if "preferences" in requirements:
            prefs = requirements["preferences"]
            if isinstance(prefs, dict):
                requirements["preferences"] = list(prefs.values()) if prefs else []
            elif not isinstance(prefs, list):
                requirements["preferences"] = [str(prefs)] if prefs else []
            else:
                requirements["preferences"] = [str(p) for p in prefs]
        
        # Fix constraints
        if "constraints" in requirements:
            cons = requirements["constraints"]
            if isinstance(cons, dict):
                requirements["constraints"] = list(cons.values()) if cons else []
            elif not isinstance(cons, list):
                requirements["constraints"] = [str(cons)] if cons else []
            else:
                requirements["constraints"] = [str(c) for c in cons]
        
        return requirements
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n" + FEW_SHOT_EXAMPLES},
            {
                "role": "user",
                "content": json.dumps({"user_input": user_input, "requirements": requirements}),
            },
        ]
        return self._chat(messages)

    def self_critique(self, draft_build: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SELF_CRITIQUE_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"requirements": requirements, "draft_build": draft_build}),
            },
        ]
        result = self._chat(messages)
        return self._parse_json(result.get("content", "{}"))

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {}

    def _mock_response(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        user_blob = messages[-1]["content"].lower() if messages else ""

        if "extract structured requirements" in messages[0]["content"].lower():
            budget = None
            for token in user_blob.replace(",", "").split():
                if token.startswith("$"):
                    try:
                        budget = float(token.replace("$", ""))
                    except ValueError:
                        pass
                elif token.isdigit() and int(token) >= 300:
                    budget = float(token)
            usage = "gaming" if "gaming" in user_blob or "1440p" in user_blob or "4k" in user_blob else "general"
            if "office" in user_blob or "school" in user_blob or "browsing" in user_blob:
                usage = "office"
            if "video" in user_blob or "editing" in user_blob:
                usage = "content_creation"
            preferences = []
            if "amd" in user_blob:
                preferences.append("amd")
            if "nvidia" in user_blob or "geforce" in user_blob:
                preferences.append("nvidia")
            if "intel" in user_blob:
                preferences.append("intel")
            constraints = []
            if "rtx 4090" in user_blob and budget and budget < 1500:
                constraints.append("high_end_gpu_low_budget")
            return {
                "content": json.dumps(
                    {
                        "usage": usage,
                        "budget_usd": budget,
                        "preferences": preferences,
                        "constraints": constraints,
                        "notes": user_blob[:200],
                    }
                )
            }

        if "review the draft" in messages[0]["content"].lower():
            return {
                "content": json.dumps(
                    {
                        "approved": "high_end_gpu_low_budget" not in user_blob,
                        "issues": ["Budget too low for requested GPU tier"] if "4090" in user_blob else [],
                        "revised_suggestions": ["Lower GPU tier or increase budget"] if "4090" in user_blob else [],
                    }
                )
            }

        return {"content": json.dumps({"assistant_message": "Mock planner ready."}), "tool_calls": []}
