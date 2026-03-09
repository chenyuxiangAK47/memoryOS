"""Memory OS MVP - 总结生成（基于检索到的事件）."""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY


SUMMARY_PROMPT = """你是一个会议/聊天记录总结助手。请根据下面这些「核心事件」生成一份简洁总结。

要求：
1. 分块：核心决策、关键风险、待办任务（如有）。
2. 每条结论尽量简短，可标注来自谁/什么类型。
3. 不要编造，只基于给出的事件。

核心事件（结构化）：
---
{events_text}
---

请输出总结（Markdown 格式）："""


def generate_summary(events: list[dict], model: str = "gpt-3.5-turbo") -> str:
    """根据事件列表生成总结。"""
    if not events or not OPENAI_API_KEY:
        return "（暂无事件或未配置 API Key）"
    events_text = "\n".join(
        f"- [{e.get('timestamp','')}] {e.get('person','')} ({e.get('event_type','')}): {e.get('content','')}"
        for e in events
    )
    prompt = SUMMARY_PROMPT.format(events_text=events_text[:8000])
    llm = ChatOpenAI(model=model, api_key=OPENAI_API_KEY)
    return llm.invoke(prompt).content
