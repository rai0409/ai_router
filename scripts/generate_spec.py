# scripts/generate_spec.py
import argparse
from pathlib import Path
from datetime import datetime
import sys

# プロジェクト root を import パスに追加
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router import run  # type: ignore[import]


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# -----------------------------
#  Llama 用ベースプロンプト
# -----------------------------

BASE_REQUIREMENTS_PROMPT = """
あなたは日本語のソフトウェア仕様書ライターです。

目的:
- 実務でそのまま開発に使えるレベルで、
  機能要件 / 非機能要件 / ユースケース / 制約 / 優先度 を整理すること。

共通ルール:
- 出力はすべて日本語。
- 挨拶や前置き、まとめの文章は禁止。
- 各セクションは「見出し + 箇条書き」で書く。
- 一般論だけでなく、具体的な項目・処理フロー・エラーケースにも触れる。
{project_hints}

【プロジェクト説明】
{content}
""".strip()

BASE_OUTLINE_PROMPT = """
あなたは日本語のソフトウェア仕様書の構成設計者です。

目的:
- 実務でそのまま仕様書として使える章立て（アウトライン）を作ること。

共通ルール:
- 出力は日本語の Markdown 見出しのみとし、本文は書かない。
- 挨拶や前置きは禁止。
- 章番号・節番号（例: 1., 1.1, 1.2 ...）を付ける。
{project_hints}

【要求整理結果】
{requirements_md}
""".strip()

BASE_DEEP_DRAFT_PROMPT = """
あなたは日本語のソフトウェア仕様書ライターです。

目的:
- 要求とアウトラインに基づき、実務レベルの仕様書ドラフト本文を書くこと。

共通ルール:
- 出力は日本語の Markdown。
- 挨拶や前置き、不要な一般論は禁止。
- 各セクションでは、可能な限り次の観点を含める:
  - 目的
  - 前提
  - 入力 / 出力
  - 処理内容・フロー
  - エラー・例外時の挙動
  - 運用・保守上の注意
{project_hints}

【要求】
{requirements_md}

【アウトライン】
{outline_md}
""".strip()


# -----------------------------
#  プロジェクト別ヒント
# -----------------------------

PROJECT_REQUIREMENTS_HINTS = {
    "tdnet": """
TDnet XBRL 変換システムとして、必ず次の観点を含めてください:
- TDnet で扱う具体項目（会社コード、提出者種別、開示種別、提出日時 等）
- 既存フォーマット（CSV / 画面入力 等）から XBRL へのマッピング
- XBRL タクソノミ構造（要素定義、namespace、linkbase 等）
- XBRL インスタンス文書の context / unit / 精度
- 変換エラー・バリデーション・ログ・リトライ方針
- タクソノミ更新・仕様変更への追随
- 性能要件（処理件数・処理時間）と運用フロー
""",
    "stocks": """
日本株の機械学習モデルとして、必ず次の観点を含めてください:
- 対象ユニバース（例: TOPIX1000）と構成銘柄の更新方法
- 入力データ（価格・ファンダ・イベント・マクロ 等）と取得元
- 特徴量群（価格系 / ファンダ系 / イベント系 / マクロ系 等）
- ターゲット定義（リターン horizon, 単位, ラベル化方法）
- CV 戦略（TimeSeriesSplit / GroupKFold 等）とリーク対策
- 評価指標（IC / Sharpe / F1 等）とモニタリング
- 再学習・デプロイ・モデル監視の運用
""",
    "matching_app": """
マッチングアプリとして、必ず次の観点を含めてください:
- ユーザー登録 / 認証 / プロフィール管理
- マッチングロジック（レコメンド、スワイプ、スコアリング 等）
- メッセージ機能 / 通知
- 不正利用・スパム・BAN / 通報フロー
- 課金・サブスクリプション設計（必要な場合）
- データ保持期間・プライバシー・規約対応
""",
    "generic": """
一般的な業務システムとして、次の観点を含めてください:
- 主要な機能一覧
- ユーザー / 権限の種類
- 入力データと出力データ
- 運用・保守・監視の観点
""",
}

PROJECT_OUTLINE_HINTS = {
    "tdnet": """
仕様書の章立てには、少なくとも次の章を含めてください:
- 概要
- 用語定義
- システム全体構成
- 機能要件
- 非機能要件
- データモデル / マッピング仕様（TDnet → XBRL）
- エラー処理・ログ・監査
- 運用・保守・タクソノミ更新
- リスク・制約
""",
    "stocks": """
仕様書の章立てには、少なくとも次の章を含めてください:
- 概要
- 用語定義
- データソースと前処理
- 特徴量設計
- モデル設計と学習設定
- CV / 評価・リーク対策
- 運用・再学習・モニタリング
- リスク・制約
""",
    "matching_app": """
仕様書の章立てには、少なくとも次の章を含めてください:
- 概要
- 用語定義
- システム構成
- 認証・ユーザー管理
- マッチングロジック
- メッセージ / 通知
- 課金・サブスク（必要な場合）
- セキュリティ・不正利用対策
- 運用・監視
""",
    "generic": """
一般的な業務システムとして、少なくとも次の章を含めてください:
- 概要
- 用語定義
- システム構成
- 機能要件
- 非機能要件
- データモデル
- 運用・保守
- リスク・制約
""",
}

PROJECT_DEEP_DRAFT_HINTS = {
    "tdnet": """
各セクションでは、TDnet / XBRL 実務を前提に、可能な限り具体的に記述してください。
- 項目例（会社コード、開示種別 等）
- マッピング例（入力列 → XBRL 要素）
- エラーケース（バリデーション NG、タクソノミ不整合 等）
""",
    "stocks": """
各セクションでは、対象銘柄・特徴量・ターゲット・CV・評価方法を具体的に記述してください。
- 銘柄コードや期間の例
- 特徴量リストの例
- CV 分割図のイメージ 等
""",
    "matching_app": """
各セクションでは、ユーザーフロー・画面遷移・状態遷移・マッチング条件を具体的に記述してください。
- 代表的なユーザーストーリー
- マッチング条件の例
""",
    "generic": """
各セクションでは、入力・処理・出力・エラー・運用を具体的に記述してください。
""",
}


def build_requirements_prompt(project: str, content: str) -> str:
    hints = PROJECT_REQUIREMENTS_HINTS.get(project, PROJECT_REQUIREMENTS_HINTS["generic"])
    return BASE_REQUIREMENTS_PROMPT.format(project_hints=hints, content=content)


def build_outline_prompt(project: str, requirements_md: str) -> str:
    hints = PROJECT_OUTLINE_HINTS.get(project, PROJECT_OUTLINE_HINTS["generic"])
    return BASE_OUTLINE_PROMPT.format(project_hints=hints, requirements_md=requirements_md)


def build_deep_draft_prompt(project: str, requirements_md: str, outline_md: str) -> str:
    hints = PROJECT_DEEP_DRAFT_HINTS.get(project, PROJECT_DEEP_DRAFT_HINTS["generic"])
    return BASE_DEEP_DRAFT_PROMPT.format(
        project_hints=hints,
        requirements_md=requirements_md,
        outline_md=outline_md,
    )


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
    parser.add_argument(
        "--project",
        type=str,
        choices=["tdnet", "stocks", "matching_app", "generic"],
        default="tdnet",
        help="プロジェクト種別（プロンプト最適化用）",
    )
    parser.add_argument(
        "--until",
        type=str,
        choices=["requirements", "outline", "deep_draft", "all"],
        default="all",
        help="どのステップまで実行するか",
    )

    args = parser.parse_args()

    if args.input:
        content = Path(args.input).read_text(encoding="utf-8")
    elif args.prompt:
        content = args.prompt
    else:
        print("エラー: --input か --prompt のどちらかは必須です。")
        sys.exit(1)

    project = args.project
    out_dir = ROOT / args.out_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{timestamp}_{project}"

    # 1) 要求分析（Llama 想定）
    print("[1/4] requirements を生成中...")
    requirements_prompt = build_requirements_prompt(project, content)
    requirements_md = run("spec", "requirements", requirements_prompt)
    req_path = out_dir / f"{prefix}_01_requirements.md"
    save_text(req_path, requirements_md)

    if args.until == "requirements":
        print("完了: requirements まで生成しました。出力先:", out_dir)
        return

    # 2) アウトライン（Llama）
    print("[2/4] outline を生成中...")
    outline_prompt = build_outline_prompt(project, requirements_md)
    outline_md = run("spec", "outline", outline_prompt)
    outline_path = out_dir / f"{prefix}_02_outline.md"
    save_text(outline_path, outline_md)

    if args.until == "outline":
        print("完了: outline まで生成しました。出力先:", out_dir)
        return

    # 3) Deep Draft（Llama）
    print("[3/4] deep draft を生成中...")
    deep_draft_prompt = build_deep_draft_prompt(project, requirements_md, outline_md)
    deep_md = run("spec", "deep_draft", deep_draft_prompt)
    deep_path = out_dir / f"{prefix}_03_deep_draft.md"
    save_text(deep_path, deep_md)

    if args.until == "deep_draft":
        print("完了: deep draft まで生成しました。出力先:", out_dir)
        return

    # 4) 整合性チェック（Claude Sonnet）
    print("[4/4] consistency review を生成中...")
    review_prompt = (
        "以下の仕様書ドラフトを、指定された観点に従ってレビューしてください。\n"
        "仕様書本文のみを対象とし、出力フォーマットは system の指示に従ってください。\n\n"
        + deep_md
    )
    review_md = run("spec", "consistency", review_prompt)
    review_path = out_dir / f"{prefix}_04_consistency_review.md"
    save_text(review_path, review_md)

    print("完了: 出力先ディレクトリ =", out_dir)


if __name__ == "__main__":
    main()
