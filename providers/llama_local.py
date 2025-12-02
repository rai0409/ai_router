# ~/ai_router/providers/llama_local.py
import requests
from typing import List, Dict, Any

from .base import BaseProvider


class LlamaLocal(BaseProvider):
    """
    llama.cpp の /v1/chat/completions に接続するローカルプロバイダ
    - 事前に: ./llama-server -m ... --host 0.0.0.0 --port 8000 などで起動しておく
    """

    def __init__(self, url: str = "http://127.0.0.1:8000/v1/chat/completions"):
        self.url = url

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        payload: Dict[str, Any] = {
            "model": "llama",  # llama-server 側の model 名（デフォルト）
            "messages": messages,
        }
        # max_tokens など kwargs に渡されたものがあれば追加
        payload.update(kwargs)

        try:
            res = requests.post(self.url, json=payload, timeout=60)
            res.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"LlamaLocal request failed: {e}") from e

        data = res.json()
        # llama.cpp server の互換 API を想定
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected LlamaLocal response: {data}") from e
