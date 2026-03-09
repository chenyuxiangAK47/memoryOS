"""
事件 schema：结构化事件格式，供提取、存储、溯源统一使用。
"""
from typing import Literal, TypedDict

# 固定 4 类，先不扩展
EventType = Literal["decision", "risk", "todo", "fact"]

MIN_IMPORTANCE = 3  # 只保留 importance >= 3 的事件


class Event(TypedDict, total=False):
    """单条事件。"""
    id: int
    timestamp: str
    speaker: str
    event_type: EventType
    content: str
    importance: int
    source_chunk_id: int
    source_chunk: str  # 原始片段，用于溯源展示


EVENT_TYPES: list[str] = ["decision", "risk", "todo", "fact"]
