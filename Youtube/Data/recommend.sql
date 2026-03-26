-- Semantic Similarity Search RPC
-- Uses pgvector's HNSW index for fast approximate nearest neighbor search
-- Receives JSON array and converts to vector for distance calculation
CREATE OR REPLACE FUNCTION search_videos(
  query_embedding jsonb,
  filter_country  text    DEFAULT NULL,
  match_count     int     DEFAULT 20
)
RETURNS TABLE (
  id                uuid,
  video_id          text,
  country_code      varchar,
  title             text,
  channel_title     text,
  category_name     text,
  thumbnail_link    text,
  views             bigint,
  velocity_score    float,
  cosine_similarity float
)
LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_embedding vector;
BEGIN
  -- Convert jsonb array to vector
  BEGIN
    v_embedding := (query_embedding::text)::vector;
  EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'Invalid embedding format: %', query_embedding::text;
  END;

  -- Return query results
  RETURN QUERY
  SELECT
    videos.id,
    videos.video_id,
    videos.country_code,
    videos.title,
    videos.channel_title,
    videos.category_name,
    videos.thumbnail_link,
    videos.views,
    videos.velocity_score,
    (1.0 - (videos.embedding <=> v_embedding))::float AS cosine_similarity
  FROM public.videos
  WHERE
    (filter_country IS NULL OR videos.country_code = filter_country)
    AND videos.embedding IS NOT NULL
  ORDER BY videos.embedding <=> v_embedding
  LIMIT match_count;
END;
$$;

-- Trending Videos RPC
-- Two-stage design:
--   Stage 1: Get top pool_size by velocity_score (uses composite index)
--   Stage 2: Randomize to avoid same videos every request
CREATE OR REPLACE FUNCTION get_trending(
  filter_country   text    DEFAULT NULL,
  match_count      int     DEFAULT 10,
  pool_size        int     DEFAULT 100,
  exclude_ids      text[]  DEFAULT ARRAY[]::text[]
)
RETURNS TABLE (
  id             uuid,
  video_id       text,
  country_code   varchar,
  title          text,
  channel_title  text,
  category_name  text,
  thumbnail_link text,
  views          bigint,
  velocity_score float
)
LANGUAGE sql STABLE AS $$
  SELECT
    id, video_id, country_code, title, channel_title,
    category_name, thumbnail_link, views, velocity_score
  FROM (
    SELECT
      id, video_id, country_code, title, channel_title,
      category_name, thumbnail_link, views, velocity_score
    FROM public.videos
    WHERE
      (filter_country IS NULL OR country_code = filter_country)
      AND (exclude_ids IS NULL OR ARRAY_LENGTH(exclude_ids, 1) IS NULL OR NOT (video_id = ANY(exclude_ids)))
      AND velocity_score > 0
      AND velocity_score IS NOT NULL
    ORDER BY velocity_score DESC
    LIMIT pool_size
  ) AS trending_pool
  ORDER BY RANDOM()
  LIMIT match_count;
$$;
