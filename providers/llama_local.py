# ~/ai_router/providers/llama_local.py
import time
import requests
from typing import List, Dict, Any

from .base import BaseProvider


DEFAULT_LLAMA_URL = "http://127.0.0.1:8000/v1/chat/completions"
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.4
REQUEST_TIMEOUT_SEC = 300

# モデルロード待ちなどで 503 が返ったとき用
MAX_RETRIES_WHEN_LOADING = 10
RETRY_SLEEP_SEC = 5


class LlamaLocal(BaseProvider):
    """
    llama.cpp の /v1/chat/completions に接続するローカルプロバイダ。

    - 事前に: llama-server -m ... --host 0.0.0.0 --port 8000 などで起動しておく
    """

    def __init__(self, url: str = DEFAULT_LLAMA_URL):
        self.url = url

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        payload: Dict[str, Any] = {
            "model": "llama",  # llama-server 側の model 名（デフォルト）
            "messages": messages,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "temperature": DEFAULT_TEMPERATURE,
        }
        # max_tokens, temperature など kwargs で上書き可能
        payload.update(kwargs)

        last_error_text = None

        for attempt in range(1, MAX_RETRIES_WHEN_LOADING + 1):
            try:
                res = requests.post(self.url, json=payload, timeout=REQUEST_TIMEOUT_SEC)
            except requests.RequestException as e:
                # ネットワークレベルのエラーは即終了
                raise RuntimeError(f"LlamaLocal request failed: {e}") from e

            # モデルロード中などで 503 が返るケース
            if res.status_code == 503:
                last_error_text = res.text
                if "Loading model" in res.text and attempt < MAX_RETRIES_WHEN_LOADING:
                    time.sleep(RETRY_SLEEP_SEC)
                    continue

                raise RuntimeError(f"LlamaLocal request failed (503): {res.text}")

            if not res.ok:
                raise RuntimeError(
                    f"LlamaLocal request failed: status={res.status_code}, body={res.text}"
                )

            data = res.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as e:
                raise RuntimeError(f"Unexpected LlamaLocal response: {data}") from e

        raise RuntimeError(f"LlamaLocal request failed after retries. last_error={last_error_text}")
