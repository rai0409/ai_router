# ~/ai_router/providers/claude_api_backup.py
import os
import requests
from typing import List, Dict, Any

class ClaudeProvider:
    def __init__(self, model="claude-3-5-sonnet-20240620", max_tokens=4096, system_prompt=None):
        self.model = model
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt

        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise RuntimeError("CLAUDE_API_KEY is not set.")

        # Claude の最新 API エンドポイント
        self.url = "https://api.anthropic.com/v1/messages"

        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages
        }

        if self.system_prompt:
            payload["system"] = self.system_prompt

        payload.update(kwargs)

        try:
            res = requests.post(self.url, headers=self.headers, json=payload)
            res.raise_for_status()
            data = res.json()
            return data["content"][0]["text"]

        except Exception as e:
            raise RuntimeError(
                f"Claude API request failed: {e} / response={getattr(e, 'response', None)}"
            )
