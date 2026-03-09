"""
根据结构化事件生成总结，并尽量引用事件 id 做溯源。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent / ".env")

SUMMARY_SYSTEM = """你是会议总结助手。根据下面的「结构化事件」生成总结。

要求：
1. 分三块输出：核心决策、风险、待办。
2. 每条结论尽量标注来源，格式：来源：事件#N，发言人，时间
   例如：来源：事件#3，张三，2026-03-05 14:00
3. 只基于给出的事件，不要编造。
4. 使用 Markdown 格式，简洁清晰。"""


def summarize(events: list[dict[str, Any]], client: OpenAI | None = None) -> str:
    """根据事件列表生成带溯源引用的总结。"""
    if not events:
        return "（未提取到核心事件）"
    if client is None:
        client = OpenAI()
    lines = []
    for e in events:
        eid = e.get("id", "?")
        ts = e.get("timestamp", "")
        sp = e.get("speaker", "")
        et = e.get("event_type", "")
        cnt = (e.get("content") or "")[:200]
        lines.append(f"[事件#{eid}] {ts} {sp} ({et}): {cnt}")
    text = "\n".join(lines)[:8000]
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": "结构化事件：\n" + text},
        ],
    )
    return r.choices[0].message.content.strip()
