import os
from bs4 import BeautifulSoup

# HTML を集めるフォルダ
TARGET_DIR = "/home/rai/ai_router/html_docs"

def extract_outline(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f, "html.parser")

    headers = []
    for tag in ["h1", "h2", "h3"]:
        for h in soup.find_all(tag):
            text = h.get_text(strip=True)
            if text:
                headers.append(f"{tag}: {text}")

    return headers

def main():
    for file in os.listdir(TARGET_DIR):
        if not file.endswith(".html"):
            continue

        path = os.path.join(TARGET_DIR, file)
        size = os.path.getsize(path)

        print("\n==============================")
        print(f"FILE: {file}  ({size} bytes)")
        print("------------------------------")

        headers = extract_outline(path)
        for h in headers:
            print(" -", h)

        print("==============================")

if __name__ == "__main__":
    main()
