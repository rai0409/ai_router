from .deepseek_local import DeepSeekLocal


class DeepSeekCoder(DeepSeekLocal):
    def __init__(self):
        super().__init__(
            base_url="http://localhost:8001",
            model="deepseek-coder-v2-lite",
            temperature=0.2,
            max_tokens=4096,
        )
