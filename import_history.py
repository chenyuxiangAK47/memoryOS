#!/usr/bin/env python3
"""
import_history MVP：从旧聊天记录导入，提取当前有效状态与关键约束，供 prepare/check 使用。
支持 .txt / .md / .json（session 格式），复用 extractor、memory_guard、state_builder。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from extractor import extract_events, extract_events_from_chunk
from memory_guard import detect_conflicts_and_updates
from state_builder import build_state_snapshot, get_state_for_prompt
from utils import OUTPUTS_DIR, ensure_outputs_dir

load_dotenv(Path(__file__).resolve().parent / ".env")
ROOT = Path(__file__).resolve().parent


def _turns_to_text(turns: list[dict]) -> str:
    """turns [{role, content}] -> 对话文本，供 extract_events。"""
    lines = []
    for i, t in enumerate(turns, 1):
        role = t.get("role", "user")
        content = (t.get("content") or "").strip()
        if not content:
            continue
        speaker = "用户" if role == "user" else "助手"
        lines.append(f"Round {i} {speaker}：{content}")
    return "\n".join(lines)


def load_history_file(path: Path) -> tuple[list[dict], str]:
    """
    加载历史文件，返回 (turns, raw_text)。
    - .json：若是 session 格式则取 history 为 turns，否则整文件当单条
    - .txt / .md：解析为 turns + 原始文本
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    suf = path.suffix.lower()
    raw = path.read_text(encoding="utf-8", errors="ignore")

    if suf == ".json":
        data = json.loads(raw)
        if isinstance(data, dict) and "history" in data:
            turns = data.get("history") or []
            return turns, _turns_to_text(turns)
        # 非 session 格式暂不解析
        return [], raw

    # .txt / .md：解析对话角色
    turns = parse_dialogue_to_turns(raw)
    return turns, raw


def parse_dialogue_to_turns(text: str) -> list[dict]:
    """
    从纯文本解析出 turns。
    支持：
    - 行内：用户：/ 助手：、User:/ Assistant:、Round N 用户：/ Round N 助手：
    - 块格式：**User** / **Cursor** 单独成行，内容直到下一个 **User**/**Cursor**
    """
    lines = text.strip().split("\n")
    turns: list[dict] = []
    current_role: str | None = None
    current_content: list[str] = []

    def flush():
        if current_role and current_content:
            turns.append({"role": current_role, "content": "\n".join(current_content).strip()})

    # 块格式：行内仅 \*\*(User|Cursor)\*\*
    block_header = re.compile(r"^\s*\*\*(User|Cursor)\*\*\s*$", re.IGNORECASE)

    # 先尝试块格式（若文本里出现过 **User** 或 **Cursor** 且行内模式几乎没匹配到）
    line_pattern = re.compile(
        r"^(?:Round\s*\d+\s+)?(用户|助手|User|Assistant)\s*[：:]\s*(.*)$",
        re.IGNORECASE,
    )
    has_block_marker = any(block_header.match(line.strip()) for line in lines)
    for line in lines:
        m = line_pattern.match(line.strip())
        if m:
            break
    else:
        # 没有任何行内匹配
        if has_block_marker:
            # 用块格式解析
            for line in lines:
                bl = block_header.match(line.strip())
                if bl:
                    flush()
                    role_label = (bl.group(1) or "").strip().lower()
                    current_role = "user" if role_label == "user" else "assistant"
                    current_content = []
                else:
                    if current_role is not None:
                        current_content.append(line)
            flush()
            if turns:
                return turns
    # 行内格式
    current_role = None
    current_content = []
    for line in lines:
        m = line_pattern.match(line.strip())
        if m:
            flush()
            role_label = (m.group(1) or "").strip().lower()
            if role_label in ("用户", "user"):
                current_role = "user"
            else:
                current_role = "assistant"
            content = (m.group(2) or "").strip()
            current_content = [content] if content else []
        else:
            if current_content is not None:
                current_content.append(line)
    flush()
    if not turns:
        # 回退：整段当一条 user 内容
        if text.strip():
            turns = [{"role": "user", "content": text.strip()}]
    return turns


def infer_critical_constraints(text: str) -> list[str]:
    """
    从对话文本启发式抽取关键约束（不要/保留/只改/回答加喵 等）。
    不调用 LLM，仅模式匹配。若整行是 "Round N 用户：xxx" 则只取 xxx。
    """
    constraints: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\n。！？]", text):
        part = part.strip()
        if not part or len(part) < 4:
            continue
        # 去掉 "Round N 用户：" / "Round N 助手：" 前缀，只保留约束内容
        m = re.match(r"^Round\s*\d+\s*(?:用户|助手|User|Assistant)\s*[：:]\s*(.+)$", part, re.IGNORECASE)
        if m:
            part = m.group(1).strip()
        if not part or len(part) < 3:
            continue
        # 不要/不改/不修改/别改
        if re.search(r"不要\s*(动|改|修改|用)\s*", part) or "不改" in part or "别改" in part:
            c = part[:80].strip()
            if c not in seen:
                seen.add(c)
                constraints.append(c)
        # 保留 xxx
        if "保留" in part and ("函数" in part or "getTodoList" in part or "renderPlan" in part):
            c = part[:80].strip()
            if c not in seen:
                seen.add(c)
                constraints.append(c)
        # 只改/只做/仅前端（排除「只要…」操作指引，避免误收）
        if re.search(r"只[改做]|仅(前端|后端)|只\s*前端", part) and not re.match(r"^你?只要", part):
            c = part[:80].strip()
            if c not in seen:
                seen.add(c)
                constraints.append(c)
        # 回答结尾加喵 / 最后加喵
        if "喵" in part and ("回答" in part or "结尾" in part or "最后" in part):
            c = "回答最后必须加喵"
            if c not in seen:
                seen.add(c)
                constraints.append(c)
    return constraints


# ---------- 分块 + 规则优先 pipeline（大文件） ----------


def chunk_lines(lines: list[str], chunk_size: int = 2000) -> list[list[str]]:
    """按行分块，每块最多 chunk_size 行。"""
    if chunk_size <= 0:
        return [lines] if lines else []
    return [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]


def rule_extract_events(chunk_text: str, chunk_id: int) -> list[dict[str, Any]]:
    """
    规则抽取：负责人、截止/上线时间、地点、约束（不要/保留/只做/加喵）。
    返回与 extractor 兼容的事件结构（无 id，有 source_chunk_id, entity, content, event_type）。
    """
    events: list[dict[str, Any]] = []
    text = chunk_text.strip()
    if not text:
        return events

    for m in re.finditer(
        r"(?:负责人|谁负责|owner)\s*(?:改成|改为|是|：|:)?\s*([^\s,，。\n]{2,20})",
        text,
        re.IGNORECASE,
    ):
        name = m.group(1).strip()
        if name and len(name) >= 2:
            events.append({
                "event_type": "decision",
                "content": f"负责人为{name}",
                "entity": "owner",
                "timestamp": "",
                "speaker": "用户",
                "source_chunk_id": chunk_id,
                "importance": 4,
            })

    for m in re.finditer(
        r"(?:截止|上线|deadline|交付)\s*(?:到|时间|日期)?\s*[：:]?\s*([^\n。！？]{2,30})",
        text,
        re.IGNORECASE,
    ):
        val = m.group(1).strip()
        if val and len(val) <= 25:
            events.append({
                "event_type": "decision",
                "content": f"截止/上线：{val}",
                "entity": "schedule",
                "timestamp": "",
                "speaker": "用户",
                "source_chunk_id": chunk_id,
                "importance": 4,
            })
    for m in re.finditer(r"(?:周[一二三四五六日]|月底|月初|[0-9]{1,2}[月号日])", text):
        s = m.group(0)
        if s and not any(e.get("content") and s in (e.get("content") or "") for e in events):
            events.append({
                "event_type": "fact",
                "content": f"时间节点：{s}",
                "entity": "schedule",
                "timestamp": "",
                "speaker": "用户",
                "source_chunk_id": chunk_id,
                "importance": 3,
            })

    for m in re.finditer(
        r"(?:地点|住在|所在地)\s*[：:]?\s*([^\n。！？=;()]{2,30})",
        text,
    ):
        val = m.group(1).strip()
        if val and "=" not in val and ";" not in val:
            events.append({
                "event_type": "fact",
                "content": f"地点/所在地：{val}",
                "entity": "location",
                "timestamp": "",
                "speaker": "用户",
                "source_chunk_id": chunk_id,
                "importance": 3,
            })

    for part in re.split(r"[\n。！？]", text):
        part = part.strip()
        if not part or len(part) < 4:
            continue
        m = re.match(r"^Round\s*\d+\s*(?:用户|助手|User|Assistant)\s*[：:]\s*(.+)$", part, re.IGNORECASE)
        if m:
            part = m.group(1).strip()
        if not part or len(part) < 3:
            continue
        content_short = part[:80].strip()
        if re.search(r"不要\s*(动|改|修改|用)\s*", part) or "不改" in part or "别改" in part:
            events.append({
                "event_type": "fact",
                "content": content_short,
                "entity": "constraint",
                "timestamp": "",
                "speaker": "用户",
                "source_chunk_id": chunk_id,
                "importance": 4,
            })
        if "保留" in part and ("函数" in part or "getTodoList" in part or "renderPlan" in part or "代码" in part):
            events.append({
                "event_type": "fact",
                "content": content_short,
                "entity": "constraint",
                "timestamp": "",
                "speaker": "用户",
                "source_chunk_id": chunk_id,
                "importance": 4,
            })
        if re.search(r"只[改做]|仅(前端|后端)|只\s*前端", part) and not re.match(r"^你?只要", part):
            events.append({
                "event_type": "fact",
                "content": content_short,
                "entity": "constraint",
                "timestamp": "",
                "speaker": "用户",
                "source_chunk_id": chunk_id,
                "importance": 4,
            })
        if "喵" in part and ("回答" in part or "结尾" in part or "最后" in part):
            events.append({
                "event_type": "fact",
                "content": "回答最后必须加喵",
                "entity": "constraint",
                "timestamp": "",
                "speaker": "用户",
                "source_chunk_id": chunk_id,
                "importance": 4,
            })

    return events


def run_import_chunked(
    path: Path,
    client: OpenAI | None = None,
    *,
    chunk_size: int = 2000,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    分块读取 → 每块规则抽取（+ 可选 LLM）→ 合并 event_log → state_builder → imported_state。
    """
    if client is None:
        client = OpenAI()
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = raw.splitlines()
    total_lines = len(lines)
    chunks = chunk_lines(lines, chunk_size=chunk_size)
    num_chunks = len(chunks)

    all_state_events: list[dict[str, Any]] = []
    all_constraint_contents: list[str] = []

    for i, chunk_line_list in enumerate(chunks):
        print(f"  Chunk {i+1}/{num_chunks}", flush=True)
        chunk_text = "\n".join(chunk_line_list)
        rule_events = rule_extract_events(chunk_text, chunk_id=i)
        for e in rule_events:
            if (e.get("entity") or "").strip().lower() == "constraint":
                c = (e.get("content") or "").strip()
                if c and c not in all_constraint_contents:
                    all_constraint_contents.append(c)
            else:
                all_state_events.append(e)
        if use_llm and len(chunk_text.strip()) > 100:
            llm_events = extract_events_from_chunk(chunk_text[:6000], chunk_id=i, client=client)
            all_state_events.extend(llm_events)

    for idx, e in enumerate(all_state_events, 1):
        e["id"] = idx

    critical_constraints = list(dict.fromkeys(all_constraint_contents))
    if not all_state_events and not critical_constraints:
        critical_constraints = infer_critical_constraints(raw)

    findings = detect_conflicts_and_updates(all_state_events, client=client) if len(all_state_events) >= 2 else []
    snapshot = build_state_snapshot(all_state_events, findings)
    state_text = get_state_for_prompt(snapshot)

    current_effective_state = []
    for s in snapshot:
        if s.get("status") != "ok":
            continue
        key = s.get("entity_key") or s.get("topic") or ""
        value = (s.get("current_state") or "").strip()
        if key and value:
            current_effective_state.append({"key": key, "value": value})

    state_updates = []
    for f in findings:
        if f.get("type") != "update":
            continue
        key = f.get("entity_key") or f.get("topic") or ""
        old_s = (f.get("old_state") or "").strip()
        new_s = (f.get("new_state") or "").strip()
        if key and new_s:
            state_updates.append({"key": key, "from": old_s, "to": new_s})

    conflicts = []
    for f in findings:
        if f.get("type") != "conflict":
            continue
        key = f.get("entity_key") or f.get("topic") or ""
        conflicts.append({
            "key": key,
            "values": [f.get("old_state", ""), f.get("new_state", "")],
            "status": "needs_review",
        })

    extracted_events = [
        {"id": e.get("id"), "content": (e.get("content") or "")[:150], "event_type": e.get("event_type"), "entity": e.get("entity")}
        for e in all_state_events
    ]

    return {
        "source_file": str(path),
        "import_mode": "history_import",
        "chunked": True,
        "lines_processed": total_lines,
        "chunks": num_chunks,
        "events_extracted": len(all_state_events),
        "constraints_count": len(critical_constraints),
        "state_updates_count": len(state_updates),
        "conflicts_count": len(conflicts),
        "current_effective_state": current_effective_state,
        "critical_constraints": critical_constraints,
        "state_updates": state_updates,
        "conflicts": conflicts,
        "extracted_events": extracted_events,
        "event_log": all_state_events,
        "_state_text": state_text,
        "_snapshot": snapshot,
    }


def run_import(
    path: Path,
    client: OpenAI | None = None,
    *,
    tail: int | None = None,
    max_turns: int | None = None,
) -> dict[str, Any]:
    """
    执行导入：读文件 → 解析 turns →（可选）只取最后 tail 条或前 max_turns 条 → 提取事件 → Guard → state_snapshot → 组装 imported_state 结构。
    """
    if client is None:
        client = OpenAI()
    turns, raw_text = load_history_file(path)
    turns_total = len(turns)
    if tail is not None and tail > 0:
        turns = turns[-tail:]
    elif max_turns is not None and max_turns > 0:
        turns = turns[:max_turns]
    conversation_text = _turns_to_text(turns) if turns else raw_text
    if not conversation_text.strip():
        return {
            "source_file": str(path),
            "import_mode": "history_import",
            "current_effective_state": [],
            "critical_constraints": [],
            "state_updates": [],
            "conflicts": [],
            "extracted_events": [],
            "error": "empty_content",
        }

    events = extract_events(conversation_text, client=client)
    findings = detect_conflicts_and_updates(events, client=client) if len(events) >= 2 else []
    snapshot = build_state_snapshot(events, findings)
    state_text = get_state_for_prompt(snapshot)

    # current_effective_state: 从 snapshot 转成 [{key, value}]
    current_effective_state: list[dict[str, str]] = []
    for s in snapshot:
        if s.get("status") != "ok":
            continue
        key = s.get("entity_key") or s.get("topic") or ""
        value = (s.get("current_state") or "").strip()
        if key and value:
            current_effective_state.append({"key": key, "value": value})

    # state_updates: 从 findings type=update
    state_updates: list[dict[str, str]] = []
    for f in findings:
        if f.get("type") != "update":
            continue
        key = f.get("entity_key") or f.get("topic") or ""
        old_s = (f.get("old_state") or "").strip()
        new_s = (f.get("new_state") or "").strip()
        if key and new_s:
            state_updates.append({"key": key, "from": old_s, "to": new_s})

    # conflicts: 从 findings type=conflict
    conflicts: list[dict[str, Any]] = []
    for f in findings:
        if f.get("type") != "conflict":
            continue
        key = f.get("entity_key") or f.get("topic") or ""
        old_s = f.get("old_state") or ""
        new_s = f.get("new_state") or ""
        conflicts.append({
            "key": key,
            "values": [old_s, new_s] if old_s and new_s else [old_s or new_s],
            "status": "needs_review",
        })

    # critical_constraints: 启发式 + 若为 session json 则合并 sentinels
    critical_constraints = infer_critical_constraints(raw_text)
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "sentinels" in data:
                for v in (data.get("sentinels") or {}).get("surface") or []:
                    if v and v not in critical_constraints:
                        critical_constraints.append(v)
                for v in (data.get("sentinels") or {}).get("semantic") or []:
                    if v and v not in critical_constraints:
                        critical_constraints.append(v)
                for v in (data.get("sentinels") or {}).get("state") or []:
                    if v and v not in critical_constraints:
                        critical_constraints.append(v)
        except Exception:
            pass

    # extracted_events 精简字段
    extracted_events = [
        {"id": e.get("id"), "content": (e.get("content") or "")[:150], "event_type": e.get("event_type"), "entity": e.get("entity")}
        for e in events
    ]

    return {
        "source_file": str(path),
        "import_mode": "history_import",
        "turns_used": len(turns),
        "turns_total": turns_total,
        "current_effective_state": current_effective_state,
        "critical_constraints": critical_constraints,
        "state_updates": state_updates,
        "conflicts": conflicts,
        "extracted_events": extracted_events,
        "_state_text": state_text,
        "_snapshot": snapshot,
    }


def build_import_summary_md(data: dict[str, Any]) -> str:
    """生成人类可读的 import_summary.md。"""
    lines = [
        "# Memory Guard — 导入摘要",
        "",
        f"**来源文件**: `{data.get('source_file', '')}`",
        "",
    ]
    if data.get("turns_total") is not None and data.get("turns_used") is not None:
        total, used = data["turns_total"], data["turns_used"]
        if total != used:
            lines.append(f"**对话轮数**: 共 {total} 轮，本次使用 {used} 轮（可用 --tail / --max-turns 控制）")
            lines.append("")
    if data.get("chunked"):
        lines.append(f"**lines_processed**: {data.get('lines_processed', 0)}")
        lines.append(f"**chunks**: {data.get('chunks', 0)}")
        lines.append(f"**events_extracted**: {data.get('events_extracted', 0)}")
        lines.append(f"**state_updates**: {data.get('state_updates_count', 0)}")
        lines.append(f"**constraints**: {data.get('constraints_count', 0)}")
        lines.append(f"**conflicts**: {data.get('conflicts_count', 0)}")
        lines.append("")
    lines.extend([
        "## 当前有效状态",
        "",
    ])
    state_list = data.get("current_effective_state") or []
    if state_list:
        for s in state_list:
            lines.append(f"- **{s.get('key', '')}**: {s.get('value', '')}")
    else:
        lines.append("（未识别到结构化状态，可查看 extracted_events）")
    lines.extend(["", "## 关键约束", ""])
    for c in data.get("critical_constraints") or []:
        lines.append(f"- {c}")
    if not data.get("critical_constraints"):
        lines.append("（未识别到显式约束）")
    lines.extend(["", "## 状态更新", ""])
    for u in data.get("state_updates") or []:
        lines.append(f"- **{u.get('key', '')}**: {u.get('from', '')} → {u.get('to', '')}")
    if not data.get("state_updates"):
        lines.append("（无）")
    lines.extend(["", "## 冲突 / 待确认", ""])
    for c in data.get("conflicts") or []:
        lines.append(f"- **{c.get('key', '')}**: {c.get('values', [])} — {c.get('status', '')}")
    if not data.get("conflicts"):
        lines.append("（无）")
    lines.extend(["", "## 抽取事件（前 20 条）", ""])
    for e in (data.get("extracted_events") or [])[:20]:
        lines.append(f"- #{e.get('id')} [{e.get('event_type', '')}] {e.get('content', '')}")
    return "\n".join(lines)


def write_imported_state(data: dict[str, Any], out_path: Path, event_log_path: Path | None = None) -> None:
    """写出 imported_state.json（去掉内部字段 _state_text, _snapshot）；若提供 event_log_path 则单独写出 event_log。"""
    out = {k: v for k, v in data.items() if not k.startswith("_") and k != "event_log"}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if event_log_path is not None and data.get("event_log") is not None:
        event_log_path.parent.mkdir(parents=True, exist_ok=True)
        event_log_path.write_text(
            json.dumps(data["event_log"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def cmd_import_history(
    history_file: str,
    out_path: str | None = None,
    summary_path: str | None = None,
    *,
    tail: int | None = None,
    max_turns: int | None = None,
    chunked: bool = False,
    chunk_size: int = 2000,
    use_llm: bool = True,
    event_log_path: str | Path | None = None,
) -> int:
    """CLI：导入历史并写出 imported_state.json + import_summary.md。支持 --chunked 分块+规则优先（大文件）。"""
    ensure_outputs_dir()
    path = Path(history_file)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        return 1
    out_path = Path(out_path or OUTPUTS_DIR / "imported_state.json").resolve()
    summary_path = Path(summary_path or OUTPUTS_DIR / "import_summary.md").resolve()
    event_log_out = Path(event_log_path) if event_log_path else (OUTPUTS_DIR / "event_log.json")

    if chunked:
        print("Processing history (chunked pipeline)...")
        data = run_import_chunked(path, chunk_size=chunk_size, use_llm=use_llm)
        print(f"Total lines: {data.get('lines_processed', 0)}")
        print(f"Chunks: {data.get('chunks', 0)}")
        print(f"Events extracted: {data.get('events_extracted', 0)}")
        print(f"State updates: {data.get('state_updates_count', 0)}")
        print(f"Constraints: {data.get('constraints_count', 0)}")
        print(f"Conflicts: {data.get('conflicts_count', 0)}")
        print("Building state...")
        write_imported_state(data, out_path, event_log_path=event_log_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(build_import_summary_md(data), encoding="utf-8")
        print(f"已写入: {out_path}")
        print(f"已写入: {summary_path}")
        print(f"已写入: {event_log_out}")
    else:
        data = run_import(path, tail=tail, max_turns=max_turns)
        write_imported_state(data, out_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(build_import_summary_md(data), encoding="utf-8")
        print(f"已写入: {out_path}")
        print(f"已写入: {summary_path}")
    return 0
