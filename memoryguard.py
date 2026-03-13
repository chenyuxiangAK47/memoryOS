from __future__ import annotations

#!/usr/bin/env python3
"""
Memory Guard CLI — 防 AI 记忆偏移 / Memory drift detection for long-running AI sessions.

用法（py -3 memoryguard.py <command> ...）:
  prepare [session.json]     输出 current state + constraints + enhanced prompt
  check <output.txt> [--session session.json]  检查输出是否 drift
  run [--session session.json] [--output output.txt]  prepare + 可选 check
  benchmark [--all | scenario.json]  跑 Memory Drift Benchmark
  import_history <file> [--out path] [--summary path]  从旧聊天导入状态
  analyze <file>             分析会议/聊天记录（事件+冲突检测+总结）
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from extractor import extract_events
from memory_guard import (
    detect_conflicts_and_updates,
    format_finding_card,
    get_current_effective_state,
)
from report_explainer import explain_check_result, explain_trace_drift
from summarizer import summarize
from utils import OUTPUTS_DIR, ensure_outputs_dir, get_word_count, read_file, split_text
from guard_chat import guard_chat
from mock_wrapper import MockWrapper
from runtime.wrappers.openai_wrapper import OpenAIWrapper

# Cursor Guard 实验相关（prepare / check / run）
try:
    from cursor_guard_experiment import run_experiment, check_output_drift
except ImportError:
    run_experiment = None
    check_output_drift = None
# 导入历史（import_history）
try:
    from import_history import run_import, build_import_summary_md, write_imported_state, cmd_import_history
except ImportError:
    run_import = None
    build_import_summary_md = None
    write_imported_state = None
    cmd_import_history = None

load_dotenv(Path(__file__).resolve().parent / ".env")
ROOT = Path(__file__).resolve().parent


def _safe_print(text: str) -> None:
    """
    在可能是 GBK 等有限编码的终端下安全打印文本：
    - 首选直接 print；
    - 若遇到 UnicodeEncodeError（例如 emoji），则降级为忽略无法编码的字符再打印。
    """
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        try:
            safe = text.encode(enc, errors="ignore").decode(enc, errors="ignore")
        except Exception:
            safe = text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
        print(safe)


def cmd_analyze(file_path: str) -> int:
    path = Path(file_path)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    if not path.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        return 1
    try:
        text = read_file(path)
    except Exception as e:
        print(f"读取失败: {e}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("Memory Guard 分析报告")
    print("=" * 60)
    print(f"文件: {path}")
    print(f"字数: {get_word_count(text)}")
    chunks = split_text(text)
    print(f"分块: {len(chunks)}")
    print()

    print("--- 事件提取 ---")
    events = extract_events(text)
    print(f"事件数: {len(events)}")
    for e in events:
        print(f"  事件#{e.get('id')} [{e.get('timestamp','')}] {e.get('speaker','')} ({e.get('event_type','')}): {(e.get('content') or '')[:50]}...")
    print()

    if len(events) >= 2:
        print("--- Memory Guard：冲突/更新检测 ---")
        findings = detect_conflicts_and_updates(events)
        if findings:
            for f in findings:
                print(format_finding_card(f))
                print()
        else:
            print("未发现记忆冲突或状态更新。")
        print()
        print("--- 当前有效状态 ---")
        print(get_current_effective_state(events, findings))
        print()
    else:
        print("--- 记忆检测 ---")
        print("事件数 < 2，跳过冲突/更新检测。")
        print()

    print("--- 总结（带溯源）---")
    summary_text = summarize(events)
    print(summary_text)
    print()

    # 保存
    ensure_outputs_dir()
    out_json = OUTPUTS_DIR / "events.json"
    to_save = [
        {"id": e.get("id"), "timestamp": e.get("timestamp"), "speaker": e.get("speaker"), "event_type": e.get("event_type"), "content": e.get("content"), "importance": e.get("importance"), "source_chunk_id": e.get("source_chunk_id")}
        for e in events
    ]
    out_json.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"事件已保存: {out_json}")

    return 0


def _resolve_session_path(session_path: str | None) -> Path:
    if session_path:
        p = Path(session_path)
    else:
        p = ROOT / "cursor_sessions" / "session_real_20plus.json"  # 官方 demo
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    return p


def _format_imported_state_summary(data: dict) -> str:
    """把 imported_state 的 current_effective_state 格式化成可读文本。"""
    items = data.get("current_effective_state") or []
    if not items:
        return "（无）"
    return "\n".join(f"- [{s.get('key', '')}] {s.get('value', '')}" for s in items)


def _imported_state_to_sentinels(data: dict) -> dict:
    """把 imported_state 的 critical_constraints 转成 sentinels 结构供 check 使用。"""
    constraints = data.get("critical_constraints") or []
    surface = []
    semantic = []
    for c in constraints:
        if "喵" in c or "结尾" in c:
            surface.append(c)
        else:
            semantic.append(c)
    return {"surface": surface, "semantic": semantic, "state": []}


def run_check_from_text(state_path: str, reply_text: str) -> dict:
    """
    基于给定的 state JSON 路径和单条回答文本，运行一次 drift 检查并返回原始报告字典。
    该函数复用现有 check 逻辑，不做任何新的 drift 规则判断。
    """
    session_path = Path(state_path)
    if not session_path.is_absolute():
        session_path = (ROOT / session_path).resolve()
    if not session_path.exists():
        raise FileNotFoundError(f"Session 不存在: {session_path}")

    session = json.loads(session_path.read_text(encoding="utf-8"))
    # 兼容导入状态文件
    if session.get("import_mode") == "history_import":
        if check_output_drift is None:
            raise RuntimeError("cursor_guard_experiment 未可用")
        state_summary = _format_imported_state_summary(session)
        sentinels = _imported_state_to_sentinels(session)
        return check_output_drift(reply_text, sentinels, state_summary)

    if run_experiment is None or check_output_drift is None:
        raise RuntimeError("cursor_guard_experiment 未可用")

    result = run_experiment(session_path, mode="guard")
    return check_output_drift(
        reply_text,
        session.get("sentinels") or {},
        result["current_state_summary"],
    )


def get_changed_files() -> List[str]:
    """
    Return a list of changed files from `git diff --name-only`.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        # 在这个 MVP 版本里，git 出错就当作“没有改动”
        return []

    lines = result.stdout.splitlines()
    return [line.strip() for line in lines if line.strip()]


def cmd_guard_diff() -> int:
    """
    Minimal 3B diff guard command:
    - Collect changed files from git
    - Print a small JSON blob
    """
    changed_files = get_changed_files()

    payload = {
        "changed_files": changed_files,
        "final_status": "ok",
    }

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _split_constraints_hard_soft(constraints: list[str]) -> tuple[list[str], list[str]]:
    """
    把约束粗分为 hard / soft：
    - hard：明显禁止/必须/只做/不要动数据库/回答必须加喵 等
    - soft：其余偏建议、操作指引
    """
    hard: list[str] = []
    soft: list[str] = []
    hard_keywords = [
        "不要",
        "不能",
        "不准",
        "不得",
        "禁止",
        "严禁",
        "绝对不能",
        "不可以",
        "别动",
        "别改",
        "必须",
        "一定要",
        "务必",
    ]
    hard_patterns = [
        "不要动数据库",
        "不要改数据库",
        "不要动后端",
        "不要改后端",
        "只做前端",
        "只改前端",
        "只改后端",
        "只做后端",
        "回答最后必须加喵",
    ]
    for raw in constraints or []:
        text = (raw or "").strip()
        if not text:
            continue
        lowered = text
        is_hard = any(k in lowered for k in hard_keywords) or any(p in lowered for p in hard_patterns)
        if "喵" in lowered:
            is_hard = True
        if is_hard:
            hard.append(text)
        else:
            soft.append(text)
    return hard, soft


def cmd_prepare(session_path: str) -> int:
    """输出 current state + critical constraints + enhanced prompt。"""
    path = _resolve_session_path(session_path)
    if not path.exists():
        print(f"Session 不存在: {path}", file=sys.stderr)
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    # 兼容导入状态文件（import_mode == history_import）
    if data.get("import_mode") == "history_import":
        state_text = _format_imported_state_summary(data)
        constraints = data.get("critical_constraints") or []
        hard_constraints, soft_constraints = _split_constraints_hard_soft(constraints)
        hard_text = "\n".join(hard_constraints) or "（无）"
        soft_text = "\n".join(soft_constraints) or "（无）"
        enhanced = f"""【当前有效状态】请务必遵守以下状态与约束。

Current effective state:
{state_text}

Hard constraints:
{hard_text}

Soft constraints:
{soft_text}

---
（请在此输入当前请求，或粘贴后续问题）

请根据上述「当前有效状态」和「Hard constraints / Soft constraints」回答，尤其不要违反 Hard constraints。"""
        _safe_print("=" * 60)
        _safe_print("Memory Guard — prepare（导入状态）")
        _safe_print("=" * 60)
        _safe_print("\n--- Current effective state ---")
        _safe_print(state_text)
        _safe_print("\n--- Hard constraints ---")
        _safe_print(hard_text)
        _safe_print("\n--- Soft constraints ---")
        _safe_print(soft_text)
        _safe_print("\n--- Enhanced prompt ---")
        _safe_print(enhanced)
        _safe_print("=" * 60)
        return 0
    if run_experiment is None:
        print("cursor_guard_experiment 未可用", file=sys.stderr)
        return 1
    result = run_experiment(path, mode="guard")
    _safe_print("=" * 60)
    _safe_print("Memory Guard — prepare（当前状态 + 约束 + 增强 prompt）")
    _safe_print("=" * 60)
    _safe_print("\n--- Current effective state ---")
    _safe_print(result["current_state_summary"])
    _safe_print("\n--- Critical constraints ---")
    _safe_print(result["critical_constraints_summary"])
    _safe_print("\n--- Enhanced prompt ---")
    _safe_print(result["enhanced_prompt"])
    _safe_print("=" * 60)
    return 0


def cmd_check(output_path: str, session_path: str | None) -> int:
    """检查给定输出是否 drift。"""
    out_path = Path(output_path) if Path(output_path).is_absolute() else (ROOT / output_path).resolve()
    if not out_path.exists():
        print(f"输出文件不存在: {out_path}", file=sys.stderr)
        return 1
    session_path_resolved = _resolve_session_path(session_path)
    if not session_path_resolved.exists():
        print(f"Session 不存在: {session_path_resolved}", file=sys.stderr)
        return 1
    output_text = out_path.read_text(encoding="utf-8")
    try:
        report = run_check_from_text(str(session_path_resolved), output_text)
    except Exception as e:
        print(f"check 失败: {e}", file=sys.stderr)
        return 1
    _safe_print("=" * 60)
    _safe_print("Memory Guard — output drift check")
    _safe_print("=" * 60)
    _safe_print(json.dumps(report, ensure_ascii=False, indent=2))
    _safe_print("=" * 60)

    # 额外写入可读解释文件（不影响原有输出）
    try:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        explained = explain_check_result(report)
        explained_path = OUTPUTS_DIR / "latest_check_explained.md"
        explained_path.write_text(explained, encoding="utf-8")
    except Exception:
        # 解释层失败不应影响主逻辑
        pass

    return 0


def _collect_violations(report: dict) -> list[str]:
    """
    从单次 check 报告中提取统一的 violations 列表：
    - semantic_constraint_violations
    - stale_state_references
    - surface/sentinel 相关（missing_surface_sentinel）
    - 格式违规（format_violation）
    - 语义 warnings（作为较轻级别标记）
    """
    violations: list[str] = []
    violations.extend(report.get("semantic_constraint_violations") or [])
    violations.extend(report.get("stale_state_references") or [])
    if report.get("missing_surface_sentinel"):
        violations.append("missing_surface_sentinel")
    if report.get("format_violation"):
        violations.append("format_violation")
    violations.extend(report.get("semantic_constraint_warnings") or [])
    return violations


def _read_reply_text(path: Path) -> str:
    """
    读取回复文件内容，优先按 UTF-8，其次尝试常见编码，避免因为编码问题导致整个 trace-drift 失败。
    仅用于 trace-drift 场景，不影响其他命令。
    """
    for enc in ("utf-8", "utf-8-sig", "utf-16", "gbk"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # 兜底：按二进制读取再解码为 utf-8，非法字节忽略
    return path.read_bytes().decode("utf-8", errors="ignore")


def cmd_trace_drift(state_path: str, replies_dir: str, out_path: str) -> int:
    """
    批量对多轮回答运行 drift check，生成 trace_drift.json + trace_drift.md：
    - timeline：每一轮的 final_status + violations
    - summary：首次 drift 出现的位置及状态
    """
    state = Path(state_path)
    if not state.is_absolute():
        state = (ROOT / state).resolve()
    if not state.exists():
        print(f"状态文件不存在: {state}", file=sys.stderr)
        return 1

    replies_root = Path(replies_dir)
    if not replies_root.is_absolute():
        replies_root = (ROOT / replies_root).resolve()
    if not replies_root.exists() or not replies_root.is_dir():
        print(f"回复目录不存在或不是目录: {replies_root}", file=sys.stderr)
        return 1

    out_json_path = Path(out_path)
    if not out_json_path.is_absolute():
        out_json_path = (ROOT / out_json_path).resolve()

    reply_files = sorted(
        [p for p in replies_root.glob("*.txt") if p.is_file()],
        key=lambda p: p.name,
    )
    if not reply_files:
        print(f"回复目录中未找到任何 .txt 文件: {replies_root}", file=sys.stderr)
        return 1

    timeline: list[dict] = []
    first_drift_reply: str | None = None
    first_drift_turn_index: int | None = None
    first_drift_status: str | None = None

    for idx, rp in enumerate(reply_files, start=1):
        reply_text = _read_reply_text(rp)
        try:
            report = run_check_from_text(str(state), reply_text)
        except Exception as e:
            print(f"trace-drift: 第 {idx} 轮（{rp.name}）检查失败: {e}", file=sys.stderr)
            return 1

        final_status = report.get("final_status", "unknown")
        violations = _collect_violations(report)

        timeline.append(
            {
                "turn_index": idx,
                "reply_file": rp.name,
                "final_status": final_status,
                "violations": violations,
            }
        )

        if final_status != "ok" and first_drift_reply is None:
            first_drift_reply = rp.name
            first_drift_turn_index = idx
            first_drift_status = final_status

    summary = {
        "total_replies": len(reply_files),
        "first_drift_reply": first_drift_reply,
        "first_drift_turn_index": first_drift_turn_index,
        "first_drift_status": first_drift_status,
    }

    out_json = {
        "summary": summary,
        "timeline": timeline,
    }

    ensure_outputs_dir()
    out_json_path.write_text(json.dumps(out_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown 报告路径：与 JSON 同名不同后缀
    out_md_path = out_json_path.with_suffix(".md")
    lines: list[str] = []
    lines.append("# Trace Drift Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total replies: {summary['total_replies']}")
    if first_drift_reply is None:
        lines.append("- First drift reply: none")
        lines.append("- First drift turn index: none")
        lines.append("- First drift status: ok")
    else:
        lines.append(f"- First drift reply: {first_drift_reply}")
        lines.append(f"- First drift turn index: {first_drift_turn_index}")
        lines.append(f"- First drift status: {first_drift_status}")
    lines.append("")
    lines.append("## Timeline")
    lines.append("")
    for item in timeline:
        lines.append(f"### Turn {item['turn_index']} — {item['reply_file']}")
        lines.append(f"- Status: {item['final_status']}")
        if item["violations"]:
            lines.append("- Violations:")
            for v in item["violations"]:
                lines.append(f"  - {v}")
        else:
            lines.append("- Violations: none")
        lines.append("")

    out_md_path.write_text("\n".join(lines), encoding="utf-8")

    # 额外写入解释版 Markdown（不影响原有 JSON/MD）
    try:
        explained_text = explain_trace_drift(out_json)
        explained_md_path = out_json_path.with_name(f"{out_json_path.stem}_explained.md")
        explained_md_path.write_text(explained_text, encoding="utf-8")
    except Exception:
        # 解释层失败不应影响主逻辑
        pass

    print(f"Trace drift JSON saved to: {out_json_path}")
    print(f"Trace drift Markdown saved to: {out_md_path}")
    return 0


def cmd_guard_chat(
    state_path: str,
    model: str,
    scenario: str,
    provider_model: str | None,
    prompt: str,
    out_path: str | None,
) -> int:
    """
    v2-alpha/beta: runtime guard wrapper.
    model=mock -> MockWrapper(scenario); model=openai -> OpenAIWrapper(provider_model).
    Produces a result bundle: enhanced_prompt + ai_response + guard_result + readable_summary.
    """
    model = (model or "mock").strip().lower()
    if model == "openai":
        try:
            wrapper = OpenAIWrapper(model=provider_model or "gpt-4o-mini")
        except ValueError as e:
            print(f"guard-chat: {e}", file=sys.stderr)
            return 1
    else:
        wrapper = MockWrapper(scenario=scenario or "clean")
    try:
        bundle = guard_chat(model_wrapper=wrapper, state_path=state_path, user_prompt=prompt)
    except Exception as e:
        print(f"guard-chat 失败: {e}", file=sys.stderr)
        return 1

    ensure_outputs_dir()
    out_json = Path(out_path) if out_path else (OUTPUTS_DIR / "live_guard_result.json")
    if not out_json.is_absolute():
        out_json = (ROOT / out_json).resolve()
    out_json.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    out_md = out_json.with_suffix(".md")
    out_md.write_text(bundle.get("readable_summary", ""), encoding="utf-8")

    _safe_print(bundle.get("readable_summary", ""))
    _safe_print(f"\nSaved: {out_json}")
    _safe_print(f"Saved: {out_md}")
    return 0


def cmd_run(session_path: str, output_path: str | None) -> int:
    """prepare + 若提供 --output 则做 check。"""
    path = _resolve_session_path(session_path)
    if not path.exists():
        print(f"Session 不存在: {path}", file=sys.stderr)
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("import_mode") == "history_import":
        state_text = _format_imported_state_summary(data)
        constraints_text = "\n".join(data.get("critical_constraints") or [])
        print("=" * 60)
        print("Memory Guard — run（导入状态）")
        print("=" * 60)
        print("\n--- Current effective state ---")
        print(state_text)
        print("\n--- Critical constraints ---")
        print(constraints_text)
        if output_path:
            out_path = Path(output_path) if Path(output_path).is_absolute() else (ROOT / output_path).resolve()
            if out_path.exists() and check_output_drift:
                sentinels = _imported_state_to_sentinels(data)
                report = check_output_drift(out_path.read_text(encoding="utf-8"), sentinels, state_text)
                print("\n--- Output drift check ---")
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(f"\n未找到输出文件 {out_path}，跳过 check。")
        print("=" * 60)
        return 0
    if run_experiment is None:
        print("cursor_guard_experiment 未可用", file=sys.stderr)
        return 1
    result = run_experiment(path, mode="guard")
    print("=" * 60)
    print("Memory Guard — run（prepare）")
    print("=" * 60)
    print("\n--- Current effective state ---")
    print(result["current_state_summary"])
    print("\n--- Critical constraints ---")
    print(result["critical_constraints_summary"])
    print("\n--- Enhanced prompt ---")
    print(result["enhanced_prompt"][:2000] + ("..." if len(result["enhanced_prompt"]) > 2000 else ""))
    if output_path:
        out_path = Path(output_path) if Path(output_path).is_absolute() else (ROOT / output_path).resolve()
        if out_path.exists():
            session = json.loads(path.read_text(encoding="utf-8"))
            report = check_output_drift(
                out_path.read_text(encoding="utf-8"),
                session.get("sentinels") or {},
                result["current_state_summary"],
            )
            print("\n--- Output drift check ---")
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"\n未找到输出文件 {out_path}，跳过 check。")
    else:
        print("\n提示：可用 memoryguard check <output.txt> --session <session.json> 检查模型输出。")
    print("=" * 60)
    return 0


def cmd_benchmark(args_list: list[str]) -> int:
    """跑 Memory Drift Benchmark。"""
    try:
        import drift_benchmark
    except ImportError:
        print("drift_benchmark 未可用", file=sys.stderr)
        return 1
    old_argv = sys.argv
    sys.argv = ["drift_benchmark.py"] + args_list
    try:
        return drift_benchmark.main()
    finally:
        sys.argv = old_argv


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory Guard CLI — 防 AI 记忆偏移")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_p = sub.add_parser("analyze", help="分析文件：提取事件 + 冲突检测 + 总结")
    analyze_p.add_argument("file", help="会议记录或聊天记录文件路径（txt/md/docx）")
    prepare_p = sub.add_parser("prepare", help="输出 current state + constraints + enhanced prompt（默认 session_real_20plus.json）")
    prepare_p.add_argument("session", nargs="?", default=None, help="session JSON，默认 cursor_sessions/session_real_20plus.json")
    check_p = sub.add_parser("check", help="检查模型输出是否 drift")
    check_p.add_argument("output", help="模型输出文件路径")
    check_p.add_argument("--session", default=None, help="session JSON，默认 session_real_20plus.json")
    run_p = sub.add_parser("run", help="prepare + 可选 check")
    run_p.add_argument("--session", default=None, help="session JSON")
    run_p.add_argument("--output", default=None, help="若有则对输出做 drift check")
    bench_p = sub.add_parser("benchmark", help="跑 Memory Drift Benchmark")
    bench_p.add_argument("scenario", nargs="?", default=None, help="scenario JSON；若为 --all 则跑全部 30 个")
    bench_p.add_argument("--all", action="store_true", dest="bench_all", help="跑全部 scenarios")
    imp_p = sub.add_parser("import_history", help="从旧聊天记录导入状态（txt/md/json）")
    imp_p.add_argument("file", help="历史文件路径（.txt / .md / .json）")
    imp_p.add_argument("--out", default=None, help="输出 JSON 路径，默认 outputs/imported_state.json")
    imp_p.add_argument("--summary", default=None, help="输出摘要路径，默认 outputs/import_summary.md")
    imp_p.add_argument("--tail", type=int, default=None, metavar="N", help="只取最后 N 轮对话（大文件推荐，如 --tail 30）")
    imp_p.add_argument("--max-turns", type=int, default=None, metavar="N", dest="max_turns", help="只取前 N 轮对话")
    imp_p.add_argument("--chunked", action="store_true", help="分块+规则优先 pipeline（适合几万行大文件）")
    imp_p.add_argument("--chunk-size", type=int, default=2000, metavar="N", dest="chunk_size", help="分块行数，默认 2000（仅 --chunked 时有效）")
    imp_p.add_argument("--no-llm", action="store_true", dest="no_llm", help="分块时仅规则抽取，不调 LLM（仅 --chunked 时有效）")
    imp_p.add_argument("--event-log", default=None, dest="event_log", help="event_log 输出路径，默认 outputs/event_log.json")
    diff_p = sub.add_parser("guard-diff", help="列出当前 git diff 的改动文件（MVP diff guard）")
    gui_p = sub.add_parser("gui", help="打开 MemoryGuard Desktop 图形界面（不依赖 Cursor/Gemini）")
    trace_p = sub.add_parser("trace-drift", help="批量对多轮回答做 drift 检查并追踪首次偏移")
    trace_p.add_argument("--state", required=True, help="import_history 生成的 imported_state.json 路径")
    trace_p.add_argument("--replies", required=True, help="包含多轮回答 txt 文件的目录")
    trace_p.add_argument("--out", required=True, help="trace_drift.json 输出路径")
    guard_p = sub.add_parser("guard-chat", help="v2: prepare + model call + check + explain (mock or openai)")
    guard_p.add_argument("--state", required=True, help="import_history 生成的 imported_state.json 路径")
    guard_p.add_argument("--model", default="mock", choices=["mock", "openai"], help="mock 或 openai")
    guard_p.add_argument("--scenario", default="clean", choices=["clean", "drift"], help="仅 mock 时有效：clean/drift")
    guard_p.add_argument("--provider-model", default=None, dest="provider_model", help="openai 时模型名，默认 gpt-4o-mini")
    guard_p.add_argument("--prompt", required=True, help="用户请求文本")
    guard_p.add_argument("--out", default=None, help="输出 JSON 路径，默认 outputs/live_guard_result.json")
    args = parser.parse_args()
    if args.command == "analyze":
        return cmd_analyze(args.file)
    if args.command == "prepare":
        return cmd_prepare(args.session)
    if args.command == "check":
        return cmd_check(args.output, args.session)
    if args.command == "run":
        return cmd_run(args.session, args.output)
    if args.command == "import_history":
        if cmd_import_history is None:
            print("import_history 未可用", file=sys.stderr)
            return 1
        return cmd_import_history(
            args.file,
            args.out,
            args.summary,
            tail=args.tail,
            max_turns=args.max_turns,
            chunked=getattr(args, "chunked", False),
            chunk_size=getattr(args, "chunk_size", 2000),
            use_llm=not getattr(args, "no_llm", False),
            event_log_path=getattr(args, "event_log", None),
        )
    if args.command == "guard-diff":
        return cmd_guard_diff()
    if args.command == "gui":
        try:
            from memoryguard_gui import main as gui_main
            gui_main()
            return 0
        except ImportError as e:
            print(f"启动 GUI 失败: {e}", file=sys.stderr)
            return 1
    if args.command == "benchmark":
        bench_args = ["--all"] if getattr(args, "bench_all", False) else []
        if not bench_args and args.scenario:
            bench_args = [args.scenario]
        return cmd_benchmark(bench_args)
    if args.command == "trace-drift":
        return cmd_trace_drift(args.state, args.replies, args.out)
    if args.command == "guard-chat":
        return cmd_guard_chat(
            args.state,
            getattr(args, "model", "mock"),
            getattr(args, "scenario", "clean"),
            getattr(args, "provider_model", None),
            args.prompt,
            args.out,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
