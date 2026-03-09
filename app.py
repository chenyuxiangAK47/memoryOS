"""
AI Memory Guard Demo
发现会议/聊天中的状态变化、冲突与被覆盖的旧结论，减少 AI 记忆漂移。
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from extractor import extract_events
from memory_guard import (
    detect_conflicts_and_updates,
    format_finding_card,
    get_current_effective_state,
)
from summarizer import summarize
from utils import OUTPUTS_DIR, ensure_outputs_dir, get_word_count, read_file, split_text

st.set_page_config(page_title="AI Memory Guard Demo", page_icon="🛡️", layout="centered")
st.title("🛡️ AI Memory Guard")
st.caption("Detect updates, conflicts, and stale conclusions in meeting or chat memory · 帮 AI 识别旧结论、状态更新和记忆冲突")

# ---------- 1. 上传文件 ----------
st.subheader("1️⃣ 上传文件")
uploaded = st.file_uploader("支持 .txt / .md / .docx", type=["txt", "md", "docx"])

if not uploaded:
    st.info("请上传一份会议记录或聊天记录")
    st.stop()

try:
    raw_bytes = uploaded.read()
    suffix = Path(uploaded.name).suffix.lower()
    if suffix in (".txt", ".md"):
        text = raw_bytes.decode("utf-8", errors="ignore")
    elif suffix == ".docx":
        import io
        from docx import Document
        doc = Document(io.BytesIO(raw_bytes))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        text = raw_bytes.decode("utf-8", errors="ignore")
except Exception as e:
    st.error(f"读取文件失败: {e}")
    st.stop()

# ---------- 2. 提取事件 ----------
st.subheader("2️⃣ 提取事件")
if "events" not in st.session_state or st.button("重新提取事件"):
    with st.spinner("正在提取结构化事件..."):
        events = extract_events(text)
    st.session_state["events"] = events
    for k in ("guard_findings", "current_state", "summary"):
        st.session_state.pop(k, None)
    to_save = [
        {"id": e.get("id"), "timestamp": e.get("timestamp"), "speaker": e.get("speaker"), "event_type": e.get("event_type"), "content": e.get("content"), "importance": e.get("importance"), "source_chunk_id": e.get("source_chunk_id")}
        for e in events
    ]
    ensure_outputs_dir()
    OUTPUTS_DIR.joinpath("events.json").write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")
else:
    events = st.session_state["events"]

st.metric("字数", get_word_count(text))
st.metric("事件数", len(events))

# ---------- 3. 运行 Memory Guard ----------
st.subheader("3️⃣ 运行 Memory Guard")
if len(events) >= 2:
    if "guard_findings" not in st.session_state:
        with st.spinner("正在检测记忆冲突与状态更新..."):
            findings = detect_conflicts_and_updates(events)
        st.session_state["guard_findings"] = findings
    else:
        findings = st.session_state["guard_findings"]
    st.caption("已根据事件列表检测更新与冲突。")
    if st.button("重新运行 Memory Guard"):
        with st.spinner("重新检测中..."):
            findings = detect_conflicts_and_updates(events)
        st.session_state["guard_findings"] = findings
        st.session_state.pop("current_state", None)
        st.rerun()
else:
    findings = []
    st.info("事件数 ≥ 2 时可运行 Memory Guard；当前可点击「重新提取事件」或上传更长内容。")

# ---------- 输出三块结果 ----------
st.divider()
st.subheader("📋 输出结果")

# 第一块：当前有效状态
st.markdown("#### ① 当前有效状态")
st.caption("AI 应采用的「当前记忆」：上线计划、负责人、待办、风险与应对。")
if events:
    if "current_state" not in st.session_state and (findings or events):
        with st.spinner("归纳当前有效状态..."):
            current_state = get_current_effective_state(events, findings)
        st.session_state["current_state"] = current_state
    if "current_state" in st.session_state:
        st.markdown(st.session_state["current_state"])
else:
    st.info("请先提取事件。")

# 第二块：检测到的更新 / 冲突
st.markdown("#### ② 检测到的更新 / 冲突")
st.caption("哪些旧结论被覆盖、哪些存在矛盾。")
if findings:
    updates = [f for f in findings if f.get("type") == "update"]
    conflicts = [f for f in findings if f.get("type") == "conflict"]
    if updates:
        st.markdown("**🔄 状态更新**")
        for f in updates:
            st.markdown(format_finding_card(f))
            st.caption("")
    if conflicts:
        st.markdown("**⚠️ 冲突（需人工确认）**")
        for f in conflicts:
            st.markdown(format_finding_card(f))
            st.caption("")
else:
    if len(events) >= 2:
        st.success("未发现记忆冲突或状态更新。")
    else:
        st.info("事件数 ≥ 2 时可运行 Memory Guard 检测。")

# 第三块：最终总结 + 溯源
st.markdown("#### ③ 最终总结")
st.caption("核心决策、风险、待办；每条带来源。")
if st.button("生成总结"):
    with st.spinner("生成带溯源的总结..."):
        summary_text = summarize(events)
    st.session_state["summary"] = summary_text
if "summary" in st.session_state:
    st.markdown(st.session_state["summary"])

# 事件溯源（可折叠）
st.markdown("#### 🔗 事件溯源")
with st.expander("查看事件明细与原始片段"):
    if events:
        for e in events:
            with st.expander(f"事件#{e.get('id')} | {e.get('timestamp','')} {e.get('speaker','')} | {(e.get('content') or '')[:50]}..."):
                st.write("**类型**:", e.get("event_type"), "**重要性**:", e.get("importance"))
                st.write("**内容**:", e.get("content"))
                if e.get("source_chunk"):
                    st.caption("原始片段:")
                    st.text(e["source_chunk"][:500])
