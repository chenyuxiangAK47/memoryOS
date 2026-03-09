"""Memory OS MVP - 事件存储（Event Log）与检索."""
from __future__ import annotations

from typing import Any

from config import DATABASE_URL

# 可选：只有装了 pgvector 时才用向量
try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None
    execute_values = None


def get_conn():
    if not psycopg2 or not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL)


def save_events(events: list[dict[str, Any]]) -> int:
    """把事件只追加写入 events 表（不写 embedding，Day 5 再加）。"""
    conn = get_conn()
    if not events or not conn:
        return 0
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO events (timestamp, person, event_type, content, importance, source_chunk)
                VALUES %s
                """,
                [
                    (
                        e.get("timestamp") or "",
                        e.get("person") or "未知",
                        e.get("event_type") or "other",
                        e.get("content") or "",
                        e.get("importance", 3),
                        e.get("source_chunk") or "",
                    )
                    for e in events
                ],
            )
            conn.commit()
            return len(events)
    finally:
        conn.close()


def list_events(
    person: str | None = None,
    event_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """按人物、类型检索事件（MVP 先不用向量）。"""
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            q = "SELECT id, timestamp, person, event_type, content, importance, source_chunk FROM events WHERE 1=1"
            params = []
            if person:
                q += " AND person = %s"
                params.append(person)
            if event_type:
                q += " AND event_type = %s"
                params.append(event_type)
            q += " ORDER BY id LIMIT %s"
            params.append(limit)
            cur.execute(q, params)
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "timestamp": r[1],
                    "person": r[2],
                    "event_type": r[3],
                    "content": r[4],
                    "importance": r[5],
                    "source_chunk": r[6],
                }
                for r in rows
            ]
    finally:
        conn.close()
