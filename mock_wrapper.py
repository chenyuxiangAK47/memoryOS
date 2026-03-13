from __future__ import annotations

"""
Mock model wrapper for MemoryGuard v2-alpha.

- clean: always returns a constraint-compliant answer (ends with '喵')
- drift: returns an answer that violates database/backend/function-name constraints
"""

from runtime.wrappers.base import BaseModelWrapper


class MockWrapper(BaseModelWrapper):
    def __init__(self, scenario: str = "clean"):
        self.scenario = (scenario or "clean").strip().lower()

    def generate(self, prompt: str) -> str:
        # Keep behavior deterministic and offline.
        if self.scenario in ("drift", "violate", "bad"):
            return (
                "为了彻底解决性能问题，我建议从数据库、后端 API 和前端一起做“根因优化”。\n\n"
                "1) 数据库：修改数据库/改表结构，新增字段并加索引（schema migration）。\n"
                "2) 后端：修改后端/改 API，新增分页接口并调整 service 逻辑。\n"
                "3) 前端：rename getTodoList to fetchTodoListWithPagination，并更新调用方。\n\n"
                "这是跨层改动的完整方案。喵"
            )

        # clean
        return (
            "I'll keep this frontend-only and avoid any database or backend changes.\n"
            "I will keep the function name `getTodoList` unchanged and only optimize rendering and caching "
            "(e.g., list virtualization, memoization, incremental rendering). 喵"
        )

