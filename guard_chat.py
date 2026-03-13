from __future__ import annotations

"""
MemoryGuard v2-alpha runtime wrapper:
guard_chat = prepare + model call + check + explain

This is an explicit wrapper (no IDE auto-hooking).
"""

import json
from pathlib import Path
from typing import Any, Dict


def load_state(state_path: str) -> dict:
    p = Path(state_path)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parent / p).resolve()
    return json.loads(p.read_text(encoding="utf-8"))


def build_enhanced_prompt(user_prompt: str, imported_state: dict) -> str:
    """
    Minimal prompt builder for v2-alpha:
    - Reuses the same shape as `prepare` for history_import states
    - If state isn't history_import, still includes constraints/sentinels if present
    """
    user_prompt = (user_prompt or "").strip()

    state_items = imported_state.get("current_effective_state") or []
    if state_items:
        state_text = "\n".join(f"- [{s.get('key', '')}] {s.get('value', '')}" for s in state_items)
    else:
        state_text = "（无）"

    constraints = imported_state.get("critical_constraints") or []
    hard_text = "\n".join(constraints) if constraints else "（无）"

    return f"""【当前有效状态】请务必遵守以下状态与约束。

Current effective state:
{state_text}

Critical constraints:
{hard_text}

---
当前用户请求：
{user_prompt}

请根据上述「当前有效状态」和「Critical constraints」回答，尤其不要违反硬约束。"""


def guard_chat(*, model_wrapper: Any, state_path: str, user_prompt: str) -> Dict[str, Any]:
    """
    Run guarded chat flow and return a structured bundle.

    Returns:
      {
        "state_path": ...,
        "user_prompt": ...,
        "enhanced_prompt": ...,
        "ai_response": ...,
        "guard_result": <check report dict>,
        "readable_summary": <explanation string>
      }
    """
    from memoryguard import run_check_from_text  # reuse existing checker logic
    from report_explainer import explain_check_result

    imported_state = load_state(state_path)
    enhanced = build_enhanced_prompt(user_prompt, imported_state)
    ai_response = model_wrapper.generate(enhanced)
    guard_result = run_check_from_text(state_path, ai_response)
    readable = explain_check_result(guard_result)

    return {
        "state_path": state_path,
        "user_prompt": user_prompt,
        "enhanced_prompt": enhanced,
        "ai_response": ai_response,
        "guard_result": guard_result,
        "readable_summary": readable,
    }

