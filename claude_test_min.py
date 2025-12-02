# claude_test_min.py
#
# router.py と同じ ClaudeProvider を使って、
# Haiku にごく短い質問を投げる最小テスト。

from providers.claude_api import ClaudeProvider


def main() -> None:
    # Haiku を使う（コストが安い）
    prov = ClaudeProvider(
        model="claude-3-haiku-20240307",
        max_tokens=32,  # 出力をかなり短くする → トークン削減
        system_prompt="You are a concise Japanese assistant. Answer in one short line.",
    )

    messages = [
        {
            "role": "user",
            "content": "1+1はいくつですか？数字だけ1行で答えてください。",
        }
    ]

    answer = prov.chat(messages)
    print("Claude answer:", answer)


if __name__ == "__main__":
    main()
