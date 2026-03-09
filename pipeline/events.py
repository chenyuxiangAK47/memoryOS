"""Memory OS MVP - 事件提取（Write Gate）."""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from config import EVENT_TYPES, MIN_IMPORTANCE, OPENAI_API_KEY


EVENT_EXTRACT_PROMPT = """你是一个会议/聊天记录分析助手。请从下面这段文本中提取「核心事件」。
只保留：决策、需求、问题、结论等有意义内容；忽略「好的」「嗯嗯」「哈哈」等无效内容。

输出严格为 JSON 数组，每个元素格式：
{
  "timestamp": "日期时间或未知",
  "person": "发言人或未知",
  "event_type": "decision|requirement|problem|conclusion|other",
  "content": "事件核心内容，100字以内",
  "importance": 1-5
}

若本段没有核心事件，返回空数组 []。
不要输出任何其他文字，只输出 JSON。

文本片段：
---
{chunk}
---"""


def extract_events_from_chunk(
    chunk: str,
    llm: ChatOpenAI | None = None,
) -> list[dict[str, Any]]:
    """从单个文本片段提取事件（可后续批量并行）。"""
    if not OPENAI_API_KEY:
        return []
    if llm is None:
        llm = ChatOpenAI(model="gpt-3.5-turbo", api_key=OPENAI_API_KEY)
    prompt = EVENT_EXTRACT_PROMPT.format(chunk=chunk[:2000])
    try:
        resp = llm.invoke(prompt)
        text = resp.content.strip()
        # 尝试从 markdown 代码块中取出 JSON
        m = re.search(r"\[[\s\S]*\]", text)
        if m:
            text = m.group(0)
        data = json.loads(text)
        if not isinstance(data, list):
            data = [data] if isinstance(data, dict) else []
        # 只保留 importance >= MIN_IMPORTANCE，并补全 source_chunk
        out = []
        for e in data:
            if isinstance(e, dict) and e.get("importance", 0) >= MIN_IMPORTANCE:
                e.setdefault("event_type", "other")
                if e["event_type"] not in EVENT_TYPES:
                    e["event_type"] = "other"
                e["source_chunk"] = chunk[:500]
                out.append(e)
        return out
    except (json.JSONDecodeError, Exception):
        return []


def extract_events_from_chunks(
    chunks: list[str],
    llm: ChatOpenAI | None = None,
) -> list[dict[str, Any]]:
    """从多个片段提取事件并合并（MVP 先串行，后续可并行）。"""
    all_events = []
    for chunk in chunks:
        events = extract_events_from_chunk(chunk, llm=llm)
        all_events.extend(events)
    return all_events
