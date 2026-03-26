# Likes API - Complete Guide

## Overview
Three new endpoints for managing user's liked videos collection:
- **GET /api/feed/likes** - Fetch all liked videos
- **POST /api/feed/like** - Like a video
- **DELETE /api/feed/like/{video_id}** - Unlike a video

All endpoints require authentication (JWT token in Authorization header).

---

## 1. GET /api/feed/likes - Get All Liked Videos

### Description
Retrieve all videos that the authenticated user has liked.

### Request
```
GET /api/feed/likes?limit=50
Authorization: Bearer <JWT_TOKEN>
```

### Query Parameters
- `limit` (optional): Number of videos to return
  - Default: 50
  - Range: 1-500
  - Example: `?limit=100`

### Response (200 OK)
```json
{
  "videos": [
    {
      "id": "bceacc63-b338-48b3-8f24-626c0baa7dec",
      "video_id": "dQw4w9WgXcQ",
      "title": "Never Gonna Give You Up",
      "thumbnail": "https://...",
      "channel": {
        "name": "Rick Astley",
        "avatar": "https://...",
        "verified": true,
        "id": "Rick Astley"
      },
      "views": "1.2B",
      "timestamp": "2020-10-25",
      "duration": "3:33",
      "category": "Music",
      "velocity_score": 0.95
    },
    ...more videos...
  ],
  "total": 42
}
```

### Error Responses
```json
{
  "detail": "Failed to fetch liked videos"
}
```
Status: 500 (if database error occurs)

### Usage Example (cURL)
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/feed/likes?limit=50"
```

### Usage Example (JavaScript/Fetch)
```javascript
const response = await fetch('http://localhost:8000/api/feed/likes?limit=50', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const data = await response.json();
console.log(data.videos, data.total);
```

---

## 2. POST /api/feed/like - Like a Video

### Description
Add a video to the user's liked collection. Idempotent - safe to call multiple times.

### Request
```
POST /api/feed/like
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "video_uuid": "bceacc63-b338-48b3-8f24-626c0baa7dec"
}
```

### Request Body
- `video_uuid` (required, string): UUID of the video to like (from videos.id, not YouTube ID)

### Response (200 OK)
```json
{
  "success": true,
  "message": "Video liked successfully",
  "is_liked": true
}
```

### Error Responses
```json
{
  "detail": "Failed to like video"
}
```
Status: 500 (if database error occurs)

### Usage Example (cURL)
```bash
curl -X POST http://localhost:8000/api/feed/like \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"video_uuid": "bceacc63-b338-48b3-8f24-626c0baa7dec"}'
```

### Usage Example (JavaScript/Fetch)
```javascript
const response = await fetch('http://localhost:8000/api/feed/like', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    video_uuid: 'bceacc63-b338-48b3-8f24-626c0baa7dec'
  })
});
const data = await response.json();
console.log(data.message); // "Video liked successfully"
console.log(data.is_liked); // true
```

### Idempotency
Calling this endpoint multiple times with the same video_uuid is safe:
- First call: Creates the like (201)
- Second call: Ignores duplicate (409 internally handled)
- Result: Same success response both times

---

## 3. DELETE /api/feed/like/{video_id} - Unlike a Video

### Description
Remove a video from the user's liked collection. Idempotent - safe to call multiple times.

### Request
```
DELETE /api/feed/like/bceacc63-b338-48b3-8f24-626c0baa7dec
Authorization: Bearer <JWT_TOKEN>
```

### Path Parameters
- `video_id` (required, string): UUID of the video to unlike (from path)

### Response (200 OK)
```json
{
  "success": true,
  "message": "Video unliked successfully",
  "is_liked": false
}
```

### Error Responses
```json
{
  "detail": "Failed to unlike video"
}
```
Status: 500 (if database error occurs)

### Usage Example (cURL)
```bash
curl -X DELETE http://localhost:8000/api/feed/like/bceacc63-b338-48b3-8f24-626c0baa7dec \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Usage Example (JavaScript/Fetch)
```javascript
const videoId = 'bceacc63-b338-48b3-8f24-626c0baa7dec';
const response = await fetch(`http://localhost:8000/api/feed/like/${videoId}`, {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const data = await response.json();
console.log(data.message); // "Video unliked successfully"
console.log(data.is_liked); // false
```

### Idempotency
Calling this endpoint multiple times with the same video_uuid is safe:
- First call: Deletes the like (200/204)
- Second call: Nothing to delete (200 internally handled)
- Result: Same success response both times

---

## Database Schema

### user_likes Table
```sql
CREATE TABLE user_likes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, video_id)  -- Prevent duplicate likes
);

CREATE INDEX idx_user_likes_user_id ON user_likes(user_id);
CREATE INDEX idx_user_likes_created_at ON user_likes(user_id, created_at DESC);
```

---

## Database Functions (app/db.py)

### get_user_liked_videos()
```python
async def get_user_liked_videos(user_id: str, limit: int = 100) -> list[dict]
```
- Fetches all liked videos for a user
- Returns full video objects (includes embeddings, metadata)
- Ordered by like creation date (newest first)
- Used by: GET /api/feed/likes

### add_like()
```python
async def add_like(user_id: str, video_id: str) -> bool
```
- Adds a like (idempotent)
- Returns True if successful
- Handles duplicate constraint gracefully
- Used by: POST /api/feed/like

### remove_like()
```python
async def remove_like(user_id: str, video_id: str) -> bool
```
- Removes a like (idempotent)
- Returns True if successful
- Safe if like doesn't exist
- Used by: DELETE /api/feed/like/{video_id}

### is_video_liked()
```python
async def is_video_liked(user_id: str, video_id: str) -> bool
```
- Checks if user has liked a video
- Returns True if liked, False otherwise
- Used internally to confirm state after actions

---

## Testing in Postman

### 1. Get Liked Videos
```
GET http://localhost:8000/api/feed/likes?limit=50
Headers:
  Authorization: Bearer <YOUR_TOKEN>
```

### 2. Like a Video
```
POST http://localhost:8000/api/feed/like
Headers:
  Authorization: Bearer <YOUR_TOKEN>
  Content-Type: application/json
Body (raw JSON):
{
  "video_uuid": "bceacc63-b338-48b3-8f24-626c0baa7dec"
}
```

### 3. Unlike a Video
```
DELETE http://localhost:8000/api/feed/like/bceacc63-b338-48b3-8f24-626c0baa7dec
Headers:
  Authorization: Bearer <YOUR_TOKEN>
```

---

## Error Handling

All endpoints implement comprehensive error handling:

### Authentication Errors
- **401 Unauthorized**: Invalid or missing JWT token
  - Solution: Provide valid JWT in Authorization header

### Validation Errors
- **422 Unprocessable Entity**: Invalid request body
  - Solution: Check request format matches schema

### Server Errors
- **500 Internal Server Error**: Database operation failed
  - Logged with context: User ID, Video ID, Error message
  - Solution: Check backend logs, verify database connectivity

---

## Features & Safety

✅ **Idempotent operations** - Safe to call multiple times
✅ **Deduplication** - Prevents duplicate likes in database
✅ **Comprehensive error handling** - Detailed error messages
✅ **Authentication required** - All endpoints protected
✅ **Fast lookups** - Indexed on user_id and created_at
✅ **Cascading deletes** - Cleans up when user/video deleted
✅ **Return current state** - Operations return is_liked boolean

---

## Integration with Frontend

### React Example
```javascript
import { useState } from 'react';

export function VideoCard({ video, accessToken }) {
  const [isLiked, setIsLiked] = useState(false);

  const handleLike = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/feed/like', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ video_uuid: video.id })
      });
      const data = await response.json();
      setIsLiked(data.is_liked);
    } catch (error) {
      console.error('Failed to like video:', error);
    }
  };

  const handleUnlike = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/feed/like/${video.id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      const data = await response.json();
      setIsLiked(data.is_liked);
    } catch (error) {
      console.error('Failed to unlike video:', error);
    }
  };

  return (
    <div>
      <h3>{video.title}</h3>
      <button onClick={isLiked ? handleUnlike : handleLike}>
        {isLiked ? '❤️ Unlike' : '🤍 Like'}
      </button>
    </div>
  );
}
```

---

## Performance Considerations

- Likes list endpoint supports limit up to 500
- Index on (user_id, created_at DESC) for fast pagination
- No N+1 queries - videos fetched in single batch
- Caches JWKS for JWT verification
- HTTP/1.1 keep-alive for connection reuse
