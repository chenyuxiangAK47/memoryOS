"""
从会议记录文本中提取结构化事件（严格 JSON）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from schemas import EVENT_TYPES, MIN_IMPORTANCE
from utils import split_text

load_dotenv(Path(__file__).resolve().parent / ".env")

EXTRACT_SYSTEM = """你是会议记录/对话事件提取器。从给定文本中提取「核心事件」与「实体更新」，只输出一个 JSON 数组，不要其他文字。

每个事件必须是如下格式（字段名严格一致）：
{
  "timestamp": "日期时间或空字符串",
  "speaker": "发言人（用户/助手/姓名）",
  "event_type": "decision | risk | todo | fact",
  "content": "事件内容，100字以内",
  "importance": 1-5 的整数,
  "entity": "可选，若涉及以下实体则标注：location | schedule | owner | preference | status"
}

event_type 只能取：decision, risk, todo, fact。

请特别关注以下实体的出现或变更，即使只有一句话也要提取为事件（importance 至少 3）：
- location：地点、所在地、住在哪、城市
- schedule：时间、计划、上线时间、截止日期
- owner：负责人、谁负责
- preference：偏好、喜欢什么
- status：状态、当前决定

例如："我住在新加坡" → fact, entity: location, content: "用户所在地为新加坡"；
     "上线时间改成4月20日" → decision, entity: schedule, content: "上线时间改为4月20日"。

若无核心事件则输出 []。只输出 JSON 数组。"""


def _parse_events_from_response(raw: str) -> list[dict[str, Any]]:
    raw = raw.strip()
    m = re.search(r"\[[\s\S]*\]", raw)
    if m:
        raw = m.group(0)
    data = json.loads(raw)
    if not isinstance(data, list):
        data = [data] if isinstance(data, dict) else []
    out = []
    for e in data:
        if not isinstance(e, dict):
            continue
        if e.get("importance", 0) < MIN_IMPORTANCE:
            continue
        et = (e.get("event_type") or "fact").strip().lower()
        if et not in EVENT_TYPES:
            et = "fact"
        e["event_type"] = et
        e.setdefault("timestamp", "")
        e.setdefault("speaker", "未知")
        e.setdefault("content", "")
        e.setdefault("entity", "")
        e["importance"] = int(e.get("importance", 3))
        out.append(e)
    return out


def extract_events_from_chunk(
    chunk: str,
    chunk_id: int,
    client: OpenAI | None = None,
) -> list[dict[str, Any]]:
    """从单个文本块提取事件，并注入 source_chunk_id。"""
    if client is None:
        client = OpenAI()
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": chunk[:2500]},
            ],
        )
        raw = r.choices[0].message.content
        events = _parse_events_from_response(raw)
        for e in events:
            e["source_chunk_id"] = chunk_id
            e["source_chunk"] = chunk[:400]
        return events
    except (json.JSONDecodeError, KeyError, Exception):
        return []


def extract_events(
    text: str,
    client: OpenAI | None = None,
) -> list[dict[str, Any]]:
    """
    对整段文本分块后逐块提取事件，合并并赋予全局 id。
    返回带 id, source_chunk_id, source_chunk 的事件列表。
    """
    chunks = split_text(text)
    if not chunks:
        return []
    if client is None:
        client = OpenAI()
    all_events = []
    for i, chunk in enumerate(chunks):
        events = extract_events_from_chunk(chunk, chunk_id=i, client=client)
        all_events.extend(events)
    for idx, e in enumerate(all_events, 1):
        e["id"] = idx
    return all_events
