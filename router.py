# ~/ai_router/router.py
import json
import os
from pathlib import Path
from typing import Dict

from providers.llama_local import LlamaLocal
from providers.claude_api import ClaudeProvider

# -----------------------------
#  プロジェクトの絶対パス取得
# -----------------------------
ROOT = Path(__file__).resolve().parent
RULE_DIR = ROOT / "rules"


def load_rules(filename: str) -> Dict:
    """rules ディレクトリから JSON を確実に読み込む"""
    path = RULE_DIR / filename

    if not path.exists():
        print(f"[警告] ルールファイルが見つかりません: {path}")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ルール読み込み（絶対パス）
SPEC_RULES = load_rules("spec_rules.json")
CODE_RULES = load_rules("code_rules.json")

# -----------------------------
# Providers 登録
# -----------------------------

PROVIDERS = {}

# ローカル Llama
PROVIDERS["llama_local"] = LlamaLocal()

# Claude Haiku（構造化）
try:
    PROVIDERS["claude_haiku"] = ClaudeProvider(
        model="claude-3-haiku-20240307",
        max_tokens=2048,
        system_prompt="You are a cost-efficient assistant for structuring and checking specifications and code.",
    )
except Exception:
    pass

# Claude Sonnet（論理チェック）
try:
    PROVIDERS["claude_sonnet"] = ClaudeProvider(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system_prompt="You are a high-precision reviewer for specifications and code.",
    )
except Exception:
    pass


# -----------------------------
# Router 本体
# -----------------------------

def run(task_type: str, section: str, content: str) -> str:
    """task_type と rules に従って Provider を自動選択"""
    if task_type == "spec":
        rules = SPEC_RULES
    elif task_type == "code":
        rules = CODE_RULES
    else:
        raise ValueError(f"Unknown task_type: {task_type}")

    # spec_rules.json の内部は {"spec": {...}} なので一段深い
    if task_type in rules:
        rules = rules[task_type]

    if section not in rules:
        raise KeyError(
            f"Section '{section}' not found in rules for task_type '{task_type}'. "
            f"利用可能: {list(rules.keys())}"
        )

    provider_name = rules[section]
    provider = PROVIDERS.get(provider_name)

    if provider is None:
        raise ValueError(f"Provider '{provider_name}' が未定義です。")

    messages = [{"role": "user", "content": content}]
    return provider.chat(messages)


# -----------------------------
# サンプル実行（Llamaのみ）
# -----------------------------

if __name__ == "__main__":
    os.makedirs(ROOT / "spec_output", exist_ok=True)

    llama = LlamaLocal()
    messages = [
        {
            "role": "user",
            "content": "日本語で、AIルーターの仕様書アウトラインを簡潔に作ってください。",
        }
    ]

    outline = llama.chat(messages, max_tokens=256)
    out_path = ROOT / "spec_output" / "example_outline_llama.md"
    out_path.write_text(outline, encoding="utf-8")

    print("Router ready.")
    print("出力先:", out_path)
