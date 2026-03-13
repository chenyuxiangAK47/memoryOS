from __future__ import annotations

import os

from runtime.wrappers.base import BaseModelWrapper


class OpenAIWrapper(BaseModelWrapper):
    """Thin wrapper: prompt -> OpenAI chat completion -> response text."""

    def __init__(self, model: str = "gpt-4o-mini"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model or "gpt-4o-mini"

    def generate(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = resp.choices[0].message.content if resp.choices else None
        return (content or "").strip() or "(empty response)"
