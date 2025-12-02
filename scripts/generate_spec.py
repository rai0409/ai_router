import argparse
import os
from pathlib import Path
from datetime import datetime
import sys
import traceback  # 追加

# プロジェクト root を import パスに追加
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import router  # 追加
from providers.claude_api import ClaudeAPIError  # 追加


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def safe_run_section(
    task_type: str,
    section: str,
    content: str,
    fallback: str | None = None,
) -> str:
    """
    router.run をラップして、Claude 落ちなどの例外時にフォールバックやログ出力を行う。
    """
    try:
        return router.run(task_type, section, content)
    except ClaudeAPIError as e:
        # ログ出力
        log_dir = ROOT / "spec_output" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"error_{task_type}_{section}.log"
        with log_path.open("w", encoding="utf-8") as f:
            f.write(f"[ERROR] task_type={task_type}, section={section}\n")
            f.write(str(e) + "\n")
            f.write(traceback.format_exc())

        print(f"[警告] {section} で ClaudeAPIError が発生。詳細は {log_path} を参照。")

        # フォールバックが指定されていれば、llama_local などで代用
        if fallback is not None:
            print(f"[info] フォールバック provider={fallback} で再実行します。")
            if fallback in router.PROVIDERS:
                provider = router.PROVIDERS[fallback]
                messages = [{"role": "user", "content": content}]
                return provider.chat(messages)

        # フォールバックなし → 空文字を返す
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="仕様書（requirements / outline / deep draft / consistency）自動生成"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=False,
        help="仕様対象プロジェクトの説明テキストファイル（なければ --prompt を使う）",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        required=False,
        help="直接プロジェクト概要を文字列で渡す場合",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="spec_output",
        help="出力ディレクトリ（デフォルト: spec_output）",
    )
    args = parser.parse_args()

    if args.input:
        content = Path(args.input).read_text(encoding="utf-8")
    elif args.prompt:
        content = args.prompt
    else:
        print("エラー: --input か --prompt のどちらかは必須です。")
        sys.exit(1)

    out_dir = ROOT / args.out_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1) 要求分析（通常は llama_local）
    print("[1/4] requirements を生成中...")
    requirements_prompt = (
        "以下のプロジェクト説明から、機能要件 / 非機能要件 / ユースケース / 制約 / 優先度 を整理してください。\n\n"
        + content
    )
    requirements_md = safe_run_section("spec", "requirements", requirements_prompt)
    save_text(out_dir / f"{timestamp}_01_requirements.md", requirements_md)

    # 2) アウトライン（Llama ローカル）
    print("[2/4] outline を生成中...")
    outline_prompt = (
        "以下の要求整理結果をもとに、仕様書の章立て・目次（Outline）を Markdown で作成してください。\n\n"
        + requirements_md
    )
    outline_md = safe_run_section("spec", "outline", outline_prompt)
    save_text(out_dir / f"{timestamp}_02_outline.md", outline_md)

    # 3) Deep Draft（章ごとの詳細ドラフト）
    print("[3/4] deep draft を生成中...")
    deep_draft_prompt = (
        "以下のアウトラインと要求をもとに、各章の本文ドラフトを詳しく記述してください。\n"
        "実務でそのまま使えるレベルで、日本語で書いてください。\n\n"
        "【要求】\n" + requirements_md + "\n\n【アウトライン】\n" + outline_md
    )
    deep_md = safe_run_section("spec", "deep_draft", deep_draft_prompt)
    save_text(out_dir / f"{timestamp}_03_deep_draft.md", deep_md)

    # 4) 整合性チェック（Claude Sonnet → 落ちたら llama_local にフォールバック）
    print("[4/4] consistency review を生成中...")
    review_prompt = (
        "以下の仕様書ドラフトをレビューしてください。\n"
        "- 要求と仕様の不整合\n"
        "- 欠けている観点\n"
        "- 曖昧な記述\n"
        "- リスク\n"
        "を一覧化し、最後に改善提案した改訂版の見出し案も提示してください。\n\n"
        + deep_md
    )
    review_md = safe_run_section(
        "spec",
        "consistency",
        review_prompt,
        fallback="llama_local",  # Claude エラー時はローカルで最低限のレビューを生成
    )
    save_text(out_dir / f"{timestamp}_04_consistency_review.md", review_md)

    print("完了: 出力先ディレクトリ =", out_dir)


if __name__ == "__main__":
    main()
