"""
Memory OS 最小版（内存版，不接数据库）
流程：读入会议记录 → 事件提取（严格 JSON）→ 总结（带溯源）
用法：py -3 demo_mini.py [会议记录.txt]
      不传文件时使用 sample_data/meeting.txt。
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from extractor import extract_events
from summarizer import summarize
from utils import OUTPUTS_DIR, ensure_outputs_dir, get_word_count, read_file, split_text

load_dotenv(Path(__file__).resolve().parent / ".env")
ROOT = Path(__file__).resolve().parent


def main():
    if len(sys.argv) >= 2:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"文件不存在: {path}")
            sys.exit(1)
        text = read_file(path)
        print(f"[读入] {path}，共 {get_word_count(text)} 字\n")
    else:
        sample = ROOT / "sample_data" / "meeting.txt"
        if sample.exists():
            text = read_file(sample)
            print(f"[读入] {sample}，共 {get_word_count(text)} 字\n")
        else:
            text = """
2026-03-05 14:00 张三：新功能A要推迟到4月10日上线。
2026-03-05 14:05 李四：原因是后端接口还没稳定。
2026-03-05 14:20 王五：本周先完成测试环境部署。
"""
            print("[读入] 使用内置示例\n")

    print("1) 分块...")
    chunks = split_text(text)
    print(f"    共 {len(chunks)} 块\n")

    print("2) 事件提取（严格 JSON）...")
    events = extract_events(text)
    print(f"    识别到 {len(events)} 个核心事件\n")

    print("3) 生成总结（带溯源引用）...")
    summary_text = summarize(events)
    print("\n--- 总结 ---\n")
    print(summary_text)

    print("\n--- 事件溯源 ---")
    for e in events:
        print(f"  事件#{e.get('id')} [{e.get('timestamp','')}] {e.get('speaker','')} ({e.get('event_type','')}): {e.get('content','')[:60]}...")

    # 保存到 outputs/events.json
    ensure_outputs_dir()
    out_file = OUTPUTS_DIR / "events.json"
    to_save = [
        {"id": e.get("id"), "timestamp": e.get("timestamp"), "speaker": e.get("speaker"), "event_type": e.get("event_type"), "content": e.get("content"), "importance": e.get("importance"), "source_chunk_id": e.get("source_chunk_id")}
        for e in events
    ]
    out_file.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已保存事件至: {out_file}")


if __name__ == "__main__":
    main()
