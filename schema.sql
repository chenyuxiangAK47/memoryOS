-- Memory OS MVP: 事件表（只追加，不修改）
-- PostgreSQL + pgvector

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    timestamp   TEXT,           -- 事件发生时间，如 2026-03-05 14:00
    person      TEXT,           -- 关联人物
    event_type  TEXT,           -- decision / requirement / problem / conclusion
    content     TEXT NOT NULL,  -- 事件核心内容
    importance  SMALLINT,       -- 1-5，只保留 >= 3
    source_chunk TEXT,          -- 原始文本片段，便于溯源
    embedding   vector(1536)   -- OpenAI text-embedding-3-small 维度
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_person ON events(person);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_importance ON events(importance);
-- 向量检索（按需）
CREATE INDEX IF NOT EXISTS idx_events_embedding ON events USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

COMMENT ON TABLE events IS 'Memory OS Event Log: 只追加，不修改';
