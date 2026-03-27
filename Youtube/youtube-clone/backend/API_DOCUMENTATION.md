# API Documentation - YouTube Clone Feed Generation System

## Base Information

**Base URL**: `http://localhost:8000` (development)
**Content Type**: `application/json`
**Authentication**: JWT Bearer token (for authenticated endpoints)
**Version**: 1.1.0 (Added Search & Recommendations)
**FastAPI**: 0.109.0

### Recent Updates (v1.1.0)
✨ **NEW Endpoints Added**:
- `POST /api/search` - Hybrid text search with semantic + keyword + category ranking
- `POST /api/recommend` - Find similar videos with context-aware scoring
- `POST /api/reload-search` - Lazy loading for infinite scroll search
- `POST /api/reload-recommend` - Lazy loading for infinite scroll recommendations

✨ **NEW Features**:
- Sentence-transformers/bge-m3 embeddings (1024-dim, int8 quantized to 600MB)
- FAISS vector similarity search
- Hybrid ranking algorithm (70% semantic + 20% keyword + 10% category)
- Category keyword detection for search intent
- Related category graph for recommendations
- Infinite scroll pagination without "has_more" flag

✨ **Documentation**:
- Detailed algorithm explanations for each endpoint
- Code comments in search.py with examples
- Frontend integration patterns and localStorage management
- Complete data model specifications
- Architecture diagrams and flow charts

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
2. [Authentication Endpoints](#authentication-endpoints)
3. [Authenticated User Endpoints](#authenticated-user-endpoints)
4. [Guest Endpoints](#guest-endpoints)
5. [Search & Recommendations](#search--recommendations)
6. [Reload/Lazy Loading](#reload-endpoints)
7. [Likes & Dislikes](#likes--dislikes)
8. [Subscriptions](#subscriptions)
9. [Video Metadata](#video-metadata)
10. [Watch Tracking](#watch-tracking)
11. [Data Models](#data-models)
12. [3-Phase Strategy](#3-phase-strategy)
13. [Testing Guide](#testing-guide)
14. [Error Handling](#error-handling)

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

## Authentication Endpoints

### GET /api/auth/profile

**Description**: Get authenticated user's complete profile combining JWT data + database settings.

**Authentication**: Required - JWT Bearer token

**Response**: `200 OK` - `UserProfile`
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "display_name": "John Doe",
  "avatar_url": "https://avatars.githubusercontent.com/u/...",
  "region": "US",
  "created_at": "2026-03-20T10:30:00Z"
}
```

**curl Example**:
```bash
curl -X GET "http://localhost:8000/api/auth/profile" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Details**:
- Fetches region from database (not in JWT)
- Auto-creates user on first call if doesn't exist
- Region defaults to "" (empty) for new users

---

### PUT /api/auth/profile

**Description**: Update user's profile (display_name and/or region).

**Authentication**: Required - JWT Bearer token

**Request Body** (`UpdateProfileRequest`):
```json
{
  "display_name": "New Name",    // Optional
  "region": "JP"                 // Optional (US, GB, JP, DE, FR, IN, KR, MX, RU, CA)
}
```

**Response**: `200 OK` - `UserProfile` (updated)

**curl Example**:
```bash
curl -X PUT "http://localhost:8000/api/auth/profile" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
     -H "Content-Type: application/json" \
     -d '{
       "region": "JP"
     }'
```

**Details**:
- Null values mean "don't update this field"
- Idempotent: calling twice with same data is safe
- Partial updates work (update region without changing display_name)
- Region affects recommendations: 60% of Phase 3 feed is from user's region

---

### POST /api/auth/logout

**Description**: Logout current session.

**Authentication**: Required - JWT Bearer token

**Response**: `200 OK`
```json
{
  "message": "Logged out successfully"
}
```

**curl Example**:
```bash
curl -X POST "http://localhost:8000/api/auth/logout" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**IMPORTANT**:
- Backend acknowledges logout only (cannot revoke JWT server-side)
- Frontend MUST delete JWT from localStorage
- Only logs out this device/session
- To logout all devices, use `/api/auth/logout-all`

---

### POST /api/auth/logout-all

**Description**: Logout from ALL devices/sessions.

**Authentication**: Required - JWT Bearer token

**Response**: `200 OK`
```json
{
  "message": "All sessions marked for logout. Frontend should call supabase.auth.signOut({ scope: 'global' })"
}
```

**curl Example**:
```bash
curl -X POST "http://localhost:8000/api/auth/logout-all" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Frontend Integration**:
```javascript
// After calling /api/auth/logout-all, frontend must revoke at Supabase:
const { error } = await supabase.auth.signOut({ scope: 'global' });

// This invalidates ALL JWT tokens issued to this user
// All devices must sign in again
```

**CRITICAL**:
- Backend endpoint only gives instructions
- Frontend MUST call `supabase.auth.signOut({ scope: 'global' })`
- Without this Supabase call, other devices' JWTs remain valid

---

## Authenticated User Endpoints

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

### POST /api/reload

**Description**: Lazy loading endpoint for authenticated users - reload feed with more videos excluding already-shown ones.

**Authentication**: Required - JWT Bearer token

**Request Body** (`ReloadFeedRequest`):
```json
{
  "excluded_video_ids": [
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    // ... all UUIDs from previous /feed and /reload calls
  ],
  "limit": 30
}
```

**Field Details**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `excluded_video_ids` | array | ❌ | `[]` | UUIDs to exclude from results |
| `limit` | integer | ❌ | `30` | Videos to return (1-50) |

**Response**: `200 OK` - [FeedResponse](#feedresponse)

**curl Example**:
```bash
curl -X POST "http://localhost:8000/api/reload" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
     -H "Content-Type: application/json" \
     -d '{
       "excluded_video_ids": ["uuid-1", "uuid-2", ..., "uuid-30"],
       "limit": 30
     }'
```

**How It Works**:
1. Uses same personalization logic as `/feed` (3-phase strategy)
2. Excludes all videos in `excluded_video_ids` list
3. Returns next batch of 20-30 new personalized videos
4. Guaranteed no duplicates with previous batch

**Frontend Implementation Pattern**:
```javascript
let allShownVideoIds = new Set();

// Step 1: Initial feed
async function initialFeed() {
  const response = await fetch('/api/feed?limit=30', {
    headers: { 'Authorization': `Bearer ${jwtToken}` }
  });
  const data = await response.json();
  data.videos.forEach(v => allShownVideoIds.add(v.id));
  displayVideos(data.videos);
}

// Step 2: Load more on infinite scroll
async function loadMore() {
  const response = await fetch('/api/reload', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`
    },
    body: JSON.stringify({
      excluded_video_ids: Array.from(allShownVideoIds),
      limit: 30
    })
  });

  const data = await response.json();
  data.videos.forEach(v => allShownVideoIds.add(v.id));
  displayVideos(data.videos);

  return data.total > 0;  // true if more available
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

### POST /api/like
**Description**: Like or unlike a video for authenticated user.

**Authentication**: Required - JWT Bearer token

**Request Body** (`LikeVideoRequest`):
```json
{
  "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response**: `200 OK` - `LikeResponse`
```json
{
  "success": true,
  "message": "Video liked successfully",
  "is_liked": true
}
```

---

### POST /api/dislike
**Description**: Dislike or remove dislike from a video for authenticated user.

**Authentication**: Required - JWT Bearer token

**Request Body** (`DislikeVideoRequest`):
```json
{
  "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response**: `200 OK` - `DislikeResponse`
```json
{
  "success": true,
  "message": "Video disliked successfully",
  "is_disliked": true
}
```

---

### POST /api/subscribe
**Description**: Subscribe or unsubscribe from a channel.

**Authentication**: Required - JWT Bearer token

**Request Body** (`SubscribeRequest`):
```json
{
  "channel_name": "Netflix"
}
```

**Response**: `200 OK` - `SubscriptionResponse`
```json
{
  "success": true,
  "message": "Subscribed to Netflix",
  "is_subscribed": true
}
```

---

## Search & Recommendations

### POST /api/search

**Description**: Full-text hybrid search combining semantic similarity, keyword matching, and category intelligence.

**Authentication**: None required

**Query Parameters**:
| Parameter | Type | Required | Default | Max | Description |
|-----------|------|----------|---------|-----|-------------|
| `q` | string | ✅ | - | 500 | Search query (e.g., "gaming tutorials", "bts band") |
| `limit` | integer | ❌ | `50` | `100` | Number of results to return |

**How It Works**:
1. **Embed Query**: Convert search text to 1024-dim vector using sentence-transformers/bge-m3
2. **FAISS Search**: Find 2x limit semantically similar videos from vector database
3. **Keyword Matching**: Count how many query words appear in video title
4. **Category Boost**: Detect category intent from query using category keywords
5. **Hybrid Ranking**: Combine scores: 70% semantic + 20% keyword + 10% category
6. **Return Top K**: Return top limit results sorted by combined score

**Request**:
```bash
curl -X POST "http://localhost:8000/api/search?q=gaming%20tutorials&limit=25"
```

**Response**: `200 OK`
```json
{
  "videos": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "video_id": "dQw4w9WgXcQ",
      "title": "How to Learn Gaming - Complete Tutorial",
      "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
      "channel": {
        "name": "Tech Tutorials",
        "avatar": "https://ui-avatars.com/api/?name=Tech%20Tutorials&background=8B5CF6&color=fff&size=36",
        "verified": true,
        "id": "Tech Tutorials"
      },
      "views": "1.2M views",
      "timestamp": "2 weeks ago",
      "duration": "10:00",
      "category": "Gaming",
      "velocity_score": 15.234
    },
    // ... 24 more results
  ],
  "query": "gaming tutorials",
  "total": 25
}
```

**Scoring Algorithm**:
```python
# For each result video:
faiss_score = cosine_similarity(query_embedding, video_embedding)  # 0.0-1.0
keyword_score = (matching_words / total_query_words)  # 0.0-1.0
category_boost = 0.2 if category_matches_intent else 0.0  # 0.0-0.2

combined_score = (
    faiss_score * 0.70 +
    keyword_score * 100 * 0.20 +
    category_boost * 100 * 0.10
)
```

**Frontend Integration**:
```javascript
// Frontend code to use /search

// 1. Send search query
const response = await fetch('/api/search?q=gaming%20tutorials&limit=25');
const data = await response.json();

// 2. Display videos
data.videos.forEach(video => {
  displayVideoCard(video);
  // Store video.id in a Set for lazy loading
  shownVideoIds.add(video.id);
});

// 3. For pagination, use /reload-search endpoint (see below)
```

**Supported Categories** (16 total):
Sports, Music, People & Blogs, Entertainment, News & Politics, Howto & Style, Travel & Events, Shows, Nonprofits & Activism, Autos & Vehicles, Gaming, Comedy, Film & Animation, Education, Pets & Animals, Science & Technology

---

### POST /api/recommend

**Description**: Find videos similar to a specific reference video with context-aware ranking.

**Authentication**: None required

**Query Parameters**:
| Parameter | Type | Required | Default | Max | Description |
|-----------|------|----------|---------|-----|-------------|
| `video_id` | string | ✅ | - | - | Reference video UUID (from videos.id, NOT YouTube ID) |
| `limit` | integer | ❌ | `15` | `50` | Number of recommendations to return |

**How It Works**:
1. **Get Reference**: Fetch reference video's embedding and metadata (title, category)
2. **Extract Keywords**: Parse reference title, remove common words, keep meaningful terms
3. **FAISS Search**: Find 2x limit semantically similar videos
4. **Score on Context**:
   - Shared keywords with reference title (+15% weight)
   - Same category as reference (+40% weight)
   - Related categories (+10% weight)
5. **Hybrid Ranking**: 70% semantic + 15% keywords + 15% category
6. **Exclude Self**: Never return the reference video itself

**Request**:
```bash
curl -X POST "http://localhost:8000/api/recommend?video_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890&limit=10"
```

**Response**: `200 OK`
```json
{
  "videos": [
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
      "video_id": "jLM2ibaRbrk",
      "title": "Flinch w/ Harry Styles",
      "thumbnail": "https://i.ytimg.com/vi/jLM2ibaRbrk/default.jpg",
      "channel": {
        "name": "The Late Late Show with James Corden",
        "avatar": "https://ui-avatars.com/api/?name=The%20Late%20Late%20Show%20with%20James%20Corden&background=8B5CF6&color=fff&size=36",
        "verified": true,
        "id": "The Late Late Show with James Corden"
      },
      "views": "3.2M views",
      "timestamp": "1 year ago",
      "duration": "10:00",
      "category": "Entertainment",
      "velocity_score": 12.456
    },
    // ... 9 more results
  ],
  "current_video_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "total": 10
}
```

**Category Relationships** (for related category boost):
- Music ↔ Entertainment, Shows
- Entertainment ↔ Music, Shows, Comedy
- Comedy ↔ Entertainment, People & Blogs
- Gaming ↔ Science & Technology
- Sports ↔ Entertainment
- Education ↔ Science & Technology
- Travel & Events ↔ People & Blogs, Entertainment
- Film & Animation ↔ Entertainment, Shows

**Frontend Integration**:
```javascript
// Frontend code for /recommend endpoint

// 1. User clicks "More Like This" on a video
const videoId = currentVideo.id;  // Store this UUID!

// 2. Fetch recommendations
const response = await fetch(`/api/recommend?video_id=${videoId}&limit=15`);
const data = await response.json();

// 3. Display sidebar or modal with similar videos
displayRecommendations(data.videos);

// 4. For pagination, use /reload-recommend (see below)
```

---

## Reload Endpoints

### POST /api/reload-search

**Description**: Lazy loading endpoint for infinite scrolling through search results. Returns next batch of semantically similar videos while excluding all previously shown results.

**Authentication**: None required

**Request Body** (`SearchReloadRequest`):
```json
{
  "q": "gaming tutorials",
  "excluded_video_ids": [
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    // ... all UUIDs from previous /search and previous /reload-search calls
  ],
  "offset": 0,
  "limit": 25
}
```

**Field Details**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `q` | string | ✅ | - | Original search query (same as /search) |
| `excluded_video_ids` | array | ❌ | `[]` | UUIDs already shown to user |
| `offset` | integer | ❌ | `0` | Pagination offset within filtered results |
| `limit` | integer | ❌ | `25` | Videos to return per reload (1-50) |

**How It Works**:
1. **Same Query Embedding**: Embed the query AGAIN to same 1024-dim vector
2. **FAISS Search**: Find K*2 + buffer (400-500) results
3. **Filter Exclusions**: Remove all videos in excluded_video_ids
4. **Apply Offset**: Get results from offset to offset+limit
5. **Re-rank**: Apply same hybrid ranking (70% semantic + 20% keyword + 10% category)
6. **Return**: Sorted unique results

**Request**:
```bash
curl -X POST "http://localhost:8000/api/reload-search" \
     -H "Content-Type: application/json" \
     -d '{
       "q": "gaming tutorials",
       "excluded_video_ids": ["uuid-1", "uuid-2", ..., "uuid-25"],
       "offset": 0,
       "limit": 25
     }'
```

**Response**: `200 OK`
```json
{
  "videos": [
    // Next 25 unique videos, semantically similar to query
  ],
  "query": "gaming tutorials",
  "total": 25,
  "offset": 0
}
```

**Frontend Implementation Pattern**:
```javascript
// Infinite scroll with /reload-search

let searchQuery = "gaming tutorials";
let allShownVideoIds = new Set();

// Step 1: Initial search
async function initialSearch() {
  const response = await fetch(`/api/search?q=${searchQuery}&limit=25`);
  const data = await response.json();

  data.videos.forEach(v => allShownVideoIds.add(v.id));
  displayVideos(data.videos);

  return data.videos.length > 0;
}

// Step 2: Reload on scroll
async function loadMore() {
  const response = await fetch('/api/reload-search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      q: searchQuery,
      excluded_video_ids: Array.from(allShownVideoIds),
      offset: 0,
      limit: 25
    })
  });

  const data = await response.json();

  data.videos.forEach(v => allShownVideoIds.add(v.id));
  displayVideos(data.videos);

  return data.total > 0;  // true if more available
}

// Step 3: User scrolls to bottom
window.addEventListener('scroll', () => {
  if (isNearBottom()) {
    loadMore();
  }
});
```

---

### POST /api/reload-recommend

**Description**: Lazy loading for continuous recommendations. Returns new recommendations for the same reference video, excluding all previously shown results.

**Authentication**: None required

**Request Body** (`ReloadRecommendRequest`):
```json
{
  "video_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "excluded_video_ids": [
    "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "c3d4e5f6-a7b8-9012-cdef-345678901234",
    // ... all UUIDs from previous /recommend and /reload-recommend calls
  ],
  "limit": 15
}
```

**Field Details**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `video_id` | string | ✅ | - | Reference video UUID (same as /recommend) |
| `excluded_video_ids` | array | ❌ | `[]` | UUIDs already shown |
| `limit` | integer | ❌ | `15` | Videos to return (1-50) |

**How It Works**:
1. **Use Cached Embedding**: Fetch reference video's pre-computed embedding
2. **FAISS Search**: Find K*3 + buffer (500) semantically similar videos
3. **Filter Exclusions**: Remove reference video and all shown videos
4. **Take Top K**: Get first limit results from filtered pool
5. **Re-rank**: Apply same hybrid ranking (70% semantic + 15% keywords + 15% category)
6. **Return**: Sorted unique results

**Request**:
```bash
curl -X POST "http://localhost:8000/api/reload-recommend" \
     -H "Content-Type: application/json" \
     -d '{
       "video_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
       "excluded_video_ids": ["uuid-1", "uuid-2", ..., "uuid-15"],
       "limit": 15
     }'
```

**Response**: `200 OK`
```json
{
  "videos": [
    // Next 15 unique recommendations for same reference video
  ],
  "current_video_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "total": 15
}
```

**Frontend Implementation Pattern**:
```javascript
// Infinite scroll recommendations sidebar

let referenceVideoId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
let allRecommendations = new Set();

// Step 1: Show initial recommendations
async function initialRecommend() {
  const response = await fetch(`/api/recommend?video_id=${referenceVideoId}&limit=15`);
  const data = await response.json();

  data.videos.forEach(v => {
    allRecommendations.add(v.id);
    displayRecommendationInSidebar(v);
  });
}

// Step 2: Load more on scroll down in recommendations
async function loadMoreRecommendations() {
  const response = await fetch('/api/reload-recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      video_id: referenceVideoId,
      excluded_video_ids: Array.from(allRecommendations),
      limit: 15
    })
  });

  const data = await response.json();

  data.videos.forEach(v => {
    allRecommendations.add(v.id);
    displayRecommendationInSidebar(v);
  });
}
```

---

## Likes & Dislikes

### POST /api/like

**Description**: Toggle like status on a video for authenticated user.

**Authentication**: Required - JWT Bearer token

**Request Body** (`LikeVideoRequest`):
```json
{
  "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response**: `200 OK` - `LikeResponse`
```json
{
  "success": true,
  "message": "Video liked successfully",
  "is_liked": true
}
```

**Frontend Integration**:
```javascript
// Like/unlike toggle

async function toggleLike(videoId) {
  const response = await fetch('/api/like', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`
    },
    body: JSON.stringify({
      video_uuid: videoId
    })
  });

  const data = await response.json();

  if (data.is_liked) {
    showThumbsUpFilled();
  } else {
    showThumbsUpOutline();
  }
}
```

---

### POST /api/dislike

**Description**: Toggle dislike status on a video for authenticated user.

**Authentication**: Required - JWT Bearer token

**Request Body** (`DislikeVideoRequest`):
```json
{
  "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response**: `200 OK` - `DislikeResponse`
```json
{
  "success": true,
  "message": "Video disliked successfully",
  "is_disliked": true
}
```

---

## Subscriptions

### POST /api/subscribe

**Description**: Toggle subscription status to a channel for authenticated user.

**Authentication**: Required - JWT Bearer token

**Request Body** (`SubscribeRequest`):
```json
{
  "channel_name": "Netflix"
}
```

**Response**: `200 OK` - `SubscriptionResponse`
```json
{
  "success": true,
  "message": "Successfully subscribed to Netflix",
  "is_subscribed": true
}
```

**Frontend Integration**:
```javascript
// Subscribe/unsubscribe button

async function toggleSubscribe(channelName) {
  const response = await fetch('/api/subscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`
    },
    body: JSON.stringify({
      channel_name: channelName
    })
  });

  const data = await response.json();

  if (data.is_subscribed) {
    updateButton("Unsubscribe");
    incrementSubscriberCount();
  } else {
    updateButton("Subscribe");
    decrementSubscriberCount();
  }
}
```

---

## Video Metadata

### POST /api/video-metadata

**Description**: Get complete metadata for a single video by UUID.

**Authentication**: None required

**Request Body** (`VideoMetadataRequest`):
```json
{
  "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response**: `200 OK` - `VideoMetadataResponse`
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
  "description": "The official video for 'Never Gonna Give You Up'...",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
  "channel": {
    "name": "Rick Astley",
    "avatar": "https://ui-avatars.com/api/?name=Rick%20Astley&background=8B5CF6&color=fff&size=36",
    "verified": true,
    "id": "Rick Astley"
  },
  "views": "1.2B views",
  "views_raw": 1200000000,
  "likes": 15000000,
  "dislikes": 500000,
  "timestamp": "15 years ago",
  "publish_time_raw": "2009-10-25T06:57:33.000Z",
  "duration": "10:00",
  "category": "Music",
  "velocity_score": 85.5,
  "region": "US",
  "tags": ["never", "gonna", "give", "you", "up"],
  "has_embedding": true,
  "created_at": "2026-01-15T10:30:00.000Z",
  "updated_at": "2026-03-20T15:45:00.000Z"
}
```

---



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
Basic video object returned in feed responses, search results, and recommendations.

```json
{
  "id": "string (UUID)",                    // UUID from videos.id (DB primary key) - USE FOR localStorage
  "video_id": "string",                     // YouTube video ID - USE FOR iframe embedding
  "title": "string",
  "thumbnail": "string",                    // YouTube thumbnail URL (https://i.ytimg.com...)
  "channel": {
    "name": "string",                       // Channel title
    "avatar": "string",                     // Generated avatar URL (ui-avatars.com)
    "verified": "boolean",                  // Heuristic: views > 100k or likes > 5k
    "id": "string"                          // Channel identifier (same as name)
  },
  "views": "string",                        // Formatted: "1.2M views", "50K views"
  "timestamp": "string",                    // Relative time: "2 weeks ago", "1 year ago"
  "duration": "string",                     // Video duration: "10:00", "15:30"
  "category": "string",                     // Category: Gaming, Music, Entertainment, etc.
  "velocity_score": "number|null"           // Trending score (0-100), null if not available
}
```

### FeedResponse
General feed response structure.

```json
{
  "videos": "VideoResponse[]",              // Array of video objects
  "strategy": "string",                     // Strategy used: "phase_1_cold_start", "phase_2_warm_up", "phase_3_personalized", "trending_only"
  "interaction_count": "number",            // Total interactions (watch history count)
  "total": "number"                         // Total videos returned
}
```

### SearchResponse
Response from `/search` endpoint.

```json
{
  "videos": "VideoResponse[]",
  "query": "string",                        // Original search query
  "total": "number"                         // Number of results returned
}
```

### RecommendResponse
Response from `/recommend` endpoint.

```json
{
  "videos": "VideoResponse[]",
  "current_video_id": "string (UUID)",      // Reference video UUID
  "total": "number"                         // Number of recommendations
}
```

### ReloadSearchResponse
Response from `/reload-search` endpoint.

```json
{
  "videos": "VideoResponse[]",
  "query": "string",                        // Original search query
  "total": "number",                        // Total in this batch
  "offset": "number"                        // Offset used
}
```

### ReloadRecommendResponse
Response from `/reload-recommend` endpoint.

```json
{
  "videos": "VideoResponse[]",
  "current_video_id": "string (UUID)",      // Reference video UUID
  "total": "number"                         // Total in this batch
}
```

### VideoMetadataResponse
Complete metadata for a video (from `/video-metadata` endpoint).

```json
{
  "id": "string (UUID)",
  "video_id": "string",
  "title": "string",
  "description": "string",                  // Full video description
  "thumbnail": "string",
  "channel": "ChannelInfo",
  "views": "string",                        // Formatted
  "views_raw": "number",                    // Raw view count
  "likes": "number",
  "dislikes": "number",
  "timestamp": "string",                    // Relative time
  "publish_time_raw": "string",             // ISO timestamp
  "duration": "string",
  "category": "string",
  "velocity_score": "number|null",
  "region": "string",                       // Country code
  "tags": "string[]",                       // Video tags/keywords
  "has_embedding": "boolean",               // If video has embedding vector
  "created_at": "string",                   // ISO timestamp
  "updated_at": "string"                    // ISO timestamp
}
```

### GuestFeedRequest
Request to get feed for guest user.

```json
{
  "guest_uuid": "string",                   // Required: unique guest identifier
  "region": "string",                       // Optional, default "US"
  "limit": "number",                        // Optional, default 30, max 50
  "watched_video_ids": "string[]"           // Optional: UUIDs from videos.id table
}
```

### WatchEventRequest
Request to track watch events (INSERT or UPDATE).

```json
{
  "video_uuid": "string",                   // Required: UUID from videos.id
  "watch_id": "string|null",                // Present only for UPDATE
  "watch_duration_seconds": "number|null",  // From YouTube API, UPDATE only
  "guest_uuid": "string|null"               // For guests
}
```

### WatchEventResponse
Response from watch event tracking.

```json
{
  "watch_id": "string|null",                // Returned ONLY on INSERT
  "success": "boolean"                      // true if successful
}
```

### LikeVideoRequest / DislikeVideoRequest
```json
{
  "video_uuid": "string"                    // UUID from videos.id
}
```

### LikeResponse / DislikeResponse
```json
{
  "success": "boolean",
  "message": "string",                      // Human readable message
  "is_liked": "boolean"                     // Current state after action
}
```

### SubscribeRequest
```json
{
  "channel_name": "string"                  // Channel title (from videos.channel_title)
}
```

### SubscriptionResponse
```json
{
  "success": "boolean",
  "message": "string",
  "is_subscribed": "boolean"                // Current subscription state
}
```

### CategoriesResponse
```json
{
  "categories": "string[]"                  // Starts with "All", then alphabetical
}
```

---

## Frontend Implementation Guide

### LocalStorage Management

**What to Store**:
```javascript
// App startup
const guest_uuid = localStorage.getItem('guest_uuid') || generateUUID();
localStorage.setItem('guest_uuid', guest_uuid);

// Watch events
const shownVideoIds = new Set(JSON.parse(localStorage.getItem('shown_videos') || '[]'));

// Search state
const searchHistory = JSON.parse(localStorage.getItem('search_history') || '[]');

// Liked videos (optional, can also fetch from backend)
const likedVideos = new Set(JSON.parse(localStorage.getItem('liked_videos') || '[]'));
```

**Guest Feed Tracking**:
```javascript
// After fetching feed
const feed = await fetchGuestFeed(guest_uuid, region, watched_ids);

// Store all shown videos
feed.videos.forEach(v => shownVideoIds.add(v.id));
localStorage.setItem('shown_videos', JSON.stringify(Array.from(shownVideoIds)));
```

**Watch History for Feed Personalization**:
```javascript
// Track which videos user has interacted with
const watchedVideos = new Set(   // Only store UUIDs!
  JSON.parse(localStorage.getItem('watched_videos') || '[]')
);

// When user clicks a video:
async function onVideoClick(video) {
  const watch = await trackWatchEvent(video.id, guest_uuid);  // INSERT
  watchedVideos.add(video.id);
  localStorage.setItem('watched_videos', JSON.stringify(Array.from(watchedVideos)));
}

// When user leaves video after 30 seconds:
async function onVideoEnd(video, watchDurationSeconds) {
  await updateWatchEvent(video.id, watch.watch_id, watchDurationSeconds, guest_uuid);  // UPDATE
}

// When fetching new feed:
const feed = await fetchGuestFeed(
  guest_uuid,
  region,
  Array.from(watchedVideos)  // Send to backend
);
```

### Search & Recommendations Flow

**Search with Lazy Loading**:
```javascript
class SearchManager {
  constructor() {
    this.currentQuery = '';
    this.allResults = [];
    this.shownIds = new Set();
  }

  async initialSearch(query, limit = 25) {
    this.currentQuery = query;
    this.shownIds.clear();

    const response = await fetch(
      `/api/search?q=${encodeURIComponent(query)}&limit=${limit}`
    );
    const data = await response.json();

    this.allResults = data.videos;
    data.videos.forEach(v => this.shownIds.add(v.id));

    return data.videos;
  }

  async loadMore(limit = 25) {
    const response = await fetch('/api/reload-search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        q: this.currentQuery,
        excluded_video_ids: Array.from(this.shownIds),
        offset: 0,
        limit: limit
      })
    });

    const data = await response.json();
    data.videos.forEach(v => this.shownIds.add(v.id));

    return data.videos;
  }
}
```

**Recommendations with Lazy Loading**:
```javascript
class RecommendManager {
  constructor(referenceVideoId) {
    this.videoId = referenceVideoId;
    this.shownIds = new Set();
  }

  async getInitial(limit = 15) {
    const response = await fetch(
      `/api/recommend?video_id=${this.videoId}&limit=${limit}`
    );
    const data = await response.json();

    data.videos.forEach(v => this.shownIds.add(v.id));
    return data.videos;
  }

  async loadMore(limit = 15) {
    const response = await fetch('/api/reload-recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        video_id: this.videoId,
        excluded_video_ids: Array.from(this.shownIds),
        limit: limit
      })
    });

    const data = await response.json();
    data.videos.forEach(v => this.shownIds.add(v.id));

    return data.videos;
  }
}
```

### Authenticated User Flow

```javascript
// After login, get JWT from Supabase
const jwtToken = await getSupabaseToken();
localStorage.setItem('auth_token', jwtToken);

// Get personalized feed
async function getPersonalizedFeed(region = 'US', limit = 30) {
  const response = await fetch(
    `/api/feed?region=${region}&limit=${limit}`,
    {
      headers: {
        'Authorization': `Bearer ${jwtToken}`
      }
    }
  );
  return await response.json();
}

// Like/unlike video
async function toggleLike(videoId) {
  const response = await fetch('/api/like', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`
    },
    body: JSON.stringify({ video_uuid: videoId })
  });
  return await response.json();
}

// Subscribe to channel
async function toggleSubscribe(channelName) {
  const response = await fetch('/api/subscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`
    },
    body: JSON.stringify({ channel_name: channelName })
  });
  return await response.json();
}
```

---

## Backend Files to Read

### Architecture Understanding
- **`app/main.py`**: Entry point, route registration, lifespan hooks
- **`app/core/embedding_service.py`**: BGE-M3 embedding model loading (int8 quantization)
- **`app/core/faiss_manager.py`**: FAISS vector search initialization and caching
- **`app/core/recommendation.py`**: 3-phase recommendation strategy implementation

### Database & APIs
- **`app/db.py`**: Supabase REST API calls, video metadata fetching
- **`app/schemas/feed.py`**: All request/response Pydantic models
- **`app/utils/formatters.py`**: View formatting, timestamp parsing, channel verification

### Endpoint Implementations
- **`app/api/routes/feed.py`**: `/feed`, `/trending`, `/guest/feed`, `/guest/watch` endpoints
- **`app/api/routes/search.py`**: `/search`, `/recommend`, `/reload-search`, `/reload-recommend` endpoints

### Configuration
- **`.env`**: Environment variables (Supabase credentials, JWT secret)
- **`requirements.txt`**: All dependencies including sentence-transformers, torch

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

## Architecture Overview

### System Components

1. **Embedding Layer** (`app/core/embedding_service.py`)
   - Model: sentence-transformers/bge-m3
   - Dimension: 1024
   - Optimization: PyTorch int8 dynamic quantization (73% memory reduction)
   - Load time: 3-5 seconds (one-time at startup)
   - Memory: ~600MB (vs 2.27GB unquantized)
   - Fallback: Auto-switches to float16 if int8 fails

2. **Vector Search** (`app/core/faiss_manager.py`)
   - Index type: FAISS IndexFlatIP (Inner Product for normalized vectors)
   - Precomputed on startup from database embeddings
   - Supports fast similarity search: O(log n)
   - Caches uuid→embedding mapping for instant lookup
   - Zero-latency access to pre-computed vectors

3. **Recommendation Engine** (`app/core/recommendation.py`)
   - 3-phase strategy: Cold Start → Warm-up → Personalized
   - Taste vector: Weighted mean of watched video embeddings
   - Time decay: 14-day half-life for older interactions
   - Category boosting: 1.0x-1.5x for underrepresented interests

4. **Database Access** (`app/db.py`)
   - Async HTTP client to Supabase REST API
   - Parallel batch queries with asyncio.gather()
   - Connection pooling via httpx.AsyncClient
   - JWT authentication for service-level access

### Request Flow Diagrams

**Search Flow**:
```
Client → /search?q=query&limit=25
        ↓
Embed Query (bgem3 model)
        ↓
FAISS Search (K*2=50 candidates)
        ↓
Fetch Metadata (50 videos from DB)
        ↓
Hybrid Score (semantic + keyword + category)
        ↓
Re-rank and Return Top 25
```

**Recommendation Flow**:
```
Client → /recommend?video_id=xyz&limit=15
        ↓
Lookup Reference Embedding (cached)
        ↓
Get Reference Metadata (title, category)
        ↓
FAISS Search (K*2+buffer=30+ candidates)
        ↓
Filter (remove reference video itself)
        ↓
Fetch Metadata (candidates from DB)
        ↓
Hybrid Score (semantic + keywords + category affinity)
        ↓
Re-rank and Return Top 15
```

**Lazy Loading Flow**:
```
/reload-search OR /reload-recommend
        ↓
Same logic as initial request
        ↓
Exclude all previous results (set difference)
        ↓
Get next batch from filtered space
        ↓
Return unique new results
```

### Performance Characteristics

| Endpoint | Latency | Bottleneck | Scalability |
|----------|---------|------------|-------------|
| `/search` | 300-400ms | FAISS search + metadata fetch | Excellent (linear with K) |
| `/reload-search` | 250-350ms | FAISS search + filtering | Excellent (set ops are fast) |
| `/recommend` | 200-300ms | Metadata fetch | Very Good (no embedding needed) |
| `/reload-recommend` | 150-250ms | Filtering | Excellent (cached embedding) |
| `/feed` Phase 1 | ~200ms | RPC calls | Very Good |
| `/feed` Phase 2 | ~400ms | Embedding + RPC | Good |
| `/feed` Phase 3 | ~800ms | Country affinity | Fair (optimization opportunity) |

### Database Schema for Search Feature

Extended from base schema:

```sql
-- Embeddings table (from videos)
ALTER TABLE videos ADD COLUMN embedding vector(1024);
CREATE INDEX ON videos USING ivfflat (embedding vector_ip_ops);

-- Watch history (for taste vector)
CREATE TABLE watch_history (
    id UUID PRIMARY KEY,
    user_id UUID,
    guest_uuid TEXT,
    video_id UUID REFERENCES videos(id),
    watch_duration_seconds INT,
    watch_percentage DECIMAL,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ
);

-- Liked videos (for taste vector in future)
CREATE TABLE liked_videos (
    id UUID PRIMARY KEY,
    user_id UUID,
    video_id UUID REFERENCES videos(id),
    created_at TIMESTAMPTZ
);
```

### Supported Regions & Categories

**Regions** (10 countries):
US, GB (United Kingdom), JP (Japan), DE (Germany), FR (France), IN (India), KR (South Korea), MX (Mexico), RU (Russia), CA (Canada)

**Categories** (16 total):
1. Sports
2. Music
3. People & Blogs
4. Entertainment
5. News & Politics
6. Howto & Style
7. Travel & Events
8. Shows
9. Nonprofits & Activism
10. Autos & Vehicles
11. Gaming
12. Comedy
13. Film & Animation
14. Education
15. Pets & Animals
16. Science & Technology

---

## Error Handling Expanded

### Network Errors
```
502 Bad Gateway: FAISS index not initialized
→ Solution: Ensure backend startup completes, check app/core/faiss_manager.py

504 Gateway Timeout: Supabase taking >30s to respond
→ Solution: Check Supabase status, verify RPC functions exist
```

### Model Errors
```
RuntimeError: "Embedding model not loaded"
→ Solution: Check embedding_service.load_model() is called in main.py lifespan

ValueError: "Query embedding has zero norm"
→ Solution: Empty or whitespace-only query, validates input length
```

### FAISS Errors
```
Exception: "FAISS index dimension mismatch"
→ Solution: Ensure embeddings are 1024-dim after bge-m3

Exception: "Zero results from FAISS"
→ Solution: Database embeddings may be corrupt, regenerate from notebook
```

### Database Errors
```
422 Validation Error: Invalid UUID format
→ Solution: Validate UUID format before sending to API

404 Not Found: Video UUID doesn't exist
→ Solution: Verify video_id matches videos.id (not videos.video_id)

FK Constraint: Inserting invalid video_id to watch_history
→ Solution: Use videos.id (UUID), not YouTube video ID
```

---

## Caching Strategy

### What's Cached
```python
# In FAISS manager (persistent for lifetime of server)
UUID_TO_EMBEDDING = {}  # {uuid: np.array(1024,)}
FAISS_INDEX = None      # Pre-built from all videos

# In memory during request
query_embedding = None  # Computed once per /search
reference_metadata = None  # Fetched once per /recommend
```

### What's NOT Cached (Computed Fresh)
- Query embeddings (re-embed for each /search)
- Re-ranking calculations (semantic scores change slightly with query)
- Metadata fetches (always hit DB for freshest data)

### Frontend Caching
```javascript
// What to cache in localStorage
{
  "guest_uuid": "string",              // Persist across sessions
  "watched_video_ids": ["uuid", ...],  // For taste vector
  "search_history": ["query", ...],    // For UX (optional)
  "auth_token": "jwt_token"            // From Supabase
}

// What NOT to cache
// - Feed results (stale after 1 hour)
// - Search results > 10 items (large serialization)
// - Recommendation results (change based on interaction)
```

---

## Testing Strategy

### Unit Tests (for backend)
Would test:
- Embedding normalization (norm = 1.0)
- FAISS search exactness (top-1 is highest similarity)
- Keyword matching logic (counting works correctly)
- Category detection (query → category intent)
- Hybrid scoring (weights sum to 1.0)

### Integration Tests (full flow)
```bash
# Search flow
POST /search?q=gaming&limit=10 → Verify 10 results, all Gaming-related or gaming-keyword

# Recommendation flow
POST /recommend?video_id=X&limit=10 → Verify 10 results, none are video X

# Lazy loading flow
POST /search → 25 results
POST /reload-search with 25 excluded → 25 NEW results (no duplication)
POST /reload-search with 50 excluded → 25 MORE NEW results
```

### Load Tests (performance validation)
- Single query: measure latency bands (100ms, 200ms, 500ms)
- Concurrent requests: 10 parallel /search calls
- Large exclusion sets: 1000+ excluded IDs in /reload-search
- Memory usage: peak during FAISS initialization

---

## Production Checklist

- [ ] All embeddings generated and uploaded (24,499 videos with 1024-dim vectors)
- [ ] FAISS index pre-computed and loaded at startup
- [ ] Embedding model loaded at startup (or returns clear error)
- [ ] All RPC functions exist in Supabase (search_videos, get_trending, etc.)
- [ ] JWT verification configured correctly
- [ ] CORS configured for frontend domain
- [ ] Rate limiting configured if deployed publicly
- [ ] Error logging and monitoring (Sentry, CloudWatch, etc.)
- [ ] Database backups configured
- [ ] Embedding updates scheduled (if new videos added weekly)
- [ ] Performance monitoring (API latency, error rates)
- [ ] Documentation deployed and accessible

---

**Last Updated**: March 27, 2026
**Search & Recommendations**: ✅ Complete (v1.0)
**Lazy Loading**: ✅ Implemented
**Frontend Guide**: ✅ Comprehensive
**Testing Status**: 🧪 Ready for Postman