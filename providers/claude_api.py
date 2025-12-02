# providers/claude_api.py
#
# Claude 3 / 3.5 用の messages API ラッパー + ClaudeProvider クラス
# router.py の
#   from providers.claude_api import ClaudeProvider
# と
#   PROVIDERS["claude_haiku"] = ClaudeProvider(...)
#   PROVIDERS["claude_sonnet"] = ClaudeProvider(...)
# に対応した実装。

from __future__ import annotations

import os
from typing import List, Dict, Any

import requests


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ClaudeAPIError(Exception):
    """Claude API 呼び出し時のエラー用例外クラス。"""
    pass


def _get_api_key() -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeAPIError("環境変数 ANTHROPIC_API_KEY が設定されていません。")
    return api_key


def _build_headers() -> Dict[str, str]:
    api_key = _get_api_key()
    return {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }


class ClaudeProvider:
    """
    router.py から使われる Claude 用 Provider クラス。

    期待されているインタフェース:
      - __init__(model, max_tokens, system_prompt)
      - chat(messages: List[Dict[str, str]]) -> str

    messages の形式は OpenAI 風:
      [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    これを Anthropic の messages API にそのまま渡す。
    """

    def __init__(
        self,
        model: str,
        max_tokens: int = 4096,
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.temperature = temperature

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        router.run() から呼ばれるメインメソッド。

        Parameters
        ----------
        messages : list[dict]
            [{"role": "user", "content": "..."}] 形式のメッセージリスト。

        Returns
        -------
        str
            Claude が生成したテキスト。
        """
        headers = _build_headers()

        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": self.system_prompt,
            "messages": messages,
        }

        try:
            res = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )
        except requests.RequestException as e:
            raise ClaudeAPIError(f"Anthropic API への接続に失敗しました: {e}") from e

        if not res.ok:
            # 404 / 401 / 400 などはここで検知
            raise ClaudeAPIError(
                f"Anthropic API エラー: status={res.status_code}, body={res.text}"
            )

        data = res.json()

        # 期待レスポンス:
        # {
        #   "id": "...",
        #   "type": "message",
        #   "role": "assistant",
        #   "content": [
        #       {"type": "text", "text": "生成された本文"}
        #   ],
        #   ...
        # }
        try:
            first_content = data["content"][0]
            if first_content.get("type") != "text":
                raise ClaudeAPIError(
                    f"テキスト以外の content が返却されました: {first_content}"
                )
            return first_content["text"]
        except (KeyError, IndexError, TypeError) as e:
            raise ClaudeAPIError(
                f"予期しないレスポンス形式です: {data}"
            ) from e
