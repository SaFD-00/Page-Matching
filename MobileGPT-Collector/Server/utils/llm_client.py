"""LLM client for OpenAI and Google Gemini APIs."""

import json
import time
from typing import Any, Optional

from openai import OpenAI

from ..config import (
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    MAX_RETRIES,
    RETRY_DELAY,
)

REASONING_MODEL_PREFIXES = frozenset(["gpt-5"])


class LLMClient:
    """Client for OpenAI and Google Gemini APIs."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        api_key: Optional[str] = None
    ):
        self.model = model
        self.reasoning_effort = reasoning_effort
        self._model_type = self._detect_model_type(model)

        if self._model_type == "google":
            self._init_google_client(api_key)
        else:
            self._init_openai_client(api_key)

    def _detect_model_type(self, model: str) -> str:
        if model.lower().startswith("gemini-"):
            return "google"
        return "openai"

    def _init_openai_client(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or OPENAI_API_KEY)

    def _init_google_client(self, api_key: Optional[str] = None):
        from google import genai
        self._google_client = genai.Client(api_key=api_key or GEMINI_API_KEY)

    def _is_reasoning_model(self) -> bool:
        model_lower = self.model.lower()
        return any(model_lower.startswith(prefix) for prefix in REASONING_MODEL_PREFIXES)

    def query(
        self,
        system_prompt: str,
        user_prompt: str,
        is_json: bool = True,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None
    ) -> Any:
        if self._model_type == "google":
            return self._query_google(system_prompt, user_prompt, is_json, max_tokens)
        return self._query_openai(system_prompt, user_prompt, is_json, temperature, max_tokens)

    def _query_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        is_json: bool = True,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None
    ) -> Any:
        messages = [
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        for attempt in range(MAX_RETRIES):
            try:
                kwargs = {"model": self.model, "messages": messages}
                if not self._is_reasoning_model():
                    kwargs["temperature"] = temperature
                if self.reasoning_effort != "none":
                    kwargs["reasoning_effort"] = self.reasoning_effort
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens
                if is_json:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content

                if is_json:
                    return self._parse_json(content)
                return content

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise RuntimeError(f"LLM query failed after {MAX_RETRIES} attempts: {e}")

    def _query_google(
        self,
        system_prompt: str,
        user_prompt: str,
        is_json: bool = True,
        max_tokens: Optional[int] = None
    ) -> Any:
        from google.genai import types

        for attempt in range(MAX_RETRIES):
            try:
                config_kwargs = {"system_instruction": system_prompt}
                if "gemini-3" in self.model.lower():
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW
                    )
                if max_tokens:
                    config_kwargs["max_output_tokens"] = max_tokens

                config = types.GenerateContentConfig(**config_kwargs)
                response = self._google_client.models.generate_content(
                    model=self.model, config=config, contents=user_prompt
                )
                content = response.text
                if is_json:
                    return self._parse_json(content)
                return content

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise RuntimeError(f"LLM query failed after {MAX_RETRIES} attempts: {e}")

    def _parse_json(self, content: str) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                try:
                    return json.loads(content[start:end].strip())
                except json.JSONDecodeError:
                    pass

        if "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                try:
                    return json.loads(content[start:end].strip())
                except json.JSONDecodeError:
                    pass

        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start = content.find(start_char)
            if start != -1:
                depth = 0
                for i, c in enumerate(content[start:], start):
                    if c == start_char:
                        depth += 1
                    elif c == end_char:
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(content[start:i+1])
                            except json.JSONDecodeError:
                                break

        raise ValueError(f"Could not parse JSON from response: {content[:200]}...")

    def query_dict(self, system_prompt: str, user_prompt: str, **kwargs) -> dict:
        result = self.query(system_prompt, user_prompt, is_json=True, **kwargs)
        if isinstance(result, dict):
            return result
        elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            return result[0]
        return {"result": result}
