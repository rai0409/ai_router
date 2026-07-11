from .deepseek_local import DeepSeekLocal


class DeepSeekR1(DeepSeekLocal):
    def __init__(self):
        super().__init__(
            base_url="http://localhost:8002",
            model="deepseek-r1-distill",
            temperature=0.1,
            max_tokens=4096,
        )
