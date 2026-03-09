# API Key 保护说明

- **Key 只放在 `.env`**：项目已用 `.env` 存 `OPENAI_API_KEY`，代码里不写 key。
- **`.env` 已加入 `.gitignore`**：提交代码时不会把 `.env` 推上去，避免泄露。
- **不要把这些内容提交到仓库**：
  - `.env` 文件
  - 任何包含 `sk-proj-...` 或 `sk-...` 的文件
- **若 Key 曾在聊天/截图里出现过**：建议到 [OpenAI API keys](https://platform.openai.com/api-keys) 撤销旧 key，新建一个只在本机 `.env` 里使用。
- **本地运行**：用 `python-dotenv` 读 `.env`，不要用 `export OPENAI_API_KEY=...` 把 key 写在 shell 历史里（可选；用的话记得别把历史提交出去）。
