"""
从 event log + Guard findings 构建当前状态快照（state_snapshot）。
支持同一 entity 的多步更新：entity_key → history + current（sequence state），避免只保留最后一句丢掉「先 beta 再正式」。
"""
from __future__ import annotations

from typing import Any


def build_state_snapshot(
    events: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    从事件 + Guard 发现构建状态快照。
    - 同一 entity_key 的多个 update 按 event_ids 排序，保留 history_states 和 current_state（最后一条）
    - conflict 单独一条 status=conflict
    返回项含: entity_key, topic, current_state, history_states (list), status, source_event_ids
    """
    # 按 entity_key 分组 update，并按 max(event_id) 排序（时间序）
    updates_by_key: dict[str, list[dict[str, Any]]] = {}
    conflicts: list[dict[str, Any]] = []

    for f in findings:
        entity_key = (f.get("entity_key") or "").strip() or (f.get("topic") or "").strip()
        if not entity_key:
            continue
        t = f.get("type", "")
        if t == "update":
            updates_by_key.setdefault(entity_key, []).append(f)
        elif t == "conflict":
            conflicts.append({
                "entity_key": entity_key,
                "topic": f.get("topic", ""),
                "current_state": None,
                "history_states": [],
                "status": "conflict",
                "description": f.get("conclusion", "") or f.get("new_state", ""),
                "old_state": f.get("old_state", ""),
                "new_state": f.get("new_state", ""),
                "source_event_ids": list(f.get("event_ids", [])),
            })

    snapshot: list[dict[str, Any]] = []

    for entity_key, group in updates_by_key.items():
        # 按涉及的最大 event_id 排序，保证时间序
        sorted_group = sorted(group, key=lambda x: max(x.get("event_ids", [0]) or [0]))
        history_states = [g.get("new_state", "") for g in sorted_group if g.get("new_state")]
        current_state = history_states[-1] if history_states else ""
        all_event_ids = []
        for g in sorted_group:
            all_event_ids.extend(g.get("event_ids", []))
        snapshot.append({
            "entity_key": entity_key,
            "topic": sorted_group[0].get("topic", "") if sorted_group else "",
            "current_state": current_state,
            "history_states": history_states,
            "status": "ok",
            "source_event_ids": list(dict.fromkeys(all_event_ids)),
        })

    for c in conflicts:
        snapshot.append(c)

    # 无 findings 时用事件兜底
    if not snapshot and events:
        for e in reversed(events):
            content = (e.get("content") or "")[:200]
            if content:
                snapshot.append({
                    "entity_key": "event.latest",
                    "topic": "最新事件",
                    "current_state": content,
                    "history_states": [content],
                    "status": "ok",
                    "source_event_ids": [e.get("id")],
                })
                break

    return snapshot


def get_state_for_prompt(snapshot: list[dict[str, Any]]) -> str:
    """把 state_snapshot 格式化成可拼进 LLM prompt 的字符串；多步更新时输出【演变】→【当前】。"""
    if not snapshot:
        return "（无当前状态）"
    lines = []
    for s in snapshot:
        key = s.get("entity_key", "")
        topic = s.get("topic", "") or key
        status = s.get("status", "ok")
        if status == "conflict":
            desc = s.get("description", "")
            old_s = s.get("old_state", "")
            new_s = s.get("new_state", "")
            if old_s and new_s:
                lines.append(f"- [{topic}] 存在冲突：一方「{old_s}」另一方「{new_s}」。{desc}")
            else:
                lines.append(f"- [{topic}] 存在冲突，需人工确认：{desc}")
            continue
        current = s.get("current_state", "")
        history = s.get("history_states", [])
        if not current:
            continue
        if len(history) > 1:
            # 多步更新：暴露演变 + 当前，便于 LLM 答出「先 beta 再正式」
            evolution = " → ".join(history)
            lines.append(f"- [{topic}] 【演变】{evolution} 【当前】{current}")
        else:
            lines.append(f"- [{topic}] {current}")
    return "\n".join(lines) if lines else "（无当前状态）"


def state_snapshot_to_dict(snapshot: list[dict[str, Any]]) -> dict[str, str]:
    """扁平化为 entity_key -> current_state（仅 status=ok）。"""
    out: dict[str, str] = {}
    for s in snapshot:
        if s.get("status") != "ok":
            continue
        key = s.get("entity_key", "")
        state = s.get("current_state", "")
        if key and state:
            out[key] = state
    return out
