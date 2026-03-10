import sys
import json
import subprocess
from pathlib import Path


def _extract_text_from_value(val):
    if isinstance(val, str) and val.strip():
        return val

    if isinstance(val, list):
        parts = []
        for item in val:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        joined = "\n".join(p for p in parts if p.strip())
        return joined if joined.strip() else None

    if isinstance(val, dict):
        for key in ("text", "content", "message", "response"):
            inner = val.get(key)
            text = _extract_text_from_value(inner)
            if text:
                return text

    return None


def _extract_response_text(payload):
    if isinstance(payload, dict):
        for key in ("response", "agentResponse", "assistantMessage", "message", "content"):
            text = _extract_text_from_value(payload.get(key))
            if text:
                return text

        msgs = payload.get("messages")
        if isinstance(msgs, list):
            for msg in reversed(msgs):
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role") or msg.get("speaker")
                if role in ("assistant", "agent"):
                    text = _extract_text_from_value(msg.get("content"))
                    if text:
                        return text

    return None


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = sys.stdin.read()
    (out_dir / "latest_post_hook_raw.txt").write_text(
        raw if raw else "<EMPTY STDIN>",
        encoding="utf-8",
    )

    if not raw.strip():
        (out_dir / "latest_check_error.txt").write_text(
            "Empty stdin payload from Cursor hook",
            encoding="utf-8",
        )
        sys.stdout.write("{}")
        return

    payload = None
    try:
        payload = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        (out_dir / "latest_check_error.txt").write_text(
            f"JSON parse error: {e}\n\nRAW PAYLOAD:\n{raw}",
            encoding="utf-8",
        )
        sys.stdout.write(raw)
        return

    response_text = _extract_response_text(payload)

    if response_text is None:
        (out_dir / "latest_check_error.txt").write_text(
            f"No response text extracted.\n\nPAYLOAD:\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
            encoding="utf-8",
        )
        sys.stdout.write(raw)
        return

    session_path = out_dir / "imported_state.json"
    if not session_path.exists():
        alt = out_dir / "imported_state_session_real_20plus.json"
        if alt.exists():
            session_path = alt

    if not session_path.exists():
        (out_dir / "latest_check_error.txt").write_text(
            "No session state file found.",
            encoding="utf-8",
        )
        sys.stdout.write(raw)
        return

    output_path = out_dir / "latest_output.txt"
    output_path.write_text(response_text, encoding="utf-8")

    try:
        proc = subprocess.run(
            [
                "py",
                "-3",
                "memoryguard.py",
                "check",
                str(output_path),
                "--session",
                str(session_path),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        (out_dir / "latest_check.json").write_text(proc.stdout, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        (out_dir / "latest_check_error.txt").write_text(str(e), encoding="utf-8")

    sys.stdout.write(raw)


if __name__ == "__main__":
    main()



