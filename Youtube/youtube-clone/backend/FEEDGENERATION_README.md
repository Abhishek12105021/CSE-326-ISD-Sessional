# Feed Generation & Video Recommendation System

## Overview

This document outlines the YouTube Clone's video feed generation and recommendation system. The system implements a **3-phase cold-start strategy** that transitions from pure trending content (for new users) to fully personalized recommendations (for engaged users).

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│  - Stores watch history (UUIDs) in localStorage     │
│  - Sends {guest_uuid, watched_video_ids} to backend │
│  - Gets watch duration from YouTube iframe API      │
└──────────────┬──────────────────────────────────────┘
               │ POST /api/guest/feed
               │ POST /api/guest/watch
               │
┌──────────────▼──────────────────────────────────────┐
│              FastAPI Backend                         │
│  - Recommendation Engine (3 phases)                  │
│  - RPC callers for Supabase functions               │
│  - Watch history tracking                            │
└──────────────┬──────────────────────────────────────┘
               │ REST API
               │
┌──────────────▼──────────────────────────────────────┐
│         Supabase (PostgreSQL + pgvector)             │
│  - videos (24,499 with 1024-dim embeddings)         │
│  - watch_history (user/guest interactions)          │
│  - RPC functions (search_videos, get_trending)      │
└─────────────────────────────────────────────────────┘
```

---

## 3-Phase Recommendation Strategy

### Phase 1: Absolute Cold Start (0 interactions)
**When**: New users with no watch history
**Goal**: 100% Exploration mode
**Strategy**:
```
50% Global Trending (top videos worldwide)
50% Local Trending (top videos from user's region)
```

**SQL Calls**:
- `get_trending(filter_country=None, pool_size=100, match_count=15)`
- `get_trending(filter_country=user_region, pool_size=50, match_count=15)`

**Example Flow**:
```python
# Guest has no watched videos
watched_count = 0
→ Use Phase 1
→ Generate 50/50 global + local mix
→ Return 30 diverse videos
```

---

### Phase 2: Warm-Up (1-4 interactions)
**When**: Users with limited watch history (prevents overfitting)
**Goal**: Balanced exploration + exploitation
**Strategy**:
```
30% Vector Search (semantic similarity to watched videos)
40% Trending (keep fresh, prevent filter bubble)
30% Local Discovery (regional relevance)
```

**Algorithm**:
1. Build taste vector from 1-4 watched video embeddings (mean pooling + normalization)
2. Search for semantically similar videos (global, no country filter for diversity)
3. Mix in trending videos
4. Add local region-specific trending

**Example Flow**:
```python
watched_count = 3
→ Use Phase 2
→ Build taste_vector from 3 watched videos
→ 30% semantic similar (~9 videos)
→ 40% trending global (~12 videos)
→ 30% local trending (~9 videos)
→ Return 30 combined videos
```

---

### Phase 3: Fully Personalized (5+ interactions)
**When**: Users with rich watch history
**Goal**: Exploitation mode with 4-bucket diversity
**Strategy**:
```
Bucket A (60%): Semantic / Same Region
  → Main anchor, primary personalization signal

Bucket B (20%): Semantic / Foreign Mix (affinity-weighted)
  → Secondary diversification across countries
  → Countries weighted by semantic similarity mean

Bucket C (10%): Trending / User Region
  → Fresh content from user's region
  → Random sample from top pool (prevents stale)

Bucket D (10%): Trending / Global Mix (40% per-country cap)
  → Global trending with country diversity
  → Prevents one region from dominating
```

**Algorithm**:
1. Build taste vector from 5+ watched video embeddings
2. **Bucket A**: `search_videos(taste, country=user_region, k=18)`
3. **Bucket B**:
   - Compute affinity for each foreign country (mean cosine similarity)
   - Probabilistically select 6 countries by affinity (no replacement)
   - Fetch semantic results per country with affinity-weighted slots
4. **Bucket C**: `get_trending(country=user_region, top_pool=50, k=3)`
5. **Bucket D**: `get_trending(country=None, top_pool=150, k=3, per_country_cap=40%)`
6. Combine all buckets (no duplicates), return 30 videos

**Example Flow**:
```python
watched_count = 12
→ Use Phase 3
→ Build taste_vector from 12 watched videos
→ Bucket A: 18 semantic similar (same country)
→ Bucket B: 6 semantic similar (foreign mix by affinity)
→ Bucket C: 3 trending (local)
→ Bucket D: 3 trending (global with diversity)
→ Return 30 total (diverse 4-bucket mix)
```

---

## Data Model

### Video IDs: Two Types

**Important**: The `videos` table has TWO different ID columns:

| Column | Type | Purpose | Example |
|--------|------|---------|---------|
| `id` | UUID | Primary key, internal DB ID | `a1b2c3d4-e5f6-...` |
| `video_id` | TEXT | YouTube video ID | `CV0J3Bq3BIc` |

**Frontend localStorage** stores: `["uuid-1", "uuid-2", "uuid-3"]` (using `videos.id` UUIDs)

**Backend references**:
- `watch_history.video_id` → points to `videos.id` (UUID)
- `videos.video_id` → YouTube ID for embedding iframe

---

### Database Tables

#### `videos` (24,499 rows, 10 countries)
```sql
CREATE TABLE videos (
    id UUID PRIMARY KEY,              -- Use this in localStorage
    video_id TEXT NOT NULL,           -- YouTube ID
    country_code VARCHAR(5),          -- 'US', 'GB', 'JP', etc.
    title TEXT,
    channel_title TEXT,
    category_name TEXT,
    thumbnail_link TEXT,
    views BIGINT,
    likes BIGINT,
    dislikes BIGINT,
    comment_count BIGINT,
    publish_time TIMESTAMPTZ,
    trending_date TEXT,
    trending_frequency INTEGER,       -- How many times trended
    velocity_score FLOAT,             -- Computed trending score (0-100)
    tags TEXT,                        -- Pipe-separated tags
    embedding vector(1024),           -- BGE-M3 dense embeddings
    UNIQUE(video_id, country_code)
);
```

#### `watch_history` (user/guest interactions)
```sql
CREATE TABLE watch_history (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    guest_uuid TEXT,                  -- For guests
    video_id TEXT NOT NULL,           -- References videos.id (UUID!)
    watch_duration_seconds INTEGER,   -- 0 until updated
    video_duration_seconds INTEGER,
    watch_percentage DECIMAL(5,2),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    CONSTRAINT check (user_id IS NOT NULL XOR guest_uuid IS NOT NULL)
);
```

---

## API Reference

See **[API_DOCUMENTATION.md](./API_DOCUMENTATION.md)** for detailed endpoint specifications.

### Quick Endpoint Summary

**Authenticated Users**:
```
GET  /api/feed?region=US&limit=30
GET  /api/trending?region=US&limit=30
GET  /api/categories
```

**Guest Users**:
```
POST /api/guest/feed          (with watch history DTO)
POST /api/guest/watch         (INSERT/UPDATE watch events)
POST /api/guest/session       (health check)
```

---

## Implementation Details

### File Structure

```
backend/app/
├── core/
│   ├── recommendation.py      # 3-phase feed generation logic
│   └── supabase.py
├── api/
│   └── routes/
│       ├── feed.py            # Authenticated user endpoints
│       ├── guest.py           # Guest user endpoints
│       ├── auth.py
│       └── deps.py
├── schemas/
│   ├── feed.py                # Request/response models
│   └── auth.py
├── utils/
│   ├── formatters.py          # View/timestamp/avatar formatting
│   └── __init__.py
├── db.py                       # Database functions & RPC callers
├── config.py
├── main.py                     # FastAPI app entry point
└── __init__.py
```

### Key Functions

**Recommendation Engine** (`core/recommendation.py`):
- `build_taste_vector_from_uuids(video_uuids)` → numpy (1024,) vector
- `compute_country_affinity(taste_vector, countries)` → {country: affinity}
- `generate_phase1_feed(region, total)` → list[dict]
- `generate_phase2_feed(taste_vector, region, total)` → list[dict]
- `generate_phase3_feed(taste_vector, region, total)` → list[dict]

**Database Functions** (`db.py`):
- `search_videos_semantic(embedding, country, k)` → RPC call
- `get_trending_videos(country, k, pool_size, exclude)` → RPC call
- `get_videos_by_uuids(uuids)` → fetch full video rows with embeddings
- `get_watch_history(user_id, limit)` → fetch user's watch history
- `insert_watch_history(user_id, guest_uuid, video_uuid)` → INSERT, return watch_id
- `update_watch_history(watch_id, duration)` → UPDATE with actual duration
- `get_all_country_embeddings(country)` → fetch ALL embeddings for affinity calculation

**Formatters** (`utils/formatters.py`):
- `format_views(count)` → "1.2M views"
- `format_timestamp(iso_date)` → "1 year ago"
- `generate_channel_avatar(name)` → URL
- `is_verified(views, likes)` → bool

---

## Watch History Tracking

### Two-Phase Recording

**Phase 1: User Clicks Video (INSERT)**
```
Frontend:
  - User clicks video in feed
  - Frontend calls: POST /api/guest/watch
  - Payload: { video_uuid, guest_uuid }
  - Frontend saves returned watch_id
  - Launches YouTube iframe

Backend:
  - INSERT into watch_history with watch_duration_seconds = 0
  - Return { watch_id: "uuid", success: true }
```

**Phase 2: User Leaves Video (UPDATE)**
```
Frontend:
  - User navigates away or closes iframe
  - Gets watch_duration from YouTube iframe API
  - Calls: POST /api/guest/watch
  - Payload: { video_uuid, watch_id, watch_duration_seconds, guest_uuid }

Backend:
  - UPDATE watch_history row with actual duration
  - Calculate watch_percentage = (duration / video_length) * 100
  - Update ended_at timestamp
  - Return { success: true }
```

---

## Testing Checklist

### Phase 1 (Cold Start)
- [ ] `POST /api/guest/feed` with empty `watched_video_ids`
- [ ] Verify response has `strategy: "phase_1_cold_start"`
- [ ] Verify 30 videos returned
- [ ] Videos should be mix of trending (global + local)
- [ ] No semantic similarity in results

### Phase 2 (Warm-Up)
- [ ] Get 3 video UUIDs from any endpoint
- [ ] `POST /api/guest/feed` with 3 `watched_video_ids`
- [ ] Verify response has `strategy: "phase_2_warm_up"`
- [ ] First ~9 videos should be semantically similar
- [ ] Next ~12 videos should be trending
- [ ] Last ~9 videos should be local trending

### Phase 3 (Personalized)
- [ ] Get 10+ video UUIDs
- [ ] `POST /api/guest/feed` with 10+ `watched_video_ids`
- [ ] Verify response has `strategy: "phase_3_personalized"`
- [ ] ~18 videos from user's region
- [ ] ~6 videos from foreign countries
- [ ] ~3 trending from user's region
- [ ] ~3 trending global
- [ ] No duplicate video_ids in response

### Watch Tracking
- [ ] `POST /api/guest/watch` with video_uuid, guest_uuid (INSERT)
- [ ] Verify `watch_id` returned
- [ ] `POST /api/guest/watch` with watch_id, duration (UPDATE)
- [ ] Verify `success: true`

### Categories
- [ ] `GET /api/categories`
- [ ] Verify includes "All" + all unique categories

---

## Performance Considerations

### Latency
- **Phase 1**: ~200ms (2 RPC calls)
- **Phase 2**: ~400ms (embedding fetch + 3 RPC calls)
- **Phase 3**: ~800ms (embedding fetches + 9 RPC calls for affinity + 4 RPC calls for buckets)

### Optimizations (Future)
1. **Cache taste vectors** in Redis (TTL: 5 mins)
2. **Batch embedding fetches** using Supabase batching
3. **Precompute country affinities** periodically (8 hour jobs)
4. **Use Supabase Edge Functions** for recommendation logic (closer to DB)
5. **Implement feed pagination** with cursor-based approach

### Limitations
- **Country affinity**: Fetches ALL embeddings per country (~2500 vectors × 1024 dims ≈ 10MB per country)
- **No caching**: Every request recalculates from scratch
- **No pagination**: Fixed limit approach
- **Category filtering**: Not implemented (UI only)

---

## Future Enhancements

1. **Video Duration**: Currently hardcoded to "10:00"
   - Fetch from YouTube Data API v3
   - Cache in videos table

2. **Channel Verification**: Currently heuristic (views > 100k)
   - Maintain separate channel metadata table
   - Track verified status per channel

3. **Search Endpoint**: Not yet implemented
   - Generate query embeddings
   - Use `search_videos` RPC with query embedding

4. **Similar Videos Sidebar**: Implement on video player page
   - Use single video embedding for similarity search

5. **Category Filtering**: Currently backend returns top 50 categories
   - Implement efficient filtering on `/api/feed` endpoint
   - Adjust bucket sizes dynamically for smaller pools

6. **Infinite Scroll**: Not yet implemented
   - Add offset-based pagination
   - Or implement cursor-based pagination

7. **Real-time Trending**: Recalculate velocity_score periodically
   - Database job to update scoring daily
   - Or compute on-the-fly from fresh interaction data

---

## Deployment

### Environment Variables Required
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
FRONTEND_URL=http://localhost:3000
```

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Run in production
gunicorn app.main:app --workers 4 --bind 0.0.0.0:8000
```

---

## Troubleshooting

### Common Issues

**Empty feed or fewer than expected videos**:
- Check if RPC functions exist in Supabase
- Verify Supabase credentials in .env
- Check if videos table is populated (should have 24,499 rows)

**Slow responses**:
- Country affinity calculation fetches all embeddings (slow)
- Phase 3 makes multiple RPC calls in sequence
- Consider implementing caching or edge functions

**Same videos in every feed**:
- Probability weighting in Phase 3 Bucket B may be skewed
- Check country affinity calculation
- Ensure sufficient videos in each country pool

**YouTube iframe not playing**:
- Verify video_id is correct (YouTube ID, not UUID)
- Check if video is embeddable
- Use video's actual publish_time for age verification

---

## References

- **Notebook**: `../Data/embed-engine-populate.ipynb` - Original 4-bucket strategy
- **SQL Functions**: `../Data/recommend.sql` - RPC definitions
- **Dataset**: `../Data/processed_youtube_global.csv` - 24,499 video metadata
- **Embeddings Model**: BAAI/bge-m3 (1024-dimensional)

---

**Last Updated**: March 26, 2026
**Status**: Production Ready
**Version**: 1.0.0
