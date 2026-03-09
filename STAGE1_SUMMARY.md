# Memory Guard — Stage 1 Summary

One-page project summary after completing the first prototype and full benchmark.

---

## Problem

**LLM long-session memory drift.** In long conversations (meetings, chat logs, or coding-assistant sessions like Cursor), the model can forget earlier decisions, confuse old vs. new state, or retain overridden conclusions. This leads to wrong answers (“who is the owner?”, “what is the launch plan?”) and instruction retention failures (e.g. “always end with 喵” is dropped). The problem is not summarization alone—it is **tracking updates, conflicts, and the current effective state** over time.

---

## Approach

**Event-sourced memory + Guard + state reconstruction.**

1. **Event extraction** — From raw dialogue text, extract structured events (who, what, when, entity type: schedule / owner / location / etc.).
2. **Memory Guard** — Over the event stream, detect **updates** (later overwrites earlier) and **conflicts** (contradictions not yet resolved). Output product-ready findings with entity_key, old/new state, and recommendation.
3. **State reconstruction** — From events + Guard findings, build a **current state snapshot** (per entity_key: evolution + current value). No over-inference: only what was stated or updated is in state.
4. **Answering** — Feed **current state + question** to the LLM instead of full history (or in addition to it), so answers align with the latest, conflict-resolved state.

This is **Memory Guard for long-running AI sessions**: not a generic summarizer, but an event-based memory layer with drift detection and state reconstruction.

---

## Evaluation

**27-scenario Memory Drift Benchmark.**

- **Baselines:** A = full history; B = recent N turns (context cut); C = summarize then answer.
- **Guard path:** extract events → Guard → state snapshot → state + question → LLM.
- **Metrics:** per-scenario scores (expected_key_facts / expected_avoid), Guard win rate, drift detection rate, constraint violations, stale references.

**Baseline numbers (Stage 1 run):**

| Metric | Value |
|--------|-------|
| Scenarios | 27 |
| Baseline A avg | 0.94 |
| Baseline B avg | 0.88 |
| Baseline C avg | 0.94 |
| Guard avg | 0.94 |
| Guard win rate | 6/27 (0.22) |
| Drift detection rate | 8/27 (0.30) |

Details: `BASELINE_NUMBERS.md`. Scenarios 18–27 add harder, meeting-style cases (interruption, negation, tentative→final, assistant misquote, long-distance, noise, multi-entity, resolved conflict, post-meeting correction, third-party + scope).

---

## Prototype

**Cursor Memory Guard experiment + CLI wrapper.**

- **Cursor Guard experiment** (`cursor_guard_experiment.py`): Simulates long coding-assistant sessions. Three modes—Baseline (history + prompt), State Injection (inject current state + constraints into prompt), Guard Mode (injection + output drift check). Supports **sentinels**: surface (e.g. “answer must end with 喵”), semantic (“do not modify DB layer”, “keep function name renderPlan”), state (“current owner is 李四”, “current plan: beta then 4/20 formal”).
- **Session format** (`cursor_sessions/session_01.json`): `history`, `current_prompt`, `sentinels` (surface / semantic / state).
- **CLI** (`memoryguard prepare / check / run`): `prepare` → current state + critical constraints + enhanced prompt; `check` → drift report on a model output (missing surface sentinel, semantic violations, stale state references); `run` → prepare + optional check.

**Deliverable form:** Local CLI / companion tool, not a Cursor plugin. The “喵” sentinel is used as an **instruction retention canary** to detect when the model drops user constraints in long sessions.

---

*Next: use `memoryguard prepare` and `memoryguard check` on real 20+ turn Cursor sessions to get a concrete feel for 喵, constraint, and state drift.*
