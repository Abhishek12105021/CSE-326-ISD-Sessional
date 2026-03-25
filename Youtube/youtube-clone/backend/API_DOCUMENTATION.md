# API Documentation - YouTube Clone Feed Generation System

## Base Information

**Base URL**: `http://localhost:8000` (development)
**Content Type**: `application/json`
**Authentication**: JWT Bearer token (for authenticated endpoints)
**Version**: 1.0.0
**FastAPI**: 0.109.0

---

## System Architecture

### Two User Types

**Authenticated Users**:
- Use JWT tokens from Supabase Auth (Google OAuth)
- Watch history stored in `watch_history` database table
- Access personalized feeds via `GET /api/feed`

**Guest Users**:
- No authentication required
- Watch history managed by frontend in localStorage (UUIDs from `videos.id`)
- Access feeds via `POST /api/guest/feed` with watch history in request body

### Video ID System

**Important**: Videos table has TWO ID columns:
```sql
videos (
    id UUID PRIMARY KEY,           -- Use this in localStorage
    video_id TEXT NOT NULL         -- YouTube ID for iframe embedding
)
```

- **Frontend localStorage** stores: `["uuid-1", "uuid-2"]` (using `videos.id`)
- **watch_history.video_id** references `videos.id` (UUID)
- **responses include both** `id` (UUID) and `video_id` (YouTube ID)

---

## Table of Contents

1. [Health & Utility](#health--utility)
2. [Authenticated Endpoints](#authenticated-endpoints)
3. [Guest Endpoints](#guest-endpoints)
4. [Data Models](#data-models)
5. [3-Phase Strategy](#3-phase-strategy)
6. [Testing Guide](#testing-guide)
7. [Error Handling](#error-handling)

---

## Health & Utility

### GET /health

**Description**: Check if the API is running and healthy.

**Authentication**: None required

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "auth_provider": "supabase"
}
```

**curl Example**:
```bash
curl -X GET "http://localhost:8000/health"
```

---

### GET /api/categories

**Description**: Fetch all available video categories from the database.

**Authentication**: None required

**Response**: `200 OK`
```json
{
  "categories": [
    "All",
    "Comedy",
    "Entertainment",
    "Film & Animation",
    "Gaming",
    "Howto & Style",
    "Music",
    "News & Politics",
    "People & Blogs",
    "Science & Technology",
    "Sports"
  ]
}
```

**curl Example**:
```bash
curl -X GET "http://localhost:8000/api/categories"
```

---

## Authenticated Endpoints

### GET /api/feed

**Description**: Generate personalized video feed for authenticated users. Uses 3-phase recommendation strategy based on watch history stored in database.

**Authentication**: Required - JWT Bearer token from Supabase Auth

**Headers**:
```
Authorization: Bearer <jwt_token>
```

**Query Parameters**:
| Parameter | Type | Required | Default | Max | Description |
|-----------|------|----------|---------|-----|-------------|
| `region` | string | No | `"US"` | - | User's region code (US, GB, JP, DE, FR, IN, KR, MX, RU, CA) |
| `limit` | integer | No | `30` | `50` | Number of videos to return |

**3-Phase Strategy**:
- **Phase 1** (0 interactions): 50% global trending + 50% local trending
- **Phase 2** (1-4 interactions): 30% semantic + 40% trending + 30% local
- **Phase 3** (5+ interactions): 4-bucket strategy (60% semantic local + 20% semantic foreign + 10% trending local + 10% trending global)

**Response**: `200 OK` - [FeedResponse](#feedresponse)

**curl Example**:
```bash
curl -X GET "http://localhost:8000/api/feed?region=US&limit=30" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Example Response** (Phase 3):
```json
{
  "videos": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "video_id": "CV0J3Bq3BIc",
      "title": "Black Mirror - Black Museum | Official Trailer [HD] | Netflix",
      "thumbnail": "https://i.ytimg.com/vi/CV0J3Bq3BIc/default.jpg",
      "channel": {
        "name": "Netflix",
        "avatar": "https://ui-avatars.com/api/?name=Netflix&background=8B5CF6&color=fff&size=36",
        "verified": true,
        "id": "Netflix"
      },
      "views": "391K views",
      "timestamp": "1 year ago",
      "duration": "10:00",
      "category": "Entertainment",
      "velocity_score": 1.5944
    }
    // ... 29 more videos with strategic distribution:
    // ~18 from same region (Bucket A)
    // ~6 from foreign countries (Bucket B)
    // ~3 trending from user's region (Bucket C)
    // ~3 trending global mix (Bucket D)
  ],
  "strategy": "phase_3_personalized",
  "interaction_count": 12,
  "total": 30
}
```

**Possible Errors**:
- `401 Unauthorized` - Missing/invalid JWT token
- `422 Validation Error` - Invalid region or limit parameter
- `500 Internal Server Error` - Database/RPC function issues

---

### GET /api/trending

**Description**: Get pure trending videos without personalization. Always returns trending content using Phase 1 strategy.

**Authentication**: None required

**Query Parameters**:
| Parameter | Type | Required | Default | Max | Description |
|-----------|------|----------|---------|-----|-------------|
| `region` | string | No | `"US"` | - | Filter trending videos by region |
| `limit` | integer | No | `30` | `50` | Number of trending videos to return |

**Response**: `200 OK` - [FeedResponse](#feedresponse)

**curl Example**:
```bash
curl -X GET "http://localhost:8000/api/trending?region=JP&limit=20"
```

**Example Response**:
```json
{
  "videos": [
    {
      "id": "f6g7h8i9-j0k1-l2m3-n4o5-p6q7r8s9t0u1",
      "video_id": "dQw4w9WgXcQ",
      "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
      "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
      "channel": {
        "name": "RickAstleyVEVO",
        "avatar": "https://ui-avatars.com/api/?name=RickAstleyVEVO&background=8B5CF6&color=fff&size=36",
        "verified": true,
        "id": "RickAstleyVEVO"
      },
      "views": "1.2B views",
      "timestamp": "15 years ago",
      "duration": "10:00",
      "category": "Music",
      "velocity_score": 99.8234
    }
    // ... 19 more trending videos
  ],
  "strategy": "trending_only",
  "interaction_count": 0,
  "total": 20
}
```

---

## Guest Endpoints

### POST /api/guest/session

**Description**: Health check for guest sessions. Acknowledges guest session creation but doesn't persist data. Used for API compatibility.

**Authentication**: None required

**Request Body** (`GuestSessionRequest`):
```json
{
  "guest_uuid": "string",      // Required - guest identifier from frontend
  "region": "string",          // Optional - guest region
  "language": "string",        // Optional - guest language
  "device_type": "string"      // Optional - device type
}
```

**Response**: `200 OK`
```json
{
  "guest_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "interaction_count": 0,
  "created_at": "2026-03-26T10:30:00.000Z"
}
```

**curl Example**:
```bash
curl -X POST "http://localhost:8000/api/guest/session" \
     -H "Content-Type: application/json" \
     -d '{
       "guest_uuid": "123e4567-e89b-12d3-a456-426614174000",
       "region": "US"
     }'
```

---

### POST /api/guest/feed

**Description**: Generate personalized feed for guest users. Receives watch history from frontend localStorage and applies 3-phase recommendation strategy.

**Authentication**: None required

**Request Body** (`GuestFeedRequest`):
```json
{
  "guest_uuid": "string",          // Required - guest identifier
  "region": "string",              // Optional, default "US"
  "limit": "number",               // Optional, default 30, max 50
  "watched_video_ids": ["string"]  // Optional - array of UUIDs from videos.id
}
```

**Field Details**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `guest_uuid` | string | ✅ | - | Unique identifier for guest (generated by frontend) |
| `region` | string | ❌ | `"US"` | Region code for local content (US, GB, JP, etc.) |
| `limit` | integer | ❌ | `30` | Videos to return (1-50) |
| `watched_video_ids` | array | ❌ | `[]` | UUIDs from videos.id table (from localStorage) |

**Phase Determination**:
- **0 UUIDs** → Phase 1 Cold Start (50% global + 50% local trending)
- **1-4 UUIDs** → Phase 2 Warm-Up (30% semantic + 40% trending + 30% local)
- **5+ UUIDs** → Phase 3 Personalized (4-bucket: 60/20/10/10)

**Response**: `200 OK` - [FeedResponse](#feedresponse)

**curl Examples**:

**Cold Start (0 interactions)**:
```bash
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{
       "guest_uuid": "guest-123",
       "region": "US",
       "limit": 10,
       "watched_video_ids": []
     }'
```

**Warm-Up (3 interactions)**:
```bash
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{
       "guest_uuid": "guest-123",
       "region": "US",
       "limit": 10,
       "watched_video_ids": [
         "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
         "b2c3d4e5-f6a7-8901-bcde-f23456789012",
         "c3d4e5f6-a7b8-9012-cdef-345678901234"
       ]
     }'
```

**Example Response** (Warm-Up):
```json
{
  "videos": [
    // First ~3 videos: semantically similar to watched content
    // Next ~4 videos: global trending
    // Last ~3 videos: regional trending
  ],
  "strategy": "phase_2_warm_up",
  "interaction_count": 3,
  "total": 10
}
```

**Errors**:
- `422 Validation Error` - Invalid request format
- `500 Internal Server Error` - Database/embedding issues

---

### POST /api/guest/watch

**Description**: Track watch events for guest users. Supports INSERT (on video click) and UPDATE (on video unload) modes.

**Authentication**: None required

**Two Usage Modes**:

#### MODE 1: INSERT (User Clicks Video)

**When**: User clicks video in feed, before launching iframe
**Purpose**: Create watch_history record, get watch_id for later update

**Request Body**:
```json
{
  "video_uuid": "string",      // Required - UUID from videos.id
  "guest_uuid": "string"       // Required - guest identifier
}
```

**Response**: `200 OK`
```json
{
  "watch_id": "w4t5c6h7-i8d9-a0b1-c2d3-e4f5g6h7i8j9",
  "success": true
}
```

**curl Example**:
```bash
curl -X POST "http://localhost:8000/api/guest/watch" \
     -H "Content-Type: application/json" \
     -d '{
       "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
       "guest_uuid": "123e4567-e89b-12d3-a456-426614174000"
     }'
```

#### MODE 2: UPDATE (User Leaves Video)

**When**: User navigates away or closes video
**Purpose**: Update watch record with actual duration from YouTube iframe API

**Request Body**:
```json
{
  "video_uuid": "string",              // Required - same UUID as INSERT
  "watch_id": "string",                // Required - from INSERT response
  "watch_duration_seconds": "number",  // Required - from YouTube iframe API
  "guest_uuid": "string"               // Required - same guest as INSERT
}
```

**Response**: `200 OK`
```json
{
  "success": true
}
```

**curl Example**:
```bash
curl -X POST "http://localhost:8000/api/guest/watch" \
     -H "Content-Type: application/json" \
     -d '{
       "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
       "watch_id": "w4t5c6h7-i8d9-a0b1-c2d3-e4f5g6h7i8j9",
       "watch_duration_seconds": 45,
       "guest_uuid": "123e4567-e89b-12d3-a456-426614174000"
     }'
```

**Complete Watch Flow**:
```
1. User clicks video in feed
   ↓ Frontend: POST /api/guest/watch (INSERT mode)
   ↓ Backend: Creates watch_history row, returns watch_id
   ↓ Frontend: Saves watch_id, launches YouTube iframe

2. User watches video for X seconds
   ↓ YouTube iframe API provides playback duration

3. User leaves/navigates away
   ↓ Frontend: POST /api/guest/watch (UPDATE mode)
   ↓ Backend: Updates watch_duration, calculates percentage
   ↓ Database: Updates interaction counts via triggers
```

---

## 3-Phase Strategy

### Phase 1: Absolute Cold Start (0 interactions)

**Trigger**: User has no watch history
**Strategy**: 100% Exploration mode
**Composition**: 50% Global Trending + 50% Local Trending

**SQL Operations**:
1. `get_trending(filter_country=None, match_count=15, pool_size=100)`
2. `get_trending(filter_country=user_region, match_count=15, pool_size=50, exclude_ids=global_results)`

**Why**: No taste vector can be built, so rely on trending content with regional preference.

---

### Phase 2: Warm-Up (1-4 interactions)

**Trigger**: User has limited watch history
**Strategy**: Balanced exploration + exploitation (prevents overfitting)
**Composition**: 30% Vector Search + 40% Trending + 30% Local

**Algorithm**:
1. Build taste vector from watched video embeddings (mean pooling + normalization)
2. `search_videos(taste_vector, filter_country=None, match_count=9)` - global semantic search for diversity
3. `get_trending(filter_country=None, match_count=12)` - global trending
4. `get_trending(filter_country=user_region, match_count=9)` - local trending

**Why**: Limited history could cause overfitting (e.g., clicked one tech video → only tech). Mix with trending keeps feed diverse.

---

### Phase 3: Fully Personalized (5+ interactions)

**Trigger**: User has rich watch history
**Strategy**: 4-Bucket Golden Ratio (exploitation mode)
**Composition**:

**Bucket A (60%)** - Semantic / Same Region:
- `search_videos(taste_vector, filter_country=user_region, match_count=18)`
- Main personalization anchor

**Bucket B (20%)** - Semantic / Foreign Mix:
- Compute country affinity: `affinity[country] = mean(all_embeddings[country] · taste_vector)`
- Convert to probabilities, sample 3-6 countries without replacement
- `search_videos(taste_vector, filter_country=each_chosen_country, match_count=1-2)`

**Bucket C (10%)** - Trending / User Region:
- `get_trending(filter_country=user_region, match_count=3, pool_size=50, exclude_ids=A+B)`
- Fresh content from user's region

**Bucket D (10%)** - Trending / Global Mix:
- `get_trending(filter_country=None, match_count=3, pool_size=150, exclude_ids=A+B+C)`
- Global trending with 40% per-country cap to prevent dominance

**Why**: Rich history allows confident personalization while maintaining strategic diversity across 4 distinct content sources.

---

## Data Models

### VideoResponse

```json
{
  "id": "string",                    // UUID from videos.id (DB primary key)
  "video_id": "string",              // YouTube video ID (for embedding)
  "title": "string",
  "thumbnail": "string",             // YouTube thumbnail URL
  "channel": {
    "name": "string",
    "avatar": "string",              // Generated ui-avatars.com URL
    "verified": "boolean",           // Heuristic: views > 100k or likes > 5k
    "id": "string"                   // Same as name for now
  },
  "views": "string",                 // Formatted: "1.2M views"
  "timestamp": "string",             // Relative: "1 year ago"
  "duration": "string",              // Hardcoded "10:00" for MVP
  "category": "string",
  "velocity_score": "number|null"    // Trending score (0-100), for debugging
}
```

### FeedResponse

```json
{
  "videos": "VideoResponse[]",       // Array of video objects
  "strategy": "string",              // Phase identifier
  "interaction_count": "number",     // Number of videos in watch history
  "total": "number"                  // Number of videos returned
}
```

### GuestFeedRequest

```json
{
  "guest_uuid": "string",            // Required: guest identifier
  "region": "string",                // Optional: default "US"
  "limit": "number",                 // Optional: default 30, max 50
  "watched_video_ids": "string[]"    // Optional: UUIDs from videos.id
}
```

### WatchEventRequest

```json
{
  "video_uuid": "string",            // Required: UUID from videos.id
  "watch_id": "string|null",         // Present only for UPDATE mode
  "watch_duration_seconds": "number|null",  // From YouTube API, UPDATE mode only
  "guest_uuid": "string|null"        // For guests
}
```

### WatchEventResponse

```json
{
  "watch_id": "string|null",         // Returned only on INSERT
  "success": "boolean"               // Always true if no error
}
```

### CategoriesResponse

```json
{
  "categories": "string[]"           // List starting with "All"
}
```

---

## Testing Guide

### Prerequisites

1. **Start backend server**:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

2. **Verify Supabase connection**:
   - Ensure `.env` has correct SUPABASE_URL and SUPABASE_SERVICE_KEY
   - Check `videos` table has ~24,499 rows
   - Verify `search_videos` and `get_trending` RPC functions exist

3. **Tools**: Postman, curl, or any HTTP client

---

### Test Sequence 1: Guest User Complete Journey

**Step 1: Cold Start Feed**
```bash
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{
       "guest_uuid": "test-guest-001",
       "region": "US",
       "limit": 5,
       "watched_video_ids": []
     }'
```

**Expected Result**:
- `strategy: "phase_1_cold_start"`
- `interaction_count: 0`
- 5 videos: mix of global and US trending
- Save 3 video UUIDs for next test

**Step 2: Click Video (INSERT Watch Event)**
```bash
# Use video UUID from Step 1 response
curl -X POST "http://localhost:8000/api/guest/watch" \
     -H "Content-Type: application/json" \
     -d '{
       "video_uuid": "REPLACE-WITH-UUID-FROM-STEP-1",
       "guest_uuid": "test-guest-001"
     }'
```

**Expected Result**:
- Response includes `watch_id`
- Save `watch_id` for Step 3

**Step 3: Update Watch Duration**
```bash
# Use watch_id from Step 2
curl -X POST "http://localhost:8000/api/guest/watch" \
     -H "Content-Type: application/json" \
     -d '{
       "video_uuid": "REPLACE-WITH-UUID-FROM-STEP-1",
       "watch_id": "REPLACE-WITH-WATCH-ID-FROM-STEP-2",
       "watch_duration_seconds": 30,
       "guest_uuid": "test-guest-001"
     }'
```

**Expected Result**:
- `success: true`
- Check database: watch_history table should have updated duration

**Step 4: Warm-Up Feed (After 3 interactions)**
```bash
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{
       "guest_uuid": "test-guest-001",
       "region": "US",
       "limit": 10,
       "watched_video_ids": [
         "REPLACE-WITH-UUID-1",
         "REPLACE-WITH-UUID-2",
         "REPLACE-WITH-UUID-3"
       ]
     }'
```

**Expected Result**:
- `strategy: "phase_2_warm_up"`
- `interaction_count: 3`
- First ~3 videos should be semantically similar to watched content
- Mix of trending content

**Step 5: Personalized Feed (After 8 interactions)**
```bash
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{
       "guest_uuid": "test-guest-001",
       "region": "US",
       "limit": 30,
       "watched_video_ids": [
         "uuid-1", "uuid-2", "uuid-3", "uuid-4",
         "uuid-5", "uuid-6", "uuid-7", "uuid-8"
       ]
     }'
```

**Expected Result**:
- `strategy: "phase_3_personalized"`
- `interaction_count: 8`
- 4-bucket distribution:
  - ~18 videos from US (Bucket A - semantic local)
  - ~6 videos from foreign countries (Bucket B - semantic foreign)
  - ~3 videos trending US (Bucket C - trending local)
  - ~3 videos trending global (Bucket D - trending global)

---

### Test Sequence 2: Authenticated User

**Prerequisites**: Valid JWT token from Supabase Auth

**Step 1: Get Authenticated Feed**
```bash
curl -X GET "http://localhost:8000/api/feed?region=US&limit=10" \
     -H "Authorization: Bearer YOUR-JWT-TOKEN-HERE"
```

**Expected Result**:
- Phase depends on user's watch history in database
- Response includes user's actual interaction count
- Videos personalized based on database history

**Step 2: Get Trending (No Auth)**
```bash
curl -X GET "http://localhost:8000/api/trending?region=JP&limit=5"
```

**Expected Result**:
- `strategy: "trending_only"`
- 5 trending videos from Japan
- No personalization

**Step 3: Get Categories**
```bash
curl -X GET "http://localhost:8000/api/categories"
```

**Expected Result**:
- Array starting with "All"
- Followed by alphabetical category names from database

---

### Test Sequence 3: Edge Cases

**Empty Database Test**:
```bash
# If no data in database
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{"guest_uuid": "test", "region": "XX", "limit": 30}'
```

**Expected**: Should handle gracefully or return appropriate error

**Invalid UUID Test**:
```bash
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{
       "guest_uuid": "test",
       "watched_video_ids": ["invalid-not-uuid", "another-invalid"]
     }'
```

**Expected**: Should filter out invalid UUIDs and continue

**Large History Test**:
```bash
# Test with 50+ video UUIDs
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{
       "guest_uuid": "test",
       "watched_video_ids": ["uuid1", "uuid2", ..., "uuid50"]
     }'
```

**Expected**: Should still use Phase 3, handle large history efficiently

---

### Performance Benchmarks

**Expected Response Times**:
- **Phase 1** (Cold Start): ~200ms (2 RPC calls)
- **Phase 2** (Warm-Up): ~400ms (embedding fetch + 3 RPC calls)
- **Phase 3** (Personalized): ~800ms (country affinity + 4 buckets)

**Testing Performance**:
```bash
# Test response time
time curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{"guest_uuid": "test", "region": "US", "watched_video_ids": []}'
```

---

## Error Handling

### Standard Error Format

```json
{
  "detail": "string"                 // Error message
}
```

### Common HTTP Status Codes

| Status | Meaning | Common Causes |
|--------|---------|---------------|
| 200 | OK | Success |
| 400 | Bad Request | Invalid request body, missing required fields |
| 401 | Unauthorized | Missing or invalid JWT token |
| 404 | Not Found | Endpoint not found |
| 422 | Validation Error | Pydantic validation failed |
| 500 | Internal Server Error | Database connection error, RPC function missing |

### Example Error Responses

**400 Bad Request**:
```json
{
  "detail": "Field 'guest_uuid' is required"
}
```

**401 Unauthorized**:
```json
{
  "detail": "Could not validate credentials"
}
```

**422 Validation Error**:
```json
{
  "detail": [
    {
      "loc": ["body", "limit"],
      "msg": "ensure this value is less than or equal to 50",
      "type": "value_error.number.not_le",
      "ctx": {"limit_value": 50}
    }
  ]
}
```

**500 Internal Server Error**:
```json
{
  "detail": "RPC function 'search_videos' not found in Supabase"
}
```

---

## Sample Workflows

### Guest User Journey

1. **Initial Visit (Cold Start)**:
   ```http
   POST /api/guest/feed
   Content-Type: application/json

   {
     "guest_uuid": "new-guest-uuid",
     "region": "US",
     "watched_video_ids": []
   }
   ```
   Response: 30 trending videos (strategy: "phase_1_cold_start")

2. **User Clicks First Video**:
   ```http
   POST /api/guest/watch
   Content-Type: application/json

   {
     "video_uuid": "video-uuid-from-feed",
     "guest_uuid": "new-guest-uuid"
   }
   ```
   Response: `{ "watch_id": "watch-uuid", "success": true }`

3. **User Watches for 45 seconds, then leaves**:
   ```http
   POST /api/guest/watch
   Content-Type: application/json

   {
     "video_uuid": "video-uuid-from-feed",
     "watch_id": "watch-uuid",
     "watch_duration_seconds": 45,
     "guest_uuid": "new-guest-uuid"
   }
   ```
   Response: `{ "success": true }`

4. **User Refreshes Feed (after watching 3 videos)**:
   ```http
   POST /api/guest/feed
   Content-Type: application/json

   {
     "guest_uuid": "new-guest-uuid",
     "region": "US",
     "watched_video_ids": ["uuid-1", "uuid-2", "uuid-3"]
   }
   ```
   Response: 30 partially personalized videos (strategy: "phase_2_warm_up")

5. **User Returns Later (after watching 10 videos)**:
   ```http
   POST /api/guest/feed
   Content-Type: application/json

   {
     "guest_uuid": "new-guest-uuid",
     "region": "US",
     "watched_video_ids": ["uuid-1", "uuid-2", ..., "uuid-10"]
   }
   ```
   Response: 30 fully personalized videos (strategy: "phase_3_personalized")

---

### Authenticated User Journey

1. **User Signs In**:
   - Frontend gets JWT from Supabase auth
   - Backend tracks watch history in database (linked to user_id)

2. **Get Personalized Feed**:
   ```http
   GET /api/feed?region=US&limit=30
   Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
   ```
   Response: Personalized feed based on database watch history

3. **Get Categories for Filter**:
   ```http
   GET /api/categories
   ```
   Response: All available categories for UI dropdown

---

## Rate Limits

Currently no rate limits implemented. Consider implementing:
- Guest endpoints: 100 requests/minute
- Authenticated endpoints: 500 requests/minute
- Watch tracking: 1000 requests/minute

### Common HTTP Status Codes

| Status | Meaning | When It Occurs |
|--------|---------|----------------|
| `200` | OK | Request successful |
| `400` | Bad Request | Invalid request body format |
| `401` | Unauthorized | Missing/invalid JWT token (authenticated endpoints only) |
| `404` | Not Found | Endpoint doesn't exist |
| `422` | Validation Error | Pydantic validation failed (invalid types, missing required fields) |
| `500` | Internal Server Error | Database connection issues, RPC function not found, server errors |

### Error Response Format

All endpoints return errors in FastAPI's standard format:

```json
{
  "detail": "Error description" | [validation_error_array]
}
```

### Example Error Scenarios

**Missing Required Field**:
```bash
# Request missing guest_uuid
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{"region": "US"}'
```

**Response** (`422`):
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "guest_uuid"],
      "msg": "Field required"
    }
  ]
}
```

**Invalid Limit Parameter**:
```bash
# limit > 50
curl -X GET "http://localhost:8000/api/trending?limit=100"
```

**Response** (`422`):
```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["query", "limit"],
      "msg": "Input should be less than or equal to 50"
    }
  ]
}
```

**Missing Authentication**:
```bash
# No Authorization header
curl -X GET "http://localhost:8000/api/feed"
```

**Response** (`401`):
```json
{
  "detail": "Not authenticated"
}
```

**Database Connection Error**:
```bash
# Wrong Supabase credentials
curl -X POST "http://localhost:8000/api/guest/feed" \
     -H "Content-Type: application/json" \
     -d '{"guest_uuid": "test", "region": "US"}'
```

**Response** (`500`):
```json
{
  "detail": "Could not connect to Supabase"
}
```

**RPC Function Missing**:
```json
{
  "detail": "RPC function 'search_videos' not found"
}
```

---

## Environment Variables

Required environment variables (create `.env` file):

```env
SUPABASE_URL=https://gqpxcspldebemsbpfpfi.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-for-verification
FRONTEND_URL=http://localhost:3000
```

**Security Notes**:
- NEVER commit `.env` to version control
- `SUPABASE_SERVICE_KEY` has full database access - keep secure
- `SUPABASE_JWT_SECRET` is used to verify user tokens

---

## Database Requirements

### Required Tables

**videos** (24,499 rows):
```sql
CREATE TABLE videos (
    id UUID PRIMARY KEY,              -- Use for localStorage
    video_id TEXT NOT NULL,           -- YouTube ID
    country_code VARCHAR(5),          -- US, GB, JP, etc.
    title TEXT,
    channel_title TEXT,
    category_name TEXT,
    thumbnail_link TEXT,
    views BIGINT,
    likes BIGINT,
    velocity_score FLOAT,             -- Trending score (0-100)
    publish_time TIMESTAMPTZ,
    embedding vector(1024),           -- BGE-M3 embeddings
    UNIQUE(video_id, country_code)
);
```

**watch_history**:
```sql
CREATE TABLE watch_history (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    guest_uuid TEXT,
    video_id TEXT NOT NULL,           -- References videos.id (UUID!)
    watch_duration_seconds INTEGER,
    watch_percentage DECIMAL(5,2),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ
);
```

### Required RPC Functions

**search_videos**:
```sql
CREATE OR REPLACE FUNCTION search_videos(
    query_embedding vector(1024),
    filter_country text,
    match_count int
) RETURNS TABLE(
    id uuid,
    video_id text,
    title text,
    channel_title text,
    category_name text,
    thumbnail_link text,
    views bigint,
    likes bigint,
    velocity_score float,
    publish_time timestamptz,
    country_code text
);
```

**get_trending**:
```sql
CREATE OR REPLACE FUNCTION get_trending(
    filter_country text,
    match_count int,
    pool_size int,
    exclude_ids text[]
) RETURNS TABLE(
    -- Same columns as search_videos
);
```

---

## Development Workflow

### Local Development Setup

1. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials
   ```

3. **Run server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. **Verify API**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/docs  # View in browser
   ```

### Testing New Features

1. **Test basic endpoints** (health, categories, trending)
2. **Test guest cold start** (no watch history)
3. **Test guest warm-up** (1-4 videos)
4. **Test guest personalized** (5+ videos)
5. **Test watch event tracking** (INSERT + UPDATE)
6. **Test authenticated endpoints** (with JWT token)

---

## Performance & Scaling

### Current Performance Characteristics

**Phase 1** (Cold Start):
- **Time**: ~200ms
- **Operations**: 2 RPC calls to get_trending
- **Scalability**: Excellent (no complex calculations)

**Phase 2** (Warm-Up):
- **Time**: ~400ms
- **Operations**: Embedding fetch + taste vector building + 3 RPC calls
- **Scalability**: Good (limited by embedding fetch)

**Phase 3** (Personalized):
- **Time**: ~800ms
- **Operations**: Embedding fetch + country affinity (9 countries × ~2500 embeddings) + 4 bucket RPC calls
- **Scalability**: Limited (country affinity calculation is expensive)

### Optimization Opportunities

**High Priority**:
1. **Cache taste vectors** in Redis (TTL: 5 minutes)
2. **Precompute country affinities** for active users (background job)
3. **Batch RPC calls** where possible

**Medium Priority**:
1. **Use Supabase Edge Functions** (move recommendation logic closer to data)
2. **Implement feed caching** with cache invalidation on new interactions
3. **Add database connection pooling**

**Low Priority**:
1. **Implement pagination** (cursor-based for better performance)
2. **Add rate limiting** per user/guest
3. **Compress embedding storage** using quantization

---

## OpenAPI Integration

FastAPI automatically generates comprehensive API documentation:

**Interactive Documentation**: http://localhost:8000/docs (Swagger UI)
**Alternative Documentation**: http://localhost:8000/redoc (ReDoc)
**OpenAPI Schema**: http://localhost:8000/openapi.json

### Features Available in /docs:
- ✅ Live API testing
- ✅ Request/response examples
- ✅ Schema validation
- ✅ Authentication testing (JWT Bearer)
- ✅ Model definitions
- ✅ Error response examples

---

## Troubleshooting

### Common Issues

**"RPC function not found"**:
- Run SQL scripts: `schema.sql`, `recommend.sql`, `user_auth.sql`
- Verify functions exist in Supabase SQL Editor

**"No videos returned"**:
- Check if `videos` table is populated (should have 24,499 rows)
- Verify embeddings exist (not NULL)
- Test RPC functions directly in Supabase

**Slow responses (>2 seconds)**:
- Country affinity calculation is expensive
- Consider implementing caching
- Reduce history limit in development

**Authentication errors**:
- Verify JWT_SECRET in environment matches Supabase
- Check JWT token format (should be valid Supabase token)
- Test with Supabase client first

**Empty embeddings**:
- Ensure embeddings were generated and uploaded
- Check notebook: `embed-engine-populate.ipynb`
- Verify embedding column is not NULL

### Debug Endpoints

Add these for debugging (not in production):

```python
@router.get("/debug/video/{uuid}")
async def debug_video(uuid: str):
    """Get single video by UUID with full details"""

@router.get("/debug/embeddings/{uuid}")
async def debug_embedding(uuid: str):
    """Get embedding vector for specific video"""

@router.post("/debug/similarity")
async def debug_similarity(video_uuid_1: str, video_uuid_2: str):
    """Test cosine similarity between two videos"""
```

---

## Changelog & Versioning

### Version 1.0.0 (March 26, 2026)
**✅ Features Added**:
- 3-phase cold-start recommendation system
- Guest user support with localStorage integration
- Authenticated user support with database persistence
- Watch event tracking (INSERT/UPDATE pattern)
- Country-based affinity weighting
- 4-bucket golden ratio strategy for personalized feeds
- Comprehensive error handling
- OpenAPI/Swagger documentation

**📊 Database**:
- 24,499 videos with BGE-M3 embeddings (1024-dim)
- 10 countries supported (US, GB, JP, DE, FR, IN, KR, MX, RU, CA)
- Verified embeddable video IDs only

**🔧 Technical**:
- FastAPI 0.109.0
- Supabase with pgvector extension
- Async HTTP client for database operations
- Numpy for vector operations

### Roadmap (Future Versions)

**Version 1.1.0** (Planned):
- Video search endpoint with query embeddings
- Real video durations from YouTube Data API
- Infinite scroll pagination
- Feed caching system

**Version 1.2.0** (Planned):
- Similar videos sidebar for video player
- Category filtering in backend
- Real-time trending score updates
- Performance optimizations

---

**Last Updated**: March 26, 2026
**Implementation Status**: ✅ Complete
**Testing Status**: 🧪 Ready for Postman
**Documentation Status**: 📚 Comprehensive