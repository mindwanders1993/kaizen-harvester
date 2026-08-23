import json
import os
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClientWrapper:
    """Unified client wrapper supporting OpenAI and Anthropic SDKs with structured Pydantic outputs."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        mock_client: Optional[Any] = None,
    ):
        self.mock_client = mock_client
        self.provider = provider or ("anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or ("claude-3-7-sonnet-20250219" if self.provider == "anthropic" else "gpt-4o")

        self._openai_client = None
        self._anthropic_client = None

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=self.api_key)
        return self._openai_client

    def _get_anthropic_client(self):
        if self._anthropic_client is None:
            from anthropic import Anthropic

            self._anthropic_client = Anthropic(api_key=self.api_key)
        return self._anthropic_client

    def structured_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: float = 0.0,
    ) -> T:
        """Invokes LLM and returns structured output validated into response_model."""
        if self.mock_client:
            return self.mock_client.structured_call(system_prompt, user_prompt, response_model)

        if not self.api_key:
            raise ValueError("No LLM API key configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY.")

        if self.provider == "openai":
            client = self._get_openai_client()
            completion = client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_model,
                temperature=temperature,
            )
            return completion.choices[0].message.parsed

        elif self.provider == "anthropic":
            client = self._get_anthropic_client()
            schema_json = json.dumps(response_model.model_json_schema())
            full_system = (
                f"{system_prompt}\n\nYou MUST respond ONLY with valid JSON matching this schema:\n{schema_json}"
            )
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                system=full_system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = response.content[0].text
            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            data = json.loads(raw_text.strip())
            return response_model.model_validate(data)

        raise ValueError(f"Unsupported LLM provider: {self.provider}")
