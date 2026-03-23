-- 1. Enable the pgvector extension for bge-m3 embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the Video Table
CREATE TABLE public.videos (
    -- Internal unique ID (Primary Key)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- YouTube specific metadata
    video_id TEXT NOT NULL,
    country_code VARCHAR(5) NOT NULL, -- 'US', 'GB', etc.
    
    -- Display Information
    title TEXT,
    channel_title TEXT,
    category_name TEXT,
    thumbnail_link TEXT,
    
    -- Stats
    views BIGINT DEFAULT 0,
    likes BIGINT DEFAULT 0,
    dislikes BIGINT DEFAULT 0,
    comment_count BIGINT DEFAULT 0,
    
    -- Scoring & Tracking
    trending_date TEXT, -- Keeping as text initially for easy import
    publish_time TIMESTAMPTZ,
    trending_frequency INTEGER DEFAULT 1,
    velocity_score FLOAT DEFAULT 0.0,
    
    -- The Mega String Content (Optional, useful for debugging)
    tags TEXT,
    
    -- THE EMBEDDING (Replaces mega_string for search)
    -- bge-m3 uses 1024 dimensions
    embedding vector(1024),

    -- Ensure we don't have the exact same video for the exact same country twice
    UNIQUE(video_id, country_code)
);

-- 3. Create an index for faster similarity searches
-- We use IVFFlat or HNSW. HNSW is better for speed/accuracy.
CREATE INDEX ON public.videos USING hnsw (embedding vector_cosine_ops);

-- 4. Enable Row Level Security (Safety first!)
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;

-- 5. Allow anyone to read the data
CREATE POLICY "Allow public read access" 
ON public.videos FOR SELECT 
TO public 
USING (true);