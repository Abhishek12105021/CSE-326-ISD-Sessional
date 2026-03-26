-- Enable the pgvector extension for bge-m3 embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the Video Table
CREATE TABLE public.videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    video_id TEXT NOT NULL,
    country_code VARCHAR(5) NOT NULL,
    title TEXT,
    channel_title TEXT,
    category_name TEXT,
    thumbnail_link TEXT,
    VIEWS BIGINT DEFAULT 0,
    likes BIGINT DEFAULT 0,
    dislikes BIGINT DEFAULT 0,
    comment_count BIGINT DEFAULT 0,
    trending_date TEXT,
    publish_time TIMESTAMPTZ,
    trending_frequency INTEGER DEFAULT 1,
    velocity_score FLOAT DEFAULT 0.0,
    tags TEXT,
    embedding vector (1024),
    UNIQUE (video_id, country_code)
);

-- HNSW Index for semantic similarity search
-- Approximate nearest neighbor search via pgvector
CREATE INDEX ON public.videos USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200);

-- Composite index for trending videos
-- Covers: WHERE country_code = X ORDER BY velocity_score DESC LIMIT N
-- Includes all columns needed for the query (covering index)
CREATE INDEX idx_videos_trending_composite ON public.videos (
    country_code,
    velocity_score DESC,
    id,
    title,
    channel_title,
    category_name,
    thumbnail_link,
    VIEWS
)
WHERE
    velocity_score IS NOT NULL;

-- Partial index on velocity_score for global trending
-- Used when filter_country IS NULL
CREATE INDEX idx_videos_velocity_score ON public.videos (velocity_score DESC)
WHERE
    velocity_score > 0
    AND velocity_score IS NOT NULL;

-- Index on country_code for filtering
CREATE INDEX idx_videos_country ON public.videos (country_code);

-- Enable Row Level Security
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;

-- Allow public read access
CREATE POLICY "Allow public read access" ON public.videos FOR
SELECT TO public USING (TRUE);