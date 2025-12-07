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
#  consistency 用レビュー共通テンプレ
#  （Prompt Caching 対象）
# -----------------------------

CONSISTENCY_TEMPLATE = """
あなたは日本語のソフトウェア仕様書のレビュー専門家です。

【タスク】
与えられた仕様書ドラフトをレビューし、重要な問題だけを指摘します。

【レビュー観点】
- 要求と仕様の不整合
- 重要な観点の抜け漏れ
- 曖昧・多義的な表現
- 実装・運用上のリスク
- 想定外ケース・エッジケースの見落とし

【厳守事項】
- 挨拶や前置き、説明文は一切書かない。
- 下記フォーマット以外の文章は出力しない。
- 指摘は重要なものから最大10件まで。
- 全体で概ね1200文字以内に収める。
- 出力はすべて日本語。

【出力フォーマット】
1. 指摘一覧
   - No.1: 対象箇所の要約 / 問題点 / 影響 / 修正の方向性
   - No.2: ...
2. 改善提案の要約
3. 必要であれば見出し構成の改善案
""".strip()

CONSISTENCY_SYSTEM_BLOCKS = [
    {
        "type": "text",
        "text": CONSISTENCY_TEMPLATE,
        "cache_control": {"type": "ephemeral"},
    }
]

# -----------------------------
# Providers 登録
# -----------------------------

PROVIDERS: Dict[str, object] = {}

# ローカル Llama
PROVIDERS["llama_local"] = LlamaLocal()

# Claude Haiku（軽量な構造化・要約など）
try:
    PROVIDERS["claude_haiku"] = ClaudeProvider(
        model="claude-3-haiku-20240307",
        max_tokens=2048,
        system_prompt=(
            "You are a cost-efficient assistant for structuring and checking "
            "specifications and code. "
            "When the user is Japanese, reply in Japanese. "
            "Do not output greetings or explanations; only the requested content."
        ),
        temperature=0.2,
        use_prompt_cache=False,
    )
except Exception:
    pass

# Claude Sonnet（論理チェック / consistency 専用、Prompt Caching 有効）
try:
    PROVIDERS["claude_sonnet"] = ClaudeProvider(
        model="claude-sonnet-4-5",  # あなたの環境で動作確認済みのモデル名を使用
        max_tokens=4096,
        system_prompt="",  # system は blocks で渡すので空
        temperature=0.1,
        use_prompt_cache=True,
        cached_system_blocks=CONSISTENCY_SYSTEM_BLOCKS,
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
            "content": "日本語で、AIルーターの仕様書アウトラインを簡潔に作ってください。"
                       "挨拶や前置きは禁止し、Markdown の見出しだけを出力してください。",
        }
    ]

    outline = llama.chat(messages, max_tokens=256)
    out_path = ROOT / "spec_output" / "example_outline_llama.md"
    out_path.write_text(outline, encoding="utf-8")

    print("Router ready.")
    print("出力先:", out_path)
