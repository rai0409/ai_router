from pathlib import Path
import platform
import re
import json

# -----------------------------
# 探索対象ディレクトリ候補
# -----------------------------

SEARCH_DIR_CANDIDATES = [
    # Linux / WSL
    Path.home() / "models",
    Path("/mnt/c/models"),
    Path("/mnt/d/models"),
    Path("/opt/models"),

    # Windows (WSL からのマウント想定)
    Path("/mnt/c/llama_models"),
]

# GGUF 判定
GGUF_EXT = ".gguf"

# -----------------------------
# モデル種別判定ロジック
# -----------------------------

def classify_model(path: Path) -> dict:
    name = path.name.lower()

    family = "unknown"
    role = "generic"

    if "deepseek" in name:
        family = "deepseek"
        if "coder" in name:
            role = "code_impl"
        elif "r1" in name:
            role = "reasoning"
        else:
            role = "general"
    elif "llama" in name:
        family = "llama"
        role = "general"
    elif "mixtral" in name or "mistral" in name:
        family = "mistral"
        role = "general"

    # 量子化レベル抽出
    q_match = re.search(r"q\d+[_\-]?\w*", name)
    quant = q_match.group(0) if q_match else "unknown"

    return {
        "file": path.name,
        "path": str(path),
        "family": family,
        "role": role,
        "quant": quant,
    }


# -----------------------------
# メイン探索処理
# -----------------------------

def scan_models():
    found = []

    for base in SEARCH_DIR_CANDIDATES:
        if not base.exists():
            continue

        for p in base.rglob(f"*{GGUF_EXT}"):
            try:
                info = classify_model(p)
                found.append(info)
            except Exception:
                continue

    return found


# -----------------------------
# 実行
# -----------------------------

if __name__ == "__main__":
    models = scan_models()

    print("\n=== Local GGUF Models Found ===\n")
    for m in models:
        print(
            f"[{m['family']}/{m['role']}] "
            f"{m['file']}  ({m['quant']})\n"
            f"  -> {m['path']}\n"
        )

    # JSON 出力（router / providers 用）
    out = Path("local_models.json")
    out.write_text(json.dumps(models, indent=2), encoding="utf-8")
    print(f"\nSaved: {out.resolve()}")
