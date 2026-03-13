from __future__ import annotations

"""
Human-readable explanation layer for MemoryGuard reports.

纯模板化解释逻辑，不引入任何 LLM 或新依赖。
"""

from typing import Dict, List, Any


VIOLATION_EXPLANATIONS: Dict[str, str] = {
    "modified_database_layer": "The reply suggested modifying the database layer or schema.",
    "modified_backend": "The reply suggested modifying backend code or APIs.",
    "changed_required_function_name": "The reply suggested renaming or changing a required function name.",
    "missing_surface_sentinel": "The reply missed a required output sentinel or formatting constraint.",
    "database mentioned; consider clarifying if negated": "The reply mentioned database changes and may need manual review.",
    "backend mentioned; consider clarifying if negated": "The reply mentioned backend changes and may need manual review.",
}


def _map_violations(violations: List[str]) -> List[str]:
    out: List[str] = []
    for v in violations:
        desc = VIOLATION_EXPLANATIONS.get(v, v)
        out.append(f"- {desc}")
    return out


def explain_check_result(result: Dict[str, Any]) -> str:
    """
    根据单次 check 的结果字典生成一段人类可读的说明。
    """
    if not isinstance(result, dict):
        return "Invalid check result format."

    final_status = result.get("final_status", "")
    violations: List[str] = []
    violations.extend(result.get("semantic_constraint_violations") or [])
    violations.extend(result.get("stale_state_references") or [])
    if result.get("missing_surface_sentinel"):
        violations.append("missing_surface_sentinel")
    if result.get("format_violation"):
        violations.append("format_violation")
    # warnings 视为轻量级提示
    warnings = result.get("semantic_constraint_warnings") or []

    lines: List[str] = []

    if final_status == "ok":
        lines.append("No drift detected.")
        lines.append(
            "The reply stays consistent with the current state and constraints."
        )
    elif final_status == "ok_with_warning":
        lines.append("No clear drift detected, but there are warnings.")
        lines.append(
            "The reply mostly stays within constraints, but you may want to review the warnings below."
        )
    else:
        lines.append("Drift detected.")
        lines.append(
            "The reply may violate earlier constraints or current state assumptions."
        )

    if violations:
        lines.append("")
        lines.append("Key reasons:")
        lines.extend(_map_violations(violations))

    if warnings:
        lines.append("")
        lines.append("Additional warnings:")
        lines.extend(_map_violations(warnings))

    return "\n".join(lines).strip() or "No drift information available."


def explain_trace_drift(result: Dict[str, Any]) -> str:
    """
    根据 trace_drift.json 的完整结果生成一段人类可读说明。
    """
    if not isinstance(result, dict):
        return "Invalid trace_drift result format."

    summary = result.get("summary") or {}
    timeline = result.get("timeline") or []

    total_replies = summary.get("total_replies", len(timeline) or 0)
    first_idx = summary.get("first_drift_turn_index")
    first_file = summary.get("first_drift_reply")
    first_status = summary.get("first_drift_status", "")

    lines: List[str] = []

    if not first_idx:
        lines.append(
            f"No drift detected across all {total_replies} checked replies."
        )
        return "\n".join(lines)

    lines.append(
        f"Drift starts at turn {first_idx} ({first_file})."
    )
    lines.append(
        "Replies before that appear consistent with the current constraints."
    )

    # 找到首漂移轮次对应的 violations
    drift_entry: Dict[str, Any] | None = None
    for item in timeline:
        if (
            isinstance(item, dict)
            and item.get("turn_index") == first_idx
        ):
            drift_entry = item
            break

    violations: List[str] = []
    if drift_entry:
        violations = list(drift_entry.get("violations") or [])

    if violations:
        lines.append("")
        lines.append("Key violated constraints:")
        lines.extend(_map_violations(violations))

    if first_status and first_status != "possible_memory_drift":
        lines.append("")
        lines.append(f"Internal status: {first_status}")

    return "\n".join(lines).strip()

