#!/usr/bin/env python3
"""
Cursor Memory Guard 实验：验证 Memory Guard 能否提高 Cursor 长对话下的约束保持率和当前状态准确率。
三种模式：Baseline（历史+prompt）、State Injection（注入 current_state）、Guard Mode（B + 输出检查）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from extractor import extract_events
from memory_guard import detect_conflicts_and_updates
from state_builder import build_state_snapshot, get_state_for_prompt

load_dotenv(Path(__file__).resolve().parent / ".env")
ROOT = Path(__file__).resolve().parent


def history_to_text(history: list[dict]) -> str:
    """把 session history 转成一段对话文本，供 extract_events 使用。"""
    lines = []
    for i, turn in enumerate(history, 1):
        role = turn.get("role", "user")
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        speaker = "用户" if role == "user" else "助手"
        lines.append(f"Round {i} {speaker}：{content}")
    return "\n".join(lines)


def build_current_state(history: list[dict], client: OpenAI) -> str:
    """从 history 构建 current_state summary（事件 → Guard → state_builder）。"""
    text = history_to_text(history)
    if not text.strip():
        return "（无历史，无当前状态）"
    events = extract_events(text, client=client)
    findings = detect_conflicts_and_updates(events, client=client) if len(events) >= 2 else []
    snapshot = build_state_snapshot(events, findings)
    return get_state_for_prompt(snapshot)


def build_critical_constraints(sentinels: dict) -> str:
    """从 session 的 sentinels 生成 critical constraints 文本。"""
    lines = []
    for surface in sentinels.get("surface") or []:
        lines.append(f"1. {surface}")
    for semantic in sentinels.get("semantic") or []:
        lines.append(f"2. {semantic}")
    for state in sentinels.get("state") or []:
        lines.append(f"3. {state}")
    if not lines:
        return "（无约束）"
    return "\n".join(lines)


def build_enhanced_prompt(
    session: dict,
    current_state: str,
    critical_constraints: str,
    mode: str,
) -> str:
    """构建发给模型的 prompt。mode: baseline | state_injection | guard."""
    history_text = history_to_text(session.get("history") or [])
    current_prompt = (session.get("current_prompt") or "").strip()

    if mode == "baseline":
        return f"""以下是对话历史与当前用户请求。请按要求回答。

对话历史：
---
{history_text[-4000:]}
---

当前用户请求：{current_prompt}

请直接回答："""

    # state_injection / guard：前面注入 current state 与 constraints
    return f"""【当前有效状态】请务必遵守以下状态与约束，回答时不要违背。

Current effective state:
{current_state}

Critical constraints:
{critical_constraints}

---
以下是对话历史与当前用户请求。

对话历史：
---
{history_text[-3500:]}
---

当前用户请求：{current_prompt}

请根据上述「当前有效状态」和「Critical constraints」回答，不要违反约束。"""


def build_enhanced_prompt(
    session: dict,
    current_state: str,
    critical_constraints: str,
    mode: str,
) -> str:
    """构建发给模型的 prompt。mode: baseline | state_injection | guard."""
    history_text = history_to_text(session.get("history") or [])
    current_prompt = (session.get("current_prompt") or "").strip()

    if mode == "baseline":
        return f"""以下是对话历史与当前用户请求。请按要求回答。

对话历史：
---
{history_text[-4000:]}
---

当前用户请求：{current_prompt}

请直接回答："""

    # state_injection / guard：前面注入 current state 与 constraints
    return f"""【当前有效状态】请务必遵守以下状态与约束，回答时不要违背。

Current effective state:
{current_state}

Critical constraints:
{critical_constraints}

---
以下是对话历史与当前用户请求。

对话历史：
---
{history_text[-3500:]}
---

当前用户请求：{current_prompt}

请根据上述「当前有效状态」和「Critical constraints」回答，不要违反约束。"""


# Checker 规则：violation_patterns 命中则可能违规，safe_patterns 命中则压制（否定/排除）
CONSTRAINT_RULES = {
    "database": {
        "violation_patterns": [
            "修改数据库", "动数据库", "新增数据库字段", "改表结构", "更新 schema",
            "数据库那边也加", "写入数据库", "改了数据库", "数据库层", "涉及数据库写入",
        ],
        "safe_patterns": [
            "未动数据库", "不动数据库", "不要动数据库", "不改数据库", "没有改数据库",
            "未修改数据库", "不涉及数据库", "仅前端", "只做前端", "mock 数据", "mock 列表",
            "未动后端和数据库", "没有修改数据库层",
        ],
    },
    "backend": {
        "violation_patterns": [
            "修改后端", "改后端", "新增接口", "调整接口", "改 API", "服务端",
        ],
        "safe_patterns": [
            "不改后端", "未动后端", "不要改后端", "仅前端", "mock 数据", "未动后端和",
        ],
    },
}


def _has_any(text: str, patterns: list[str]) -> bool:
    """文本中是否包含任一 pattern（忽略大小写）。"""
    t = (text or "").strip()
    for p in patterns:
        if p and p in t:
            return True
    return False


def _negation_near_keyword(text: str, keyword: str, window: int = 14) -> bool:
    """keyword 在 text 中出现时，其前 window 字内是否有否定/排除意。"""
    t = (text or "").strip()
    if keyword not in t:
        return False
    negations = ("不", "未", "没", "不要", "不改", "未动", "没有", "不涉及", "仅", "只做", "只改")
    idx = t.find(keyword)
    start = max(0, idx - window)
    prefix = t[start:idx]
    return any(n in prefix for n in negations)


def check_output_drift(
    output: str,
    sentinels: dict,
    current_state_summary: str,
) -> dict:
    """
    检查模型输出是否发生 memory drift。
    返回：sentinel_retained, missing_surface_sentinel, semantic_constraint_violations,
          semantic_constraint_warnings, stale_state_references, final_status.
    规则：先看 safe_patterns / 否定附近，再判 violation；violation 与 warning 分级。
    """
    result = {
        "sentinel_retained": True,
        "missing_surface_sentinel": False,
        "semantic_constraint_violations": [],
        "semantic_constraint_warnings": [],
        "stale_state_references": [],
        "format_violation": False,
        "final_status": "ok",
    }
    output_norm = (output or "").strip()
    output_lower = output_norm.lower()

    # ----- Surface sentinel -----
    surface_list = sentinels.get("surface") or []
    for s in surface_list:
        if "喵" in s or "结尾" in s or "最后" in s:
            if not output_norm.endswith("喵") and "喵" not in output_norm[-20:]:
                result["missing_surface_sentinel"] = True
                result["sentinel_retained"] = False

    # ----- Semantic: database / backend（否定感知 + violation/warning 分级）-----
    db_safe = _has_any(output_norm, CONSTRAINT_RULES["database"]["safe_patterns"]) or _negation_near_keyword(output_norm, "数据库")
    db_violation = _has_any(output_norm, CONSTRAINT_RULES["database"]["violation_patterns"])
    if db_safe and db_violation:
        result["semantic_constraint_violations"].append("modified_database_layer")
        result["sentinel_retained"] = False
    elif not db_safe and db_violation:
        result["semantic_constraint_violations"].append("modified_database_layer")
        result["sentinel_retained"] = False
    elif not db_safe and "数据库" in output_norm:
        result["semantic_constraint_warnings"].append("database mentioned; consider clarifying if negated")

    be_safe = _has_any(output_norm, CONSTRAINT_RULES["backend"]["safe_patterns"]) or _negation_near_keyword(output_norm, "后端")
    be_violation = _has_any(output_norm, CONSTRAINT_RULES["backend"]["violation_patterns"])
    if be_safe and be_violation:
        result["semantic_constraint_violations"].append("modified_backend")
        result["sentinel_retained"] = False
    elif not be_safe and be_violation:
        result["semantic_constraint_violations"].append("modified_backend")
        result["sentinel_retained"] = False
    elif not be_safe and "后端" in output_norm:
        result["semantic_constraint_warnings"].append("backend mentioned; consider clarifying if negated")

    # ----- 函数名：只判“明确改名/改签名”（精确匹配）-----
    semantic_list = sentinels.get("semantic") or []
    for s in semantic_list:
        if "保留" not in s and "不要改" not in s:
            continue
        # 提取函数名：如 "保留函数名 getTodoList" -> getTodoList
        if "getTodoList" in s:
            name = "getTodoList"
        elif "renderPlan" in s:
            name = "renderPlan"
        else:
            continue
        # 违规模式：明确改名、改签名（不含“未改/保留”的上下文）
        change_patterns = [
            f"{name}WithDone", f"{name}Changed", f"rename {name}", f"rename{name}",
            f"修改 {name} 为", f"{name} 改成", f"{name}改为", "改名为",
        ]
        # 若同时有“未改/保留”则不算违规
        if _has_any(output_norm, change_patterns) and not _has_any(output_norm, ["签名未改", "保留", "未改", "不变"]):
            result["semantic_constraint_violations"].append("changed_required_function_name")
            result["sentinel_retained"] = False
        # 仅未出现函数名且约束要求保留 -> warning
        if name not in output_norm and name.lower() not in output_lower:
            result["semantic_constraint_warnings"].append(f"required function {name} not mentioned")

    # ----- State：过时引用（若同时出现“现在/已改为/当前”等则不算 stale）-----
    state_list = sentinels.get("state") or []
    context_ok_phrases = ("现在", "已改为", "当前是", "当前负责人", "不再是", "原来", "已更新", "有问题找")
    has_context_ok = _has_any(output_norm, list(context_ok_phrases))
    for s in state_list:
        if "负责人" in s and "王五" in s:
            if "张三" in output_norm or "李四" in output_norm:
                if not has_context_ok or not ("王五" in output_norm):
                    result["stale_state_references"].append("used old owner")
                    result["sentinel_retained"] = False
        elif "负责人" in s and "李四" in s:
            if "张三" in output_norm and not has_context_ok:
                result["stale_state_references"].append("used old owner 张三")
                result["sentinel_retained"] = False

    # ----- final_status 分级 -----
    if result["missing_surface_sentinel"] or result["semantic_constraint_violations"] or result["stale_state_references"]:
        result["final_status"] = "possible_memory_drift"
    elif result["semantic_constraint_warnings"]:
        result["final_status"] = "ok_with_warning"
    else:
        result["final_status"] = "ok"

    return result


def run_experiment(session_path: Path, mode: str = "guard", output_to_check: str | None = None) -> dict:
    """
    运行实验。mode: baseline | state_injection | guard.
    若提供 output_to_check，则额外做 drift check 并返回报告。
    """
    session = json.loads(session_path.read_text(encoding="utf-8"))
    client = OpenAI()

    current_state = build_current_state(session.get("history") or [], client)
    sentinels = session.get("sentinels") or {}
    critical_constraints = build_critical_constraints(sentinels)
    enhanced_prompt = build_enhanced_prompt(session, current_state, critical_constraints, mode)

    out = {
        "session_id": session.get("session_id", ""),
        "mode": mode,
        "current_state_summary": current_state,
        "critical_constraints_summary": critical_constraints,
        "enhanced_prompt": enhanced_prompt,
    }

    if output_to_check is not None:
        drift_report = check_output_drift(output_to_check, sentinels, current_state)
        out["output_drift_check"] = drift_report

    return out


def main() -> int:
    session_path = ROOT / "cursor_sessions" / "session_01.json"
    if len(sys.argv) >= 2:
        session_path = Path(sys.argv[1])
    if not session_path.exists():
        print(f"Session 不存在: {session_path}", file=sys.stderr)
        return 1

    mode = "guard"
    if len(sys.argv) >= 3:
        mode = sys.argv[2].lower()
    if mode not in ("baseline", "state_injection", "guard"):
        mode = "guard"

    result = run_experiment(session_path, mode=mode)

    print("=" * 60)
    print("Cursor Memory Guard Experiment")
    print("=" * 60)
    print("\n--- Current effective state ---")
    print(result["current_state_summary"])
    print("\n--- Critical constraints ---")
    print(result["critical_constraints_summary"])
    print("\n--- Enhanced prompt (suggested for model) ---")
    print(result["enhanced_prompt"][:1500] + ("..." if len(result["enhanced_prompt"]) > 1500 else ""))
    if result.get("output_drift_check"):
        print("\n--- Output drift check ---")
        print(json.dumps(result["output_drift_check"], ensure_ascii=False, indent=2))
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
