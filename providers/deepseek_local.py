import requests
from typing import List, Dict, Any
from .base import BaseProvider


class DeepSeekLocal(BaseProvider):
    """
    llama-server 経由で DeepSeek 系 GGUF を叩く共通 Provider
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        res = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=300,
        )

        if not res.ok:
            raise RuntimeError(f"DeepSeek local error: {res.text}")

        data = res.json()
        return data["choices"][0]["message"]["content"]
