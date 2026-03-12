from __future__ import annotations

"""
从 `测试的markdown/traceMd.md` 中自动提取 demo 用的 4 个回复文件：
- reply_1.txt
- reply_2.txt
- reply_3.txt
- reply_4.txt

提取规则（尽量贴合当前 traceMd.md 结构）：
- 找到类似 `1. reply_1.txt` / `2. reply_2.txt` / ... 的行，记为当前 reply 段落。
- 在该段落下，遇到第一行为 `text` 或 `plaintext` 时，从下一行开始收集内容。
- 一直收集到：
  - 下一条形如 `N. reply_X.txt` 的行，或
  - 文件结束。

输出目录：outputs/traceMd_replies/
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
TRACE_MD_PATH = ROOT / "测试的markdown" / "traceMd.md"
OUT_DIR = ROOT / "outputs" / "traceMd_replies"


def extract_replies() -> None:
    if not TRACE_MD_PATH.exists():
        raise FileNotFoundError(f"找不到 traceMd.md: {TRACE_MD_PATH}")

    text = TRACE_MD_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 状态机
    current_label: str | None = None  # "reply_1", "reply_2", ...
    collecting = False
    buffer: list[str] = []

    def flush():
        nonlocal buffer, current_label
        if current_label and buffer:
            out_path = OUT_DIR / f"{current_label}.txt"
            out_path.write_text("\n".join(buffer).strip() + "\n", encoding="utf-8")
        buffer = []

    for i, raw in enumerate(lines):
        line = raw.strip()

        # 检测新的 reply 段落起点，如： "1. reply_1.txt  → Round 1 ..."
        if line.startswith("1. reply_1.txt"):
            flush()
            current_label = "reply_1"
            collecting = False
            continue
        if line.startswith("2. reply_2.txt"):
            flush()
            current_label = "reply_2"
            collecting = False
            continue
        if line.startswith("3. reply_3.txt"):
            flush()
            current_label = "reply_3"
            collecting = False
            continue
        if line.startswith("4. reply_4.txt"):
            flush()
            current_label = "reply_4"
            collecting = False
            continue

        # 在当前段落下，遇到 "text" 或 "plaintext" 后一行开始正式收集内容
        if current_label and not collecting and line in ("text", "plaintext"):
            collecting = True
            continue

        if current_label and collecting:
            # 若后续出现新的 "N. reply_X.txt" 会在上面的逻辑里 flush。
            buffer.append(raw)

    # 文件结束时 flush 最后一段
    flush()


if __name__ == "__main__":
    extract_replies()

