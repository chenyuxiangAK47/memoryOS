#!/usr/bin/env python3
"""
Memory Drift Benchmark：对比 Baseline LLM vs LLM + Memory Guard 的状态一致性。
用法：py -3 drift_benchmark.py [scenario_json]
      不传则跑 scenarios/drift_scenario_01.json
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from extractor import extract_events
from memory_guard import detect_conflicts_and_updates
from state_builder import build_state_snapshot, get_state_for_prompt

load_dotenv(Path(__file__).resolve().parent / ".env")
ROOT = Path(__file__).resolve().parent

# --all 时同时跑的 scenario 数，避免 API 限流
MAX_SCENARIO_WORKERS = 3


def turns_to_text(turns: list[dict]) -> str:
    """把多轮对话转成一段「会议/聊天记录」文本，便于 extract_events。"""
    lines = []
    for i, t in enumerate(turns, 1):
        role = t.get("role", "user")
        content = (t.get("content") or "").strip()
        if not content:
            continue
        speaker = "用户" if role == "user" else "助手"
        lines.append(f"Round {i} {speaker}：{content}")
    return "\n".join(lines)


def run_baseline(
    conversation_text: str,
    question: str,
    client: OpenAI,
) -> str:
    """Baseline A：整段对话 + 问题直接喂给 LLM，无状态治理。"""
    prompt = f"""以下是一段对话记录。请仅根据对话内容回答最后的问题，只输出当前结论，不要复述历史。

对话记录：
---
{conversation_text[:6000]}
---

问题：{question}

请直接回答（一句话或简短几句）："""
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return (r.choices[0].message.content or "").strip()


def run_baseline_recent(
    turns: list[dict],
    question: str,
    recent_n: int,
    client: OpenAI,
) -> str:
    """Baseline B：只截取最近 N 轮再问，模拟上下文被裁剪。"""
    if recent_n <= 0 or len(turns) <= recent_n:
        text = turns_to_text(turns)
    else:
        text = turns_to_text(turns[-recent_n:])
    return run_baseline(text, question, client)


def run_baseline_summary(
    conversation_text: str,
    question: str,
    client: OpenAI,
) -> str:
    """Baseline C：先让 LLM 做一次对话摘要，再基于摘要回答，模拟「总结后继续聊」的丢信息。"""
    summary_prompt = f"""请对以下对话做简短摘要（5 句以内），只保留关键事实与结论，不要遗漏重要更新（如时间、负责人、地点的变更）。

对话：
---
{conversation_text[:5000]}
---

摘要："""
    r1 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": summary_prompt}],
    )
    summary = (r1.choices[0].message.content or "").strip()
    q_prompt = f"""根据以下对话摘要回答问题。只输出当前结论。

摘要：
---
{summary}
---

问题：{question}

请直接回答："""
    r2 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": q_prompt}],
    )
    return (r2.choices[0].message.content or "").strip()


def run_guard_path(
    conversation_text: str,
    question: str,
    client: OpenAI,
) -> tuple[str, list, list, str]:
    """Guard 路径：提取事件 → Guard 检测 → 构建 current_state → 只把 state + 问题喂给 LLM。
    返回 (answer, events, findings, state_str_for_display)。
    """
    events = extract_events(conversation_text, client=client)
    findings = detect_conflicts_and_updates(events, client=client) if len(events) >= 2 else []
    snapshot = build_state_snapshot(events, findings)
    state_str = get_state_for_prompt(snapshot)
    events_ref = "\n".join(f"  事件#{e.get('id')}: {e.get('content', '')}" for e in events[:20])
    prompt = f"""当前有效状态（已由 Memory Guard 从对话中提取）：
---
{state_str}
---

事件顺序（供参考，按时间）：
{events_ref}

用户问题：{question}

请仅根据上述「当前有效状态」和事件顺序回答，只输出当前结论。若有多步（如先 beta 再正式），必须在答案中写全；若存在冲突请说明。"""
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    answer = (r.choices[0].message.content or "").strip()
    return answer, events, findings, state_str


def evaluate_answer(
    answer: str,
    expected_key_facts: list[str],
    expected_avoid: list[str] | None = None,
) -> tuple[float, list[str]]:
    """
    评分：expected_key_facts 中每个出现则加分，expected_avoid 出现则扣分。
    匹配时忽略空格，便于「4月20日」与「4 月 20 日」等价。
    """
    expected_avoid = expected_avoid or []

    def norm(s: str) -> str:
        return "".join(s.lower().split())

    answer_norm = norm(answer)
    hits = sum(1 for k in expected_key_facts if norm(k) in answer_norm)
    penalty = sum(1 for k in expected_avoid if norm(k) in answer_norm)
    n = len(expected_key_facts)
    if n == 0:
        score = 1.0 if penalty == 0 else 0.0
    else:
        score = max(0.0, (hits / n) - penalty * 0.5)
    msgs = []
    for k in expected_key_facts:
        if norm(k) not in answer_norm:
            msgs.append(f"缺少: {k}")
    for k in expected_avoid:
        if norm(k) in answer_norm:
            msgs.append(f"不应出现: {k}")
    return min(1.0, score), msgs


def run_scenario(scenario_path: Path, client: OpenAI) -> dict:
    """跑一个 scenario，返回 Baseline A/B/C 与 Guard 的答案、得分、是否 drift。四路并行请求。"""
    data = json.loads(scenario_path.read_text(encoding="utf-8"))
    turns = data.get("turns", [])
    question = data.get("question", "")
    expected_key_facts = data.get("expected_key_facts", [])
    expected_avoid = data.get("expected_avoid", [])
    recent_turns = data.get("recent_turns", 6)  # Baseline B 只用最近 N 轮

    conversation_text = turns_to_text(turns)

    with ThreadPoolExecutor(max_workers=4) as executor:
        fa = executor.submit(run_baseline, conversation_text, question, client)
        fb = executor.submit(run_baseline_recent, turns, question, recent_turns, client)
        fc = executor.submit(run_baseline_summary, conversation_text, question, client)
        fg = executor.submit(run_guard_path, conversation_text, question, client)
        baseline_a_answer = fa.result()
        baseline_b_answer = fb.result()
        baseline_c_answer = fc.result()
        guard_answer, events, findings, guard_state_str = fg.result()

    def _norm(s: str) -> str:
        return "".join(s.lower().split())

    sa, ma = evaluate_answer(baseline_a_answer, expected_key_facts, expected_avoid)
    sb, mb = evaluate_answer(baseline_b_answer, expected_key_facts, expected_avoid)
    sc, mc = evaluate_answer(baseline_c_answer, expected_key_facts, expected_avoid)
    sg, mg = evaluate_answer(guard_answer, expected_key_facts, expected_avoid)

    drift_detected = bool(
        sg > sa or sg > sb or sg > sc
        or (expected_avoid and any(
            _norm(k) in _norm(baseline_a_answer) or _norm(k) in _norm(baseline_b_answer) or _norm(k) in _norm(baseline_c_answer)
            for k in expected_avoid
        ))
    )
    guard_wins = sg > min(sa, sb, sc)

    return {
        "scenario": data.get("name", scenario_path.name),
        "baseline_a_answer": baseline_a_answer,
        "baseline_b_answer": baseline_b_answer,
        "baseline_c_answer": baseline_c_answer,
        "guard_answer": guard_answer,
        "guard_state_seen": guard_state_str,
        "guard_events": events,
        "baseline_a_score": sa,
        "baseline_b_score": sb,
        "baseline_c_score": sc,
        "guard_score": sg,
        "drift_detected": drift_detected,
        "guard_wins": guard_wins,
        "events_count": len(events),
        "findings_count": len(findings),
        "expected_key_facts": expected_key_facts,
        "expected_avoid": expected_avoid,
    }


def main() -> int:
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg == "--all":
            scenario_paths = sorted((ROOT / "scenarios").glob("drift_*.json"))
            if not scenario_paths:
                print("未找到 scenarios/drift_*.json", file=sys.stderr)
                return 1
        else:
            scenario_paths = [Path(arg)]
    else:
        scenario_paths = [ROOT / "scenarios" / "drift_scenario_01.json"]

    if not scenario_paths or not scenario_paths[0].exists():
        print(f"Scenario 不存在: {scenario_paths[0]}", file=sys.stderr)
        return 1

    scenario_paths = [p for p in scenario_paths if p.exists()]
    if not scenario_paths:
        print("没有可用的 scenario 文件", file=sys.stderr)
        return 1

    client = OpenAI()
    results = []
    if len(scenario_paths) > 1:
        workers = min(MAX_SCENARIO_WORKERS, len(scenario_paths))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(lambda p: run_scenario(p, client), scenario_paths))
        for i, path in enumerate(scenario_paths):
            results[i]["_path"] = str(path)
    else:
        for scenario_path in scenario_paths:
            result = run_scenario(scenario_path, client)
            result["_path"] = str(scenario_path)
            results.append(result)

    # 汇总
    n = len(results)
    baseline_a_scores = [r["baseline_a_score"] for r in results]
    baseline_b_scores = [r["baseline_b_score"] for r in results]
    baseline_c_scores = [r["baseline_c_score"] for r in results]
    guard_scores = [r["guard_score"] for r in results]
    guard_wins = sum(1 for r in results if r["guard_wins"])
    drift_detected_count = sum(1 for r in results if r["drift_detected"])

    for i, result in enumerate(results):
        print("=" * 60)
        print(f"Memory Drift Benchmark — {result['scenario']}")
        print("=" * 60)
        print("Baseline A（全历史）:", result["baseline_a_answer"][:150] + ("..." if len(result["baseline_a_answer"]) > 150 else ""))
        print("  得分:", result["baseline_a_score"])
        print("Baseline B（最近 N 轮）:", result["baseline_b_answer"][:150] + ("..." if len(result["baseline_b_answer"]) > 150 else ""))
        print("  得分:", result["baseline_b_score"])
        print("Baseline C（先摘要再答）:", result["baseline_c_answer"][:150] + ("..." if len(result["baseline_c_answer"]) > 150 else ""))
        print("  得分:", result["baseline_c_score"])
        print("Guard:", result["guard_answer"][:150] + ("..." if len(result["guard_answer"]) > 150 else ""))
        print("  得分:", result["guard_score"])
        print()
        print("--- Guard 看到的当前状态 ---")
        print(result.get("guard_state_seen", "（无）"))
        print()
        print("--- 抽取到的事件（前 10 条）---")
        for e in (result.get("guard_events") or [])[:10]:
            print(f"  事件#{e.get('id')}: {e.get('content','')[:70]}")
        print()
        print("Guard 更优（高于任一 Baseline）:", result["guard_wins"], "| drift 检测:", result["drift_detected"])
        print()

    print("=" * 60)
    print("汇总指标")
    print("=" * 60)
    print(f"  场景数:           {n}")
    if n:
        print(f"  Baseline A 平均:  {sum(baseline_a_scores)/n:.2f}")
        print(f"  Baseline B 平均:  {sum(baseline_b_scores)/n:.2f}")
        print(f"  Baseline C 平均:  {sum(baseline_c_scores)/n:.2f}")
        print(f"  Guard 平均:       {sum(guard_scores)/n:.2f}")
    print(f"  Guard 更优次数:   {guard_wins} / {n}")
    print(f"  检测到 drift 次数: {drift_detected_count} / {n}")
    # Research-grade 指标（名称与 spec 对齐，部分为脚手架）
    if n:
        def _norm(s: str) -> str:
            return "".join((s or "").lower().split())
        latest_state_accuracy = sum(guard_scores) / n  # 当前：Guard 答案与 expected_key_facts 一致率
        guard_win_rate = guard_wins / n
        drift_detection_rate = drift_detected_count / n
        # constraint_violation_count：各路径答案中 expected_avoid 出现次数（忽略空格）
        violation_a = sum(1 for r in results for k in (r.get("expected_avoid") or []) if k and _norm(k) in _norm(r.get("baseline_a_answer") or ""))
        violation_b = sum(1 for r in results for k in (r.get("expected_avoid") or []) if k and _norm(k) in _norm(r.get("baseline_b_answer") or ""))
        violation_c = sum(1 for r in results for k in (r.get("expected_avoid") or []) if k and _norm(k) in _norm(r.get("baseline_c_answer") or ""))
        violation_g = sum(1 for r in results for k in (r.get("expected_avoid") or []) if k and _norm(k) in _norm(r.get("guard_answer") or ""))
        constraint_violation_count = violation_a + violation_b + violation_c + violation_g
        stale_reference_count = violation_a + violation_b + violation_c  # Baseline 中旧状态引用次数
        print()
        print("--- Research 指标（脚手架）---")
        print(f"  latest_state_accuracy:   {latest_state_accuracy:.2f}")
        print(f"  guard_win_rate:           {guard_win_rate:.2f}")
        print(f"  drift_detection_rate:     {drift_detection_rate:.2f}")
        print(f"  constraint_violation_count: {constraint_violation_count}")
        print(f"  stale_reference_count:   {stale_reference_count}")
        print("  (sentinel_retention_rate, conflict_resolution_accuracy: TODO)")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
