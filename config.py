"""Memory OS MVP - 配置与常量."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/memoryos",
)

# 文本分块
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50

# 事件筛选
MIN_IMPORTANCE = 3

# 事件类型
EVENT_TYPES = ["decision", "requirement", "problem", "conclusion", "other"]
