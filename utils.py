"""
文件读取、文本分块、输出目录。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = ROOT / "outputs"
SAMPLE_DATA_DIR = ROOT / "sample_data"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def ensure_outputs_dir() -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUTS_DIR


def read_file(path: Path) -> str:
    """读取 txt / md / docx，返回纯文本。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    suf = path.suffix.lower()
    if suf in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suf == ".docx":
        try:
            from docx import Document
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise RuntimeError("需要安装 python-docx: pip install python-docx")
    raise ValueError(f"不支持的文件格式: {suf}，请使用 .txt / .md / .docx")


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """按长度分块，带重叠。"""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


def get_word_count(text: str) -> int:
    """粗略字数（含空格）。"""
    return len(text)
