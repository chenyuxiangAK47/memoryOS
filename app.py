from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Tuple

import gradio as gr

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS = BASE_DIR / "outputs"

from report_explainer import explain_check_result, explain_trace_drift


def _run_cli(args: list[str]) -> Tuple[int, str, str]:
    """调用 memoryguard.py CLI，返回 (returncode, stdout, stderr)。"""
    proc = subprocess.run(
        ["py", "-3", "memoryguard.py", *args],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def import_history_ui(file_obj):
    """
    上传历史文件后，点击 Import History：
    - 调用 import_history
    - 返回：state 文本、hard/soft 约束、摘要、内部 JSON 路径
    """
    if file_obj is None:
        return "请先上传历史文件。", "", "", "", ""

    src_path = Path(file_obj.name)
    tmp_path = OUTPUTS / f"ui_history{src_path.suffix}"
    tmp_path.write_bytes(src_path.read_bytes())

    out_json = OUTPUTS / "ui_imported_state.json"
    out_md = OUTPUTS / "ui_import_summary.md"

    code, out, err = _run_cli(
        [
            "import_history",
            str(tmp_path),
            "--chunked",
            "--no-llm",
            "--out",
            str(out_json),
            "--summary",
            str(out_md),
        ]
    )
    if code != 0 or not out_json.exists():
        msg = f"import_history 失败。\nstdout:\n{out}\n\nstderr:\n{err}"
        return msg, "", "", "", ""

    data = json.loads(out_json.read_text(encoding="utf-8"))

    state_items = data.get("current_effective_state") or []
    if state_items:
        state_text = "\n".join(f"- [{s.get('key','')}] {s.get('value','')}" for s in state_items)
    else:
        state_text = "（无）"

    constraints = data.get("critical_constraints") or []
    hard_keywords = ["不要", "不能", "不准", "不得", "禁止", "严禁", "不可以", "别动", "别改", "必须", "务必"]
    hard_patterns = ["不要动数据库", "不要改数据库", "不要动后端", "不要改后端", "只做前端", "只改前端"]
    hard, soft = [], []
    for raw in constraints:
        text = (raw or "").strip()
        if not text:
            continue
        is_hard = any(k in text for k in hard_keywords) or any(p in text for p in hard_patterns)
        if "喵" in text:
            is_hard = True
        (hard if is_hard else soft).append(text)
    hard_text = "\n".join(hard) or "（无）"
    soft_text = "\n".join(soft) or "（无）"

    summary_md = out_md.read_text(encoding="utf-8") if out_md.exists() else ""

    return state_text, hard_text, soft_text, summary_md, str(out_json)


def prepare_ui(imported_state_path: str) -> str:
    """根据导入的 state JSON 路径生成 Enhanced prompt。"""
    if not imported_state_path:
        return "请先做 Import History。"
    path = Path(imported_state_path)
    if not path.exists():
        return f"找不到状态文件: {path}"

    code, out, err = _run_cli(["prepare", str(path)])
    if code != 0:
        return f"prepare 失败。\nstdout:\n{out}\n\nstderr:\n{err}"
    return out


def check_ui(answer_text: str, imported_state_path: str):
    """粘贴回答文本，基于导入 state 做 drift 检查。"""
    if not imported_state_path:
        return "请先做 Import History。", ""
    if not answer_text.strip():
        return "请先粘贴 AI 回答文本。", ""

    session_path = Path(imported_state_path)
    if not session_path.exists():
        return f"找不到状态文件: {session_path}", ""

    out_txt = OUTPUTS / "ui_latest_output.txt"
    out_txt.write_text(answer_text, encoding="utf-8")

    code, out, err = _run_cli(["check", str(out_txt), "--session", str(session_path)])
    if code != 0:
        return f"check 失败。\nstdout:\n{out}\n\nstderr:\n{err}", "", ""

    report_text = out
    if "{" in out and "}" in out:
        try:
            start = out.index("{")
            end = out.rindex("}") + 1
            json_part = out[start:end]
            report = json.loads(json_part)
            final_status = report.get("final_status", "")
            readable = explain_check_result(report)
            return json.dumps(report, ensure_ascii=False, indent=2), final_status, readable
        except Exception:
            return report_text, "", ""
    return report_text, "", ""


def trace_drift_ui(state_path: str, replies_dir: str):
    """基于 state JSON + replies 目录运行 trace-drift，并返回 summary + timeline（markdown）+ 可读解释。"""
    if not state_path or not replies_dir:
        return "请先填写 state 和 replies 目录。", "", ""

    state = Path(state_path)
    replies = Path(replies_dir)
    if not state.exists():
        return f"找不到状态文件: {state}", "", ""
    if not replies.exists() or not replies.is_dir():
        return f"找不到回复目录: {replies}", "", ""

    out_json = OUTPUTS / "trace_drift.json"
    out_md = OUTPUTS / "trace_drift.md"

    code, out, err = _run_cli(
        [
            "trace-drift",
            "--state",
            str(state),
            "--replies",
            str(replies),
            "--out",
            str(out_json),
        ]
    )
    if code != 0 or not out_json.exists():
        return f"trace-drift 失败。\nstdout:\n{out}\n\nstderr:\n{err}", "", ""

    try:
        jd = json.loads(out_json.read_text(encoding="utf-8"))
    except Exception as e:
        return f"读取 trace_drift.json 失败: {e}", "", ""

    summary = jd.get("summary", {})
    summary_text = json.dumps(summary, ensure_ascii=False, indent=2)

    if out_md.exists():
        timeline_md = out_md.read_text(encoding="utf-8")
    else:
        timeline_md = json.dumps(jd, ensure_ascii=False, indent=2)

    readable = explain_trace_drift(jd)

    return summary_text, timeline_md, readable


def build_app() -> gr.Blocks:
    with gr.Blocks(title="MemoryGuard Local UI") as demo:
        gr.Markdown("## MemoryGuard — History Import / Prepare / Drift Check")

        imported_state_path = gr.State("")

        with gr.Tab("1. Import History"):
            upload = gr.File(label="上传历史聊天（.txt / .md / .json）")
            btn_import = gr.Button("Import History")
            state_box = gr.Textbox(label="Current effective state", lines=6)
            hard_box = gr.Textbox(label="Hard constraints", lines=6)
            soft_box = gr.Textbox(label="Soft constraints", lines=6)
            summary_box = gr.Textbox(label="Import summary (markdown)", lines=10)

            btn_import.click(
                import_history_ui,
                inputs=upload,
                outputs=[state_box, hard_box, soft_box, summary_box, imported_state_path],
            )

        with gr.Tab("2. Prepare Prompt"):
            gr.Markdown("基于导入状态生成 Enhanced prompt，复制到 Cursor 新 Chat 里使用。")
            btn_prep = gr.Button("Prepare Prompt")
            enhanced_box = gr.Textbox(label="Enhanced prompt", lines=20)
            btn_prep.click(prepare_ui, inputs=imported_state_path, outputs=enhanced_box)

        with gr.Tab("3. Check Drift"):
            answer_box = gr.Textbox(label="粘贴 AI 回答文本", lines=12)
            btn_check = gr.Button("Check Drift")
            report_box = gr.Textbox(label="Drift report", lines=16)
            status_box = gr.Textbox(label="final_status", lines=1)
            readable_box = gr.Textbox(label="Readable Summary", lines=6)
            btn_check.click(
                check_ui,
                inputs=[answer_box, imported_state_path],
                outputs=[report_box, status_box, readable_box],
            )

        with gr.Tab("4. Trace Drift"):
            gr.Markdown("基于 state JSON + 多轮 replies 目录，批量运行 trace-drift。")
            state_in = gr.Textbox(label="State file", value="outputs/imported_state_demo.json")
            replies_in = gr.Textbox(label="Replies dir", value="outputs/traceMd_replies")
            btn_trace = gr.Button("Run trace-drift")
            summary_box = gr.Textbox(label="Summary (JSON)", lines=8)
            timeline_box = gr.Textbox(label="Timeline (markdown)", lines=20)
            readable_trace_box = gr.Textbox(label="Readable Summary", lines=6)
            btn_trace.click(
                trace_drift_ui,
                inputs=[state_in, replies_in],
                outputs=[summary_box, timeline_box, readable_trace_box],
            )

        with gr.Tab("5. Live Guard"):
            gr.Markdown("v2：显式 runtime wrapper = prepare + model call + check + explain（mock 或 OpenAI）。")
            state_in = gr.Textbox(label="State file", value="outputs/imported_state_demo.json")
            provider_in = gr.Dropdown(label="Provider", choices=["mock", "openai"], value="mock")
            scenario_in = gr.Dropdown(label="Mock scenario（仅 mock 时有效）", choices=["clean", "drift"], value="clean")
            provider_model_in = gr.Textbox(label="Provider model（仅 openai 时有效）", value="gpt-4o-mini")
            prompt_in = gr.Textbox(label="User prompt", lines=4, value="Optimize todo loading for 5000+ items.")
            btn_live = gr.Button("Run Live Guard")

            enhanced_out = gr.Textbox(label="Enhanced prompt", lines=10)
            response_out = gr.Textbox(label="AI response", lines=10)
            guard_json_out = gr.Textbox(label="Guard result (JSON)", lines=10)
            readable_out = gr.Textbox(label="Readable Summary", lines=8)

            def live_guard_ui(
                state_path: str,
                provider: str,
                scenario: str,
                provider_model: str,
                user_prompt: str,
            ):
                if not state_path or not user_prompt:
                    return "", "", "请先填写 state 和 prompt。", ""
                args = [
                    "guard-chat",
                    "--state",
                    state_path,
                    "--model",
                    provider or "mock",
                    "--scenario",
                    scenario or "clean",
                    "--prompt",
                    user_prompt,
                    "--out",
                    str(OUTPUTS / "live_guard_result.json"),
                ]
                if (provider or "mock").strip().lower() == "openai" and (provider_model or "").strip():
                    args.extend(["--provider-model", (provider_model or "gpt-4o-mini").strip()])
                code, out, err = _run_cli(args)
                if code != 0:
                    return "", "", f"guard-chat 失败。\nstdout:\n{out}\n\nstderr:\n{err}", ""
                try:
                    jd = json.loads((OUTPUTS / "live_guard_result.json").read_text(encoding="utf-8"))
                except Exception as e:
                    return "", "", f"读取 live_guard_result.json 失败: {e}", ""
                enhanced = jd.get("enhanced_prompt", "")
                resp = jd.get("ai_response", "")
                guard_res = jd.get("guard_result", {})
                readable = jd.get("readable_summary", "")
                return enhanced, resp, json.dumps(guard_res, ensure_ascii=False, indent=2), readable

            btn_live.click(
                live_guard_ui,
                inputs=[state_in, provider_in, scenario_in, provider_model_in, prompt_in],
                outputs=[enhanced_out, response_out, guard_json_out, readable_out],
            )

    return demo


if __name__ == "__main__":
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    app = build_app()
    app.launch()