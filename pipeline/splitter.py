"""Memory OS MVP - 文本分块."""
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_OVERLAP, CHUNK_SIZE


def get_splitter(
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", "。", " ", ""],
    )


def split_text(text: str, splitter: RecursiveCharacterTextSplitter | None = None) -> list[str]:
    """把长文本拆成小片段."""
    if splitter is None:
        splitter = get_splitter()
    return splitter.split_text(text)
