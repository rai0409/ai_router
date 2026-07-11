# providers/claude_provider.py
#
# Router から呼ばれる Claude 用 Provider 実装の例。
# BaseProvider は既存の抽象クラスを想定。

from __future__ import annotations

from typing import Any

from .base import BaseProvider
from .claude_api import ClaudeProvider


class ClaudeSonnetProvider(BaseProvider):
    """
    Claude 3.5 Sonnet を使う Provider 実装例。
    router.py 側では name="claude_sonnet" で登録して使う想定。
    """

    name = "claude_sonnet"

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Router から呼ばれるエントリポイント。

        Parameters
        ----------
        system_prompt : str
            Claude の system プロンプト。
        user_prompt : str
            Claude へのメイン入力。
        kwargs : Any
            将来の拡張用（max_tokens, temperature などを渡せるように）。

        Returns
        -------
        str
            Claude の出力テキスト。
        """
        max_tokens = kwargs.get("max_tokens", 4096)
        temperature = kwargs.get("temperature", 0.2)

        model = str(kwargs.get("model", "claude-4-5-sonnet-latest"))

        provider = ClaudeProvider(
            model=model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        return provider.chat(
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=max_tokens,
        )
