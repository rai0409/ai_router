# providers/claude_api.py
#
# Claude 3 / 3.5 用の messages API ラッパー + ClaudeProvider クラス
# router.py の
#   from providers.claude_api import ClaudeProvider
# と
#   PROVIDERS["claude_haiku"] = ClaudeProvider(...)
#   PROVIDERS["claude_sonnet"] = ClaudeProvider(...)
# に対応した実装。
#
# 追加ポイント:
# - Prompt Caching 対応 (anthropic-beta ヘッダ, system content blocks)
# - system を文字列 / blocks の両方で扱えるように
# - chat() で max_tokens を一時的に上書き可能

from __future__ import annotations

import os
from typing import List, Dict, Any, Optional

import requests


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_PROMPT_CACHING_BETA = "prompt-caching-2024-07-31"


class ClaudeAPIError(Exception):
    """Claude API 呼び出し時のエラー用例外クラス。"""

    pass


def _get_api_key() -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeAPIError("環境変数 ANTHROPIC_API_KEY が設定されていません。")
    return api_key


def _build_headers(use_prompt_cache: bool = False) -> Dict[str, str]:
    """
    Anthropic API 用ヘッダを構築。

    Parameters
    ----------
    use_prompt_cache : bool
        Prompt Caching を有効化するかどうか。
    """
    api_key = _get_api_key()
    headers: Dict[str, str] = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    if use_prompt_cache:
        # Prompt Caching を使う場合に必要な beta フラグ
        headers["anthropic-beta"] = ANTHROPIC_PROMPT_CACHING_BETA
    return headers


class ClaudeProvider:
    """
    router.py から使われる Claude 用 Provider クラス。

    期待されているインタフェース:
      - __init__(model, max_tokens, system_prompt)
      - chat(messages: List[Dict[str, Any]], max_tokens: Optional[int] = None) -> str

    messages の形式は OpenAI 風:
      [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    これを Anthropic の messages API にそのまま渡す。
    """

    def __init__(
        self,
        model: str,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = "",
        temperature: float = 0.2,
        *,
        use_prompt_cache: bool = False,
        cached_system_blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Parameters
        ----------
        model : str
            利用する Claude モデル名。
        max_tokens : int, default 4096
            通常時の max_tokens。
        system_prompt : str | None
            system プロンプト（文字列）。Prompt Caching を使わない場合はこちらだけで OK。
        temperature : float, default 0.2
            出力のランダム性。
        use_prompt_cache : bool, keyword-only
            Prompt Caching 機能を使うかどうか。
        cached_system_blocks : list[dict] | None, keyword-only
            Prompt Caching 用に cache_control を含む system content blocks を直接指定したい場合。
        """
        self.model = model
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt or ""
        self.temperature = temperature
        self.use_prompt_cache = use_prompt_cache
        self.cached_system_blocks = cached_system_blocks

    def _build_system_payload(self) -> Optional[Any]:
        """
        system フィールドに渡す payload を構築。

        - cached_system_blocks があればそれを優先
        - それがなければ system_prompt を使う
          - use_prompt_cache=True の場合は、cache_control 付き content block に変換
          - そうでなければ従来通りの文字列 system として渡す
        """
        # 1) blocks が明示的に渡されている場合（最優先）
        if self.cached_system_blocks is not None:
            return self.cached_system_blocks

        # 2) 文字列の system_prompt を持っている場合
        if self.system_prompt:
            if self.use_prompt_cache:
                # Prompt Caching 用に block 化し、全文を ephemeral cache 対象にする例
                return [
                    {
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                # 従来通りの文字列 system
                return self.system_prompt

        # system なし
        return None

    def chat(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        router.run() から呼ばれるメインメソッド。

        Parameters
        ----------
        messages : list[dict]
            [{"role": "user", "content": "..."}] 形式のメッセージリスト。
        max_tokens : int | None
            呼び出しごとに max_tokens を一時的に上書きしたい場合に指定。

        Returns
        -------
        str
            Claude が生成したテキスト。
        """
        headers = _build_headers(use_prompt_cache=self.use_prompt_cache)

        system_payload = self._build_system_payload()

        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature,
            "messages": messages,
        }
        if system_payload is not None:
            payload["system"] = system_payload

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
            raise ClaudeAPIError(f"Anthropic API エラー: status={res.status_code}, body={res.text}")

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
            content_list = data["content"]
            if not content_list:
                raise ClaudeAPIError(f"content が空です: {data}")

            first_content = content_list[0]
            if first_content.get("type") != "text":
                raise ClaudeAPIError(f"テキスト以外の content が返却されました: {first_content}")
            return first_content["text"]
        except (KeyError, IndexError, TypeError) as e:
            raise ClaudeAPIError(f"予期しないレスポンス形式です: {data}") from e
