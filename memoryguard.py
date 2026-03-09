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
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from extractor import extract_events
from memory_guard import (
    detect_conflicts_and_updates,
    format_finding_card,
    get_current_effective_state,
)
from summarizer import summarize
from utils import OUTPUTS_DIR, ensure_outputs_dir, get_word_count, read_file, split_text

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
        print("=" * 60)
        print("Memory Guard — prepare（导入状态）")
        print("=" * 60)
        print("\n--- Current effective state ---")
        print(state_text)
        print("\n--- Hard constraints ---")
        print(hard_text)
        print("\n--- Soft constraints ---")
        print(soft_text)
        print("\n--- Enhanced prompt ---")
        print(enhanced)
        print("=" * 60)
        return 0
    if run_experiment is None:
        print("cursor_guard_experiment 未可用", file=sys.stderr)
        return 1
    result = run_experiment(path, mode="guard")
    print("=" * 60)
    print("Memory Guard — prepare（当前状态 + 约束 + 增强 prompt）")
    print("=" * 60)
    print("\n--- Current effective state ---")
    print(result["current_state_summary"])
    print("\n--- Critical constraints ---")
    print(result["critical_constraints_summary"])
    print("\n--- Enhanced prompt ---")
    print(result["enhanced_prompt"])
    print("=" * 60)
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
    session = json.loads(session_path_resolved.read_text(encoding="utf-8"))
    # 兼容导入状态文件
    if session.get("import_mode") == "history_import":
        if check_output_drift is None:
            print("cursor_guard_experiment 未可用", file=sys.stderr)
            return 1
        state_summary = _format_imported_state_summary(session)
        sentinels = _imported_state_to_sentinels(session)
        output_text = out_path.read_text(encoding="utf-8")
        report = check_output_drift(output_text, sentinels, state_summary)
        print("=" * 60)
        print("Memory Guard — output drift check")
        print("=" * 60)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("=" * 60)
        return 0
    if run_experiment is None or check_output_drift is None:
        print("cursor_guard_experiment 未可用", file=sys.stderr)
        return 1
    result = run_experiment(session_path_resolved, mode="guard")
    output_text = out_path.read_text(encoding="utf-8")
    report = check_output_drift(
        output_text,
        session.get("sentinels") or {},
        result["current_state_summary"],
    )
    print("=" * 60)
    print("Memory Guard — output drift check")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("=" * 60)
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
    if args.command == "benchmark":
        bench_args = ["--all"] if getattr(args, "bench_all", False) else []
        if not bench_args and args.scenario:
            bench_args = [args.scenario]
        return cmd_benchmark(bench_args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
