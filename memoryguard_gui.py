#!/usr/bin/env python3
"""
MemoryGuard Desktop — 本地小工具，不依赖 Cursor / Gemini 平台。
上传文件 → 点按钮 → 看结果。支持 Import History / Prepare / Check。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from utils import OUTPUTS_DIR, ROOT

# 使用 Tkinter（Python 自带）
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext, messagebox
except ImportError:
    print("需要 Python 自带 tkinter。", file=sys.stderr)
    sys.exit(1)


def _run_cmd(args: list[str], cwd: Path, out_text: tk.Text) -> int:
    """在 cwd 下执行 py memoryguard.py <args>，把 stdout/stderr 打到 out_text。"""
    out_text.delete("1.0", tk.END)
    out_text.insert(tk.END, f">>> py -3 memoryguard.py {' '.join(args)}\n\n")
    out_text.update()
    cmd = [sys.executable, str(ROOT / "memoryguard.py")] + args
    try:
        p = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in p.stdout:
            out_text.insert(tk.END, line)
            out_text.see(tk.END)
            out_text.update()
        p.wait()
        return p.returncode
    except Exception as e:
        out_text.insert(tk.END, f"执行出错: {e}\n")
        return 1


def main() -> None:
    root = tk.Tk()
    root.title("MemoryGuard Desktop")
    root.minsize(720, 520)
    root.geometry("900x580")

    # 默认路径
    out_dir = OUTPUTS_DIR
    default_state = str(out_dir / "imported_state.json")

    # ---------- 左侧：输入区 ----------
    left = ttk.Frame(root, padding=8)
    left.grid(row=0, column=0, sticky="nsew")

    ttk.Label(left, text="1. 历史文件（Import）", font=("", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
    var_history = tk.StringVar(value="")
    entry_history = ttk.Entry(left, textvariable=var_history, width=36)
    entry_history.grid(row=1, column=0, sticky="ew", pady=2)

    def browse_history():
        p = filedialog.askopenfilename(
            title="选择聊天记录",
            filetypes=[("Markdown/文本", "*.md *.txt"), ("JSON", "*.json"), ("All", "*")],
            initialdir=str(ROOT),
        )
        if p:
            var_history.set(p)

    ttk.Button(left, text="浏览…", command=browse_history).grid(row=1, column=1, padx=4)

    ttk.Label(left, text="2. 状态文件（Prepare/Check）", font=("", 10, "bold")).grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 4))
    var_session = tk.StringVar(value=default_state)
    entry_session = ttk.Entry(left, textvariable=var_session, width=36)
    entry_session.grid(row=3, column=0, sticky="ew")

    def browse_session():
        p = filedialog.askopenfilename(
            title="选择 session / imported_state.json",
            filetypes=[("JSON", "*.json"), ("All", "*")],
            initialdir=str(out_dir),
        )
        if p:
            var_session.set(p)

    ttk.Button(left, text="浏览…", command=browse_session).grid(row=3, column=1, padx=4)

    ttk.Label(left, text="3. 回答文件（Check 用）", font=("", 10, "bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 4))
    var_reply = tk.StringVar(value="")
    entry_reply = ttk.Entry(left, textvariable=var_reply, width=36)
    entry_reply.grid(row=5, column=0, sticky="ew")

    def browse_reply():
        p = filedialog.askopenfilename(
            title="选择模型输出/回答文件",
            filetypes=[("文本", "*.txt *.md"), ("All", "*")],
            initialdir=str(out_dir),
        )
        if p:
            var_reply.set(p)

    ttk.Button(left, text="浏览…", command=browse_reply).grid(row=5, column=1, padx=4)

    # ---------- 按钮区 ----------
    btn_frame = ttk.Frame(left)
    btn_frame.grid(row=6, column=0, columnspan=2, pady=16)

    out_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=70, height=22, font=("Consolas", 9))
    out_text.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

    def do_import():
        path = var_history.get().strip()
        if not path:
            messagebox.showwarning("提示", "请先选择历史文件（.md / .txt / .json）")
            return
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            messagebox.showerror("错误", f"文件不存在: {p}")
            return
        out_path = out_dir / "imported_state.json"
        summary_path = out_dir / "import_summary.md"
        _run_cmd(
            ["import_history", str(p), "--out", str(out_path), "--summary", str(summary_path)],
            ROOT,
            out_text,
        )
        var_session.set(str(out_path))

    def do_prepare():
        session = var_session.get().strip() or default_state
        p = Path(session)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            messagebox.showwarning("提示", f"状态文件不存在: {p}\n请先运行 Import History。")
            return
        _run_cmd(["prepare", str(p)], ROOT, out_text)
        prepare_out = out_dir / "latest_prepare.txt"
        try:
            r = subprocess.run(
                [sys.executable, str(ROOT / "memoryguard.py"), "prepare", str(p)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if r.stdout:
                prepare_out.parent.mkdir(parents=True, exist_ok=True)
                prepare_out.write_text(r.stdout, encoding="utf-8")
        except Exception:
            pass

    def do_check():
        reply_path = var_reply.get().strip()
        if not reply_path:
            messagebox.showwarning("提示", "请先选择要检查的回答文件（.txt）")
            return
        session = var_session.get().strip() or default_state
        rp = Path(reply_path)
        sp = Path(session)
        if not rp.is_absolute():
            rp = ROOT / rp
        if not sp.is_absolute():
            sp = ROOT / sp
        if not rp.exists():
            messagebox.showerror("错误", f"回答文件不存在: {rp}")
            return
        if not sp.exists():
            messagebox.showerror("错误", f"状态文件不存在: {sp}")
            return
        _run_cmd(["check", str(rp), "--session", str(sp)], ROOT, out_text)

    ttk.Button(btn_frame, text="Run Import", command=do_import).grid(row=0, column=0, padx=4)
    ttk.Button(btn_frame, text="Run Prepare", command=do_prepare).grid(row=0, column=1, padx=4)
    ttk.Button(btn_frame, text="Run Check", command=do_check).grid(row=0, column=2, padx=4)

    # ---------- 底部：导出 / 打开目录 ----------
    bottom = ttk.Frame(root, padding=8)
    bottom.grid(row=1, column=0, columnspan=2, sticky="ew")

    def open_output_dir():
        import os
        path = out_dir.resolve()
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)

    ttk.Button(bottom, text="打开输出目录 outputs/", command=open_output_dir).grid(row=0, column=0, padx=4)

    def export_check_json():
        """把当前输出区里最后一次 check 的 JSON 保存到 latest_check.json。"""
        text = out_text.get("1.0", tk.END)
        start = text.rfind("{")
        if start == -1:
            messagebox.showinfo("提示", "输出区未找到 JSON，请先执行 Run Check。")
            return
        end = text.rfind("}") + 1
        if end <= start:
            messagebox.showinfo("提示", "无法解析 JSON。")
            return
        try:
            js = json.loads(text[start:end])
            p = out_dir / "latest_check.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(js, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo("完成", f"已保存: {p}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    ttk.Button(bottom, text="导出 Check 结果为 JSON", command=export_check_json).grid(row=0, column=1, padx=4)

    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)
    left.columnconfigure(0, weight=1)

    out_text.insert(tk.END, "MemoryGuard Desktop — 选择文件后点击 Run Import / Prepare / Check。\n")
    out_text.insert(tk.END, f"输出目录: {out_dir}\n\n")
    root.mainloop()


if __name__ == "__main__":
    main()
