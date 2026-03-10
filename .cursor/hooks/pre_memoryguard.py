import sys
import subprocess
from pathlib import Path


def main() -> None:
    """Before-Submit hook: best-effort run memoryguard prepare on imported_state.json and dump output to latest_prepare.txt, then pass event through unchanged."""
    root = Path(__file__).resolve().parents[2]
    session_path = root / "outputs" / "imported_state.json"
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    if session_path.exists():
        try:
            proc = subprocess.run(
                ["py", "-3", "memoryguard.py", "prepare", str(session_path)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            (out_dir / "latest_prepare.txt").write_text(proc.stdout, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            (out_dir / "latest_prepare_error.txt").write_text(str(e), encoding="utf-8")

    # Pass-through hook payload: read stdin and echo back (to avoid interfering with Cursor)
    raw = sys.stdin.read()
    if raw:
        sys.stdout.write(raw)
    else:
        sys.stdout.write("{}")


if __name__ == "__main__":
    main()

