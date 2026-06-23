import json
from typing import Any

import httpx

from app.config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def prepare_messages(
        self, messages: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        prepared = [dict(message) for message in messages]
        if self.settings.llm_disable_thinking and prepared:
            last = prepared[-1]
            if last.get("role") == "user" and "/no_think" not in last.get(
                "content", ""
            ):
                last["content"] = f"{last.get('content', '')}\n/no_think"
        return prepared

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> str:
        prepared_messages = self.prepare_messages(messages)
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": prepared_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        async with httpx.AsyncClient(
            timeout=self.settings.llm_timeout_seconds
        ) as client:
            response = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    @staticmethod
    def parse_json(content: str) -> dict[str, Any]:
        value = content.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(value)
