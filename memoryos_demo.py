"""
Memory OS Demo：一步完成「会议记录 → 事件提取 + 总结」
（与官方 Chat Completions API 一致，可直接跑通）
"""
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent / ".env")
client = OpenAI()

text = """
2026-03-05 14:00 张三：新功能A要推迟到4月10日上线。
2026-03-05 14:05 李四：原因是后端接口还没稳定。
2026-03-05 14:20 王五：本周先完成测试环境部署。
"""

prompt = f"""
你是一个 Memory OS 的事件提取器。
请从下面会议记录中提取结构化事件，并输出：
1. 核心决策
2. 风险
3. 待办事项

会议记录：
{text}
"""

# 使用 Chat Completions API（SDK 标准用法；与 test_openai / demo_mini 一致）
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
)

print(response.choices[0].message.content)
