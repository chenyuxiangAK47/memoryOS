"""最小测试：验证 OpenAI API 可用。"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from openai import OpenAI

client = OpenAI()

# 使用 Chat Completions API（与 MVP 一致；Responses API 需单独 endpoint）
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "用一句话解释什么是 Memory OS。"}],
)

text = response.choices[0].message.content
print(text)
