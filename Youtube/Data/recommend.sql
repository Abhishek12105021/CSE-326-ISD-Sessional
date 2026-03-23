-- Semantic similarity search with optional country filter

-- search_videos is your semantic similarity engine. You pass it a 1024-dim taste vector (the mean-pooled watched history) and it uses pgvector's <=> operator to compute cosine distance between that vector and every embedding in the table. The HNSW index you created makes this fast — instead of scanning all 24k rows it approximates the nearest neighbours in milliseconds. filter_country lets you scope it to a single country, which is how Bucket A (same region) and Bucket B (foreign region) both work — same function, different filter_country value. Returns results ordered by similarity descending with the actual cosine score attached.

CREATE OR REPLACE FUNCTION search_videos(
  query_embedding vector(1024),
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
LANGUAGE sql AS $$
  SELECT
    id,
    video_id,
    country_code,
    title,
    channel_title,
    category_name,
    thumbnail_link,
    views,
    velocity_score,
    1 - (embedding <=> query_embedding) AS cosine_similarity
  FROM public.videos
  WHERE
    (filter_country IS NULL OR country_code = filter_country)
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


-- Trending videos with randomisation (for Bucket C / D)


-- get_trending is your trending injection for Buckets C and D. It doesn't use embeddings at all — purely sorts by velocity_score. The two-step design is intentional: first it takes the top pool_size (default 100) trending videos, then from that pool it picks match_count randomly using ORDER BY RANDOM(). This is exactly the randomisation we added in the notebook — same trending quality bar, different videos each request. exclude_ids takes an array of video_id strings already selected by Buckets A/B so there's zero overlap across buckets.

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
LANGUAGE sql AS $$
  SELECT
    id, video_id, country_code, title, channel_title,
    category_name, thumbnail_link, views, velocity_score
  FROM (
    SELECT *
    FROM public.videos
    WHERE
      (filter_country IS NULL OR country_code = filter_country)
      AND video_id != ALL(exclude_ids)
    ORDER BY velocity_score DESC
    LIMIT pool_size
  ) pool
  ORDER BY RANDOM()
  LIMIT match_count;
$$;
