# ~/ai_router/providers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseProvider(ABC):
    """すべてのプロバイダの共通インタフェース"""

    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        messages: OpenAI / Anthropic 互換の
          [{"role": "user"|"assistant"|"system", "content": "..."}, ...]
        を想定
        """
        raise NotImplementedError
