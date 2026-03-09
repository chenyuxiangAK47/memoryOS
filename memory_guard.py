"""
Memory Guard：在事件流上检测记忆冲突 / 状态更新（防 drift、防 stale override）。
输出产品化：entity_key、旧状态/新状态、判定、建议采用、来源。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent / ".env")

# 最小判定模型：update（后续覆盖前序）、conflict（互相矛盾）、unchanged（未变，可不输出）
DETECT_SYSTEM = """你是 Memory Guard：检查事件列表中的「记忆一致性」，输出可被产品直接展示的结果。

判定类型（只输出这两种）：
- **update**：后面的事件修正/覆盖了前面的说法，可明确采用最新状态。
- **conflict**：两条事件互相矛盾，无法自动确定哪个对，需人工确认。

对每个发现，必须输出以下字段（JSON 数组，不要其他文字）：

{
  "type": "update 或 conflict",
  "entity_key": "用英文点号表示状态对象。例如：project.launch_plan, feature.face_verification, owner.api_checklist；若事件涉及地点/偏好/时间/负责人，请用 user.location, user.preference, project.schedule, project.owner",
  "topic": "中文主题简述，如 上线计划、用户所在地、接口负责人",
  "old_state": "旧状态/前序结论（一句话）",
  "new_state": "新状态/后续结论（一句话）；conflict 时可为另一方表述",
  "conclusion": "判定说明，如：后续决策覆盖前序计划 / 风险已被后续决策响应 / 两处表述矛盾需人工确认",
  "recommendation": "建议采用：最新状态 / 建议采用：事件#N / 需人工确认",
  "event_ids": [事件id1, 事件id2]
}

若为「风险被后续决策响应」，conclusion 写「风险已被后续决策响应」，recommendation 写「建议采用：最新状态」。
**重要**：若同一主题有多轮状态变化（例如先定 4/10 再改 4/20 再改为先 beta 再 4/20），请为**每一次变化**各输出一条 update 记录，entity_key 相同，event_ids 不同。例如上线计划有 3 次变化就输出 3 条 update，不要合并成 1 条。这样系统能保留完整演变序列（先 beta 再正式 4/20）。
若没有冲突也没有更新，输出 []。只输出 JSON 数组。"""


def detect_conflicts_and_updates(
    events: list[dict[str, Any]],
    client: OpenAI | None = None,
) -> list[dict[str, Any]]:
    """
    对事件列表做冲突/更新检测，返回产品化结构：
    type, entity_key, topic, old_state, new_state, conclusion, recommendation, event_ids
    """
    if not events or len(events) < 2:
        return []
    if client is None:
        client = OpenAI()
    lines = []
    for e in events:
        eid = e.get("id", "?")
        ts = e.get("timestamp", "")
        sp = e.get("speaker", "")
        et = e.get("event_type", "")
        ent = e.get("entity", "")
        cnt = (e.get("content") or "")[:150]
        if ent:
            lines.append(f"事件#{eid} [{ts}] {sp} ({et}) entity={ent}: {cnt}")
        else:
            lines.append(f"事件#{eid} [{ts}] {sp} ({et}): {cnt}")
    text = "\n".join(lines)[:6000]
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": DETECT_SYSTEM},
                {"role": "user", "content": "事件列表（按时间序）：\n" + text},
            ],
        )
        raw = r.choices[0].message.content.strip()
        m = re.search(r"\[[\s\S]*\]", raw)
        if m:
            raw = m.group(0)
        data = json.loads(raw)
        if not isinstance(data, list):
            data = [data] if isinstance(data, dict) else []
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            t = (item.get("type") or "").strip().lower()
            if "conflict" in t:
                item["type"] = "conflict"
            elif "update" in t:
                item["type"] = "update"
            else:
                item["type"] = "update"
            item.setdefault("event_ids", [])
            item.setdefault("entity_key", "")
            item.setdefault("topic", "")
            item.setdefault("old_state", "")
            item.setdefault("new_state", "")
            item.setdefault("conclusion", "")
            item.setdefault("recommendation", "建议采用：最新状态")
            out.append(item)
        return out
    except (json.JSONDecodeError, Exception):
        return []


def format_guard_report(findings: list[dict[str, Any]]) -> str:
    """旧版：简单文本报告（CLI 用）。"""
    if not findings:
        return "未发现记忆冲突或状态更新。"
    lines = []
    for i, f in enumerate(findings, 1):
        t = f.get("type", "")
        eids = f.get("event_ids", [])
        topic = f.get("topic", "")
        summary = f.get("conclusion") or f.get("summary", "")
        label = "⚠️ 冲突" if t == "conflict" else "🔄 更新"
        lines.append(f"{i}. {label} | 事件#{eids} | {topic}\n   {summary}")
    return "\n".join(lines)


def format_finding_card(f: dict[str, Any]) -> str:
    """单条发现的产品化展示（Markdown），用于页面。"""
    t = f.get("type", "")
    topic = f.get("topic", "")
    old_s = f.get("old_state", "")
    new_s = f.get("new_state", "")
    conclusion = f.get("conclusion", "")
    recommendation = f.get("recommendation", "")
    eids = f.get("event_ids", [])
    source = "来源：事件 #" + ", #".join(str(x) for x in eids) if eids else ""

    if t == "conflict":
        return f"""**⚠️ 冲突 — {topic}**
- **旧状态 / 一方**：{old_s}
- **新状态 / 另一方**：{new_s}
- **判定**：{conclusion}
- **建议**：{recommendation}
- {source}"""
    # update（含「风险被处理」）
    return f"""**🔄 状态更新 — {topic}**
- **旧状态**：{old_s}
- **新状态**：{new_s}
- **判定**：{conclusion}
- **建议采用**：{recommendation}
- {source}"""


def get_current_effective_state(
    events: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    client: OpenAI | None = None,
) -> str:
    """
    根据事件 + Guard 发现，生成「当前有效状态」摘要（上线计划、负责人、待办等）。
    """
    if not events:
        return "（无事件）"
    if client is None:
        client = OpenAI()
    lines = []
    for e in events:
        lines.append(f"事件#{e.get('id')} [{e.get('timestamp','')}] {e.get('speaker','')} ({e.get('event_type','')}): {e.get('content','')}")
    events_text = "\n".join(lines)[:5000]
    findings_text = ""
    if findings:
        for f in findings:
            findings_text += f"- {f.get('type')} | {f.get('topic','')} | 旧: {f.get('old_state','')} → 新: {f.get('new_state','')}\n"
    prompt = f"""根据以下「事件列表」和「Memory Guard 检测到的更新/冲突」，归纳出**当前有效状态**（AI 应采用的记忆）。

要求：
1. 分块：当前上线计划 / 当前负责人与待办 / 当前风险与应对。
2. 若某条结论已被后续事件覆盖，只写**最新状态**，并注明「来源：事件#N」。
3. 若有冲突未决，注明「存在冲突，见事件#X、#Y」。
4. 每条一句话，简洁。

事件列表：
{events_text}

Guard 检测结果（更新/冲突）：
{findings_text if findings_text else "无"}

请直接输出「当前有效状态」的 Markdown，不要其他解释。"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:
        return "（生成失败）"
