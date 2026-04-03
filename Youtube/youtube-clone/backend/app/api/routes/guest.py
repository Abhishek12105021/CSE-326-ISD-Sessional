import time
from datetime import datetime

import numpy as np
from fastapi import APIRouter

from app.core import faiss_manager
from app.core.recommendation import generate_phase1_feed, generate_phase2_feed, generate_phase3_feed
from app.db import get_videos_metadata_by_uuids, increment_video_views, insert_watch_history, update_watch_history
from app.schemas.auth import GuestSessionRequest, GuestSessionResponse
from app.schemas.feed import (
    ChannelInfo,
    FeedResponse,
    GuestFeedRequest,
    GuestReloadFeedRequest,
    VideoResponse,
    WatchEventRequest,
    WatchEventResponse,
)
from app.utils.formatters import format_timestamp, format_views, generate_channel_avatar, is_verified

# /api/guest/*
# NOTE: Guest sessions are now managed via localStorage on the frontend.
# These endpoints are kept for API compatibility but don't persist to database.

router = APIRouter()


@router.post("/session", response_model=GuestSessionResponse)
async def create_guest_session(request: GuestSessionRequest):
    """
    Acknowledge guest session creation - API compatibility endpoint.

    PURPOSE:
    This endpoint exists for API compatibility but does NOT persist guest data to database.
    All guest session management is handled via localStorage on the frontend (guest_uuid).

    FLOW:
    1. Frontend generates guest_uuid (UUID v4) and stores in localStorage
    2. Frontend calls this endpoint to acknowledge session start
    3. Backend returns confirmation with timestamp (no database write)
    4. Frontend continues to manage session locally via localStorage

    WHAT THIS DOES:
    - Validates request format
    - Returns guest_uuid back with timestamp
    - Does NOT create database records
    - Does NOT track guest activity (guests are ephemeral)

    WHAT THIS DOESN'T DO:
    - Does NOT persist to database (guest sessions are stateless)
    - Does NOT create virtual user accounts
    - Does NOT affect recommendation system

    USE CASE:
    Initial API handshake for guest users starting their session.
    By the time user accesses /guest/feed, they already have guest_uuid in localStorage.

    ARG:
        request: GuestSessionRequest with guest_uuid, optional region, language, device_type

    RETURN:
        GuestSessionResponse: Echoes back guest_uuid + timestamp + interaction_count=0

    PERFORMANCE: O(1) - Just echo response, no DB hit
    """
    return GuestSessionResponse(
        guest_uuid=request.guest_uuid,
        interaction_count=0,
        created_at=datetime.utcnow()
    )




@router.post("/feed", response_model=FeedResponse)
async def get_guest_feed(request: GuestFeedRequest):
    """
    Generate personalized feed for guest users (localStorage-based watch history).

    ═══════════════════════════════════════════════════════════════════════════════════
    PURPOSE:
    Generate 30 recommended videos for unauthenticated users based on:
    - Watch history from localStorage (UUIDs of watched videos)
    - Region preference (default: US)
    - 3-phase recommendation strategy (cold start → warm-up → personalized)
    ═══════════════════════════════════════════════════════════════════════════════════

    FLOW OVERVIEW (3 Steps):

    STEP 1: Build Taste Vector from Watch History
    ─────────────────────────────────────────────
    If user has watched videos (watchedUUIDs > 0):
      - Fetch embedding vectors for each watched video from FAISS manager cache
      - Compute mean of embeddings (weighted average)
      - Normalize to unit vector (L2 norm = 1.0)
      - This becomes the user's "taste vector" (1024-dim)

    Time: ~50-150ms for 10-20 videos
    Memory: Embeddings already cached at startup

    NOTE: Guests don't have timestamp history, so recency weighting is skipped
          (all videos weighted equally in mean)

    STEP 2: Determine Phase & Generate Feed UUIDs
    ───────────────────────────────────────────────
    Phase 1 (0 interactions) - Cold Start:
      - No taste vector (can't compute from empty watch history)
      - Return 50% global trending + 50% local trending
      - Strategy: pure exploration, no personalization

    Phase 2 (1-4 interactions) - Warm-Up:
      - Have sparse taste vector (risky to over-personalize)
      - Return 20-40% semantic similar + 40% trending + 30% local
      - Strategy: balanced exploration + exploitation
      - Prevents overfitting (e.g., watched 1 gaming video → all gaming)

    Phase 3 (5+ interactions) - Personalized:
      - Rich taste vector (high confidence in preferences)
      - Return 60-75% semantic similar same-region + buckets
      - Strategy: aggressive personalization with safety diversity
      - Break down as:
        * Bucket A (60%): Videos semantically similar in user's region
        * Bucket B (20%): Semantically similar videos from other countries
        * Bucket C (10%): Trending videos in user's region
        * Bucket D (10%): Global trending mix

    Time: ~200-400ms (depending on phase complexity)

    STEP 3: Fetch Metadata
    ──────────────────────
    Convert UUIDs to full video metadata:
      - Title, thumbnail, channel, views, timestamp
      - Category, velocity score
      Single Supabase REST call for all UUIDs

    Time: ~100-200ms

    ═══════════════════════════════════════════════════════════════════════════════════
    KEY DETAILS:

    Watch History Source:
      - Frontend localStorage stores: ["uuid-1", "uuid-2", ...]
      - Uses videos.id (UUID), NOT YouTube video_id
      - Frontend maintains this list across page reloads

    Taste Vector Building:
      - Uses embeddings from FAISS manager (pre-loaded at startup)
      - Only embeddings of videos that exist in FAISS are used
      - Missing embeddings silently skipped (shouldn't happen in normal case)
      - Normalized to unit length for cosine similarity

    Phase Transitions:
      - Phase triggers on INTERACTION COUNT, not unique videos
      - 5 watches of same video → Phase 3 (even though taste is repetitive)
      - This is by design: interaction count = engagement confidence

    Deduplication:
      - Watched videos are EXCLUDED from results
      - No video appears twice in same feed
      - /reload endpoint explicitly lists excluded_video_ids for pagination
    ═══════════════════════════════════════════════════════════════════════════════════

    ARGS:
        request: GuestFeedRequest
            - guest_uuid (required): Unique guest identifier (from localStorage)
            - region (optional, default "US"): Country code (US, GB, JP, DE, FR, IN, KR, MX, RU, CA)
            - limit (optional, default 30, max 50): Number of videos to return
            - watched_video_ids (optional, default []): UUIDs of videos user has watched

    RETURNS:
        FeedResponse:
            - videos: Array of 30 VideoResponse objects
            - strategy: "phase_1_cold_start" | "phase_2_warm_up" | "phase_3_personalized"
            - interaction_count: len(watched_video_ids)
            - total: len(videos)

    ═══════════════════════════════════════════════════════════════════════════════════
    EXAMPLE REQUEST:

    {
        "guest_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "region": "US",
        "limit": 25,
        "watched_video_ids": [
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "b2c3d4e5-f6a7-8901-bcde-f23456789012",
            "c3d4e5f6-a7b8-9012-cdef-345678901234"
        ]
    }

    EXAMPLE RESPONSE (Phase 2):

    {
        "videos": [
            // First 3-4 videos: semantically similar to watched videos
            // Next 12 videos: trending (global + local mix)
            // Last 9-10 videos: regional trending
        ],
        "strategy": "phase_2_warm_up",
        "interaction_count": 3,
        "total": 25
    }
    ═══════════════════════════════════════════════════════════════════════════════════

    PERFORMANCE:
        - Total latency: 300-600ms (3 steps: taste vector + generation + metadata)
        - Taste vector: O(n) where n = watched_video_count (usually 5-50)
        - Generation: O(1) to O(1000) depending on database query complexity
        - Metadata fetch: O(k) where k = limit (usually 25-50)

    ERROR CASES:
        - Empty watched_video_ids: Returns Phase 1 feed (cold start)
        - Invalid UUID format: Silently ignored, other videos processed
        - Region not found: Defaults to "US"
        - Supabase timeout: Returns 500 error
    """
    total_start = time.time()
    watched_uuids = request.watched_video_ids
    interaction_count = len(watched_uuids)

    print(f"\n{'#'*70}")
    print(f"[GUEST FEED] Starting for guest, region={request.region}, interactions={interaction_count}")
    print(f"{'#'*70}")

    # Build taste vector from FAISS embeddings (guests always rebuild, no caching)
    taste = None
    if interaction_count > 0:
        step_start = time.time()
        print(f"[GUEST FEED Step 1/3] Building taste vector from {interaction_count} watched videos...")

        # Get embeddings from FAISS manager's in-memory dict
        vectors = []
        for video_id in watched_uuids:
            embedding = faiss_manager.UUID_TO_EMBEDDING.get(video_id)
            if embedding is not None:
                vectors.append(embedding)

        if vectors:
            # Simple weighted average (guests don't have timestamps for recency)
            vectors_arr = np.array(vectors, dtype=np.float32)
            taste = np.mean(vectors_arr, axis=0).astype(np.float32)
            taste = taste / (np.linalg.norm(taste) + 1e-10)  # Normalize

        step_elapsed = (time.time() - step_start) * 1000
        print(f"[GUEST FEED Step 1/3] Built taste vector: shape={taste.shape if taste is not None else None} ({step_elapsed:.1f}ms)")

    # Determine phase and generate feed
    step_start = time.time()
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        print("[GUEST FEED Step 2/3] Phase 1 (Cold Start): Generating trending feed...")
        video_uuids = await generate_phase1_feed(request.region, watched_uuids, request.limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        print("[GUEST FEED Step 2/3] Phase 2 (Warm-Up): Generating mixed feed...")
        video_uuids = await generate_phase2_feed(
            taste, request.region, watched_uuids, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, watched_uuids, request.limit)

    else:
        strategy = "phase_3_personalized"
        print("[GUEST FEED Step 2/3] Phase 3 (Personalized): Generating semantic feed...")
        video_uuids = await generate_phase3_feed(
            taste, request.region, watched_uuids, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, watched_uuids, request.limit)

    step_elapsed = (time.time() - step_start) * 1000
    print(f"[GUEST FEED Step 2/3] Generated {len(video_uuids)} video UUIDs using {strategy} ({step_elapsed:.1f}ms)")

    # Fetch metadata
    step_start = time.time()
    videos = await get_videos_metadata_by_uuids(video_uuids)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[GUEST FEED Step 3/3] Fetched metadata for {len(videos)} videos ({step_elapsed:.1f}ms)")

    # Transform
    def transform_video(v: dict) -> VideoResponse:
        return VideoResponse(
            id=v["id"],
            video_id=v["video_id"],
            title=v["title"],
            thumbnail=v["thumbnail_link"],
            channel=ChannelInfo(
                name=v["channel_title"],
                avatar=generate_channel_avatar(v["channel_title"]),
                verified=is_verified(v.get("views", 0), v.get("likes", 0)),
                id=v["channel_title"]
            ),
            views=format_views(v.get("views", 0)),
            timestamp=format_timestamp(v.get("publish_time", "")),
            publish_time_raw=v.get("publish_time", ""),
            duration="10:00",
            category=v.get("category_name", "Unknown"),
            velocity_score=v.get("velocity_score")
        )

    video_responses = [transform_video(v) for v in videos]

    total_elapsed = (time.time() - total_start) * 1000
    print(f"{'#'*70}")
    print(f"[GUEST FEED] Complete! Strategy: {strategy}, Videos: {len(video_responses)}, Total: {total_elapsed:.1f}ms")
    print(f"{'#'*70}\n")

    return FeedResponse(
        videos=video_responses,
        strategy=strategy,
        interaction_count=interaction_count,
        total=len(video_responses)
    )




@router.post("/reload", response_model=FeedResponse)
async def reload_guest_feed(request: GuestReloadFeedRequest):
    """
    Lazy loading endpoint - reload feed with more videos excluding already-shown ones.

    ═══════════════════════════════════════════════════════════════════════════════════
    PURPOSE:
    Return next batch of 20-30 videos for infinite scroll, excluding all previously shown
    videos. Maintains same personalization logic as /feed endpoint.
    ═══════════════════════════════════════════════════════════════════════════════════

    FRONTEND INTEGRATION PATTERN:

    Step 1: Get initial search/feed
        POST /guest/feed → 25 videos (store UUIDs in Set)

    Step 2: User scrolls to bottom
        POST /guest/reload with:
            - watched_video_ids: All videos user watched (same as /feed)
            - excluded_video_ids: All 25 videos from step 1
            → Returns 25 NEW videos (no duplicates)

    Step 3: User scrolls more
        POST /guest/reload with:
            - watched_video_ids: Same as step 1
            - excluded_video_ids: 50 video UUIDs (25 from step 1 + 25 from step 2)
            → Returns 25 MORE NEW videos

    Step 4: Continue until no more results
        Repeat, accumulating excluded_video_ids

    KEY INSIGHT:
    - excluded_video_ids = all videos shown to user (both watched + pagination results)
    - As user scrolls, excluded list grows, ensuring unique results
    - Underlying recommendation logic stays identical to /feed

    ═══════════════════════════════════════════════════════════════════════════════════

    HOW IT AVOIDS DUPLICATES:

    Traditional approach (bad):
        POST /feed → [v1, v2, v3, ...]
        POST /feed → [v1, v2, v3, ...] (SAME VIDEOS! not ideal)

    Our approach (good):
        POST /feed → [v1, v2, v3, ...]
        POST /reload with excluded=[v1, v2, v3] → [v4, v5, v6, ...]
        POST /reload with excluded=[v1...v6] → [v7, v8, v9, ...]

    This works because:
        1. Each recommendation function filters out excluded_video_ids BEFORE selecting results
        2. Database queries (RPC functions) are told "don't return these IDs"
        3. Results guarantee uniqueness

    ═══════════════════════════════════════════════════════════════════════════════════

    INTERACTION DETAILS:

    Taste Vector Building (unchanged):
        - Rebuilds from watched_video_ids (same as /feed)
        - No caching (guests don't have persistent taste vectors)
        - If watched_video_ids is empty → Phase 1, else → Phase 2/3

    Feed Generation (with exclusion):
        - All generation functions are called with all_excluded filter
        - DB queries return results that DON'T overlap with excluded IDs
        - Top K results are selected from this filtered pool

    Merged Exclusion List:
        - Combines watched_video_ids + excluded_video_ids into single filter
        - Prevents showing:
          * Videos user actually watched (watched_video_ids)
          * Videos already shown in pagination (excluded_video_ids)

    ═══════════════════════════════════════════════════════════════════════════════════

    ARGS:
        request: GuestReloadFeedRequest
            - guest_uuid (required): Same guest from /feed call
            - region (required): User's region
            - watched_video_ids (required): All videos watched so far (for taste vector)
            - excluded_video_ids (required): All videos shown in pagination
            - limit (optional, default 25): How many new videos to return

    RETURNS:
        FeedResponse:
            - videos: 20-30 new VideoResponse objects
            - strategy: Same as /feed (phase_1, phase_2, or phase_3)
            - interaction_count: len(watched_video_ids)
            - total: Number of videos returned in this batch

    ═══════════════════════════════════════════════════════════════════════════════════

    EXAMPLE REQUEST (2nd reload):

    {
        "guest_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "region": "US",
        "watched_video_ids": [
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "b2c3d4e5-f6a7-8901-bcde-f23456789012",
            "c3d4e5f6-a7b8-9012-cdef-345678901234"
        ],
        "excluded_video_ids": [
            // 25 videos from initial /feed call
            "d3d4e5f6-a7b8-9012-cdef-345678901235",
            "e3d4e5f6-a7b8-9012-cdef-345678901236",
            ...,
            "z3d4e5f6-a7b8-9012-cdef-345678901260"
        ],
        "limit": 25
    }

    EXAMPLE RESPONSE:

    {
        "videos": [
            // 25 NEW videos (not in excluded_video_ids)
            // Same personalization strategy (phase_2_warm_up in this example)
        ],
        "strategy": "phase_2_warm_up",
        "interaction_count": 3,
        "total": 25
    }

    ═══════════════════════════════════════════════════════════════════════════════════

    PERFORMANCE:
        - Total latency: 250-500ms (similar to /feed but filtering adds ~50ms)
        - Taste vector: O(n) where n = watched count
        - Generation: O(1) but needs to filter larger pool → slightly slower
        - Metadata fetch: O(k) where k = limit

    EDGE CASES:
        1. excluded_video_ids > available results:
           - Returns empty array (all videos already shown)
           - Frontend should stop pagination

        2. Mixed watched + excluded lists:
           - Both are merged into single exclusion filter
           - Only unshow videos returned

        3. Very large excluded lists (1000+ items):
           - Set operations in DB still O(1) for modern databases
           - No performance degradation expected
    """
    total_start = time.time()
    watched_uuids = request.watched_video_ids
    excluded_ids = request.excluded_video_ids or []
    interaction_count = len(watched_uuids)

    print(f"\n{'#'*70}")
    print(f"[GUEST RELOAD] Starting for guest, region={request.region}, "
          f"watching={interaction_count}, excluding={len(excluded_ids)}")
    print(f"{'#'*70}")

    # Merge watched + excluded for comprehensive filtering
    all_excluded = list(set(watched_uuids + excluded_ids))

    # Build taste vector from FAISS embeddings (same as /feed)
    taste = None
    if interaction_count > 0:
        step_start = time.time()
        print(f"[GUEST RELOAD Step 1/3] Building taste vector from {interaction_count} watched videos...")

        vectors = []
        for video_id in watched_uuids:
            embedding = faiss_manager.UUID_TO_EMBEDDING.get(video_id)
            if embedding is not None:
                vectors.append(embedding)

        if vectors:
            vectors_arr = np.array(vectors, dtype=np.float32)
            taste = np.mean(vectors_arr, axis=0).astype(np.float32)
            taste = taste / (np.linalg.norm(taste) + 1e-10)

        step_elapsed = (time.time() - step_start) * 1000
        print(f"[GUEST RELOAD Step 1/3] Built taste vector ({step_elapsed:.1f}ms)")

    # Determine phase and generate feed (with all_excluded filter)
    step_start = time.time()
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        print("[GUEST RELOAD Step 2/3] Phase 1 (Cold Start): Generating trending feed...")
        video_uuids = await generate_phase1_feed(request.region, all_excluded, request.limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        print("[GUEST RELOAD Step 2/3] Phase 2 (Warm-Up): Generating mixed feed...")
        video_uuids = await generate_phase2_feed(
            taste, request.region, all_excluded, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, all_excluded, request.limit)

    else:
        strategy = "phase_3_personalized"
        print("[GUEST RELOAD Step 2/3] Phase 3 (Personalized): Generating semantic feed...")
        video_uuids = await generate_phase3_feed(
            taste, request.region, all_excluded, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, all_excluded, request.limit)

    step_elapsed = (time.time() - step_start) * 1000
    print(f"[GUEST RELOAD Step 2/3] Generated {len(video_uuids)} video UUIDs using {strategy} ({step_elapsed:.1f}ms)")

    # Fetch metadata
    step_start = time.time()
    videos = await get_videos_metadata_by_uuids(video_uuids)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[GUEST RELOAD Step 3/3] Fetched metadata for {len(videos)} videos ({step_elapsed:.1f}ms)")

    # Transform
    def transform_video(v: dict) -> VideoResponse:
        return VideoResponse(
            id=v["id"],
            video_id=v["video_id"],
            title=v["title"],
            thumbnail=v["thumbnail_link"],
            channel=ChannelInfo(
                name=v["channel_title"],
                avatar=generate_channel_avatar(v["channel_title"]),
                verified=is_verified(v.get("views", 0), v.get("likes", 0)),
                id=v["channel_title"]
            ),
            views=format_views(v.get("views", 0)),
            timestamp=format_timestamp(v.get("publish_time", "")),
            publish_time_raw=v.get("publish_time", ""),
            duration="10:00",
            category=v.get("category_name", "Unknown"),
            velocity_score=v.get("velocity_score")
        )

    video_responses = [transform_video(v) for v in videos]

    total_elapsed = (time.time() - total_start) * 1000
    print(f"{'#'*70}")
    print(f"[GUEST RELOAD] Complete! Strategy: {strategy}, Videos: {len(video_responses)}, Total: {total_elapsed:.1f}ms")
    print(f"{'#'*70}\n")

    return FeedResponse(
        videos=video_responses,
        strategy=strategy,
        interaction_count=interaction_count,
        total=len(video_responses)
    )


@router.post("/watch", response_model=WatchEventResponse)
async def record_guest_watch(request: WatchEventRequest):
    """
    Record guest watch event (INSERT to start, UPDATE to finish).

    ═══════════════════════════════════════════════════════════════════════════════════
    TWO-PHASE WATCH TRACKING:
    ═══════════════════════════════════════════════════════════════════════════════════

    WHY TWO PHASES?

    Problem:
        - We don't know watch duration until user leaves the video
        - We need to track views immediately when video plays
        - YouTube iframe API only exposes duration AFTER watching

    Solution:
        - Phase 1 (INSERT): Create record immediately when video starts
        - Phase 2 (UPDATE): Fill in actual duration when video ends

    ═══════════════════════════════════════════════════════════════════════════════════

    PHASE 1: INSERT (When User Clicks Video)
    ─────────────────────────────────────────

    REQUEST:
    {
        "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "guest_uuid": "550e8400-e29b-41d4-a716-446655440000"
        // Note: No watch_id, no duration
    }

    WHAT HAPPENS:
    1. Insert watch_history row with:
        - user_id: NULL (not authenticated)
        - guest_uuid: from request
        - video_id: from request (UUID)
        - watch_duration_seconds: 0 (placeholder)
        - started_at: NOW()
        - ended_at: NULL

    2. Increment video view count in videos table
        - This ensures view count updates immediately
        - Even if user leaves before finishing

    3. Return watch_id (UUID of the new record)

    RESPONSE:
    {
        "watch_id": "w4t5c6h7-i8d9-a0b1-c2d3-e4f5g6h7i8j9",
        "success": true
    }

    FRONTEND FLOW:
    - Save watch_id from response
    - Launch YouTube iframe with this video_id
    - User starts watching

    ═══════════════════════════════════════════════════════════════════════════════════

    PHASE 2: UPDATE (When User Leaves Video)
    ──────────────────────────────────────────

    REQUEST:
    {
        "video_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "watch_id": "w4t5c6h7-i8d9-a0b1-c2d3-e4f5g6h7i8j9",
        "watch_duration_seconds": 42,
        "guest_uuid": "550e8400-e29b-41d4-a716-446655440000"
    }

    WHAT HAPPENS:
    1. Update watch_history row with:
        - watch_duration_seconds: 42 (from YouTube iframe API)
        - ended_at: NOW()

    2. Database may trigger other updates:
        - watch_percentage: 42/300 = 14% (if video is 300s)
        - interaction count updates (handled by DB triggers)

    3. Return success=true

    RESPONSE:
    {
        "success": true,
        "watch_id": "w4t5c6h7-i8d9-a0b1-c2d3-e4f5g6h7i8j9"
    }

    FRONTEND FLOW:
    - User navigates away or closes video
    - Get duration from YouTube iframe API: player.getCurrentTime()
    - Call this endpoint with duration + watch_id

    ═══════════════════════════════════════════════════════════════════════════════════

    COMPLETE TIMELINE:

    T=0s: User sees video in feed, clicks thumbnail
          POST /watch (INSERT) → watch_id returns
          Frontend: saves watch_id, plays iframe

    T=5s: YouTube iframe playing (duration 0-5s watched)

    T=42s: User closes tab or navigates away
          Frontend: Get currentTime() = 42s from YouTube API
          POST /watch (UPDATE) → success=true

    Database result:
      watch: {duration: 42s, started: T=0, ended: T=42, video_id: "uuid"}

    ═══════════════════════════════════════════════════════════════════════════════════

    KEY DETAILS:

    View Counting:
      - Views incremented on INSERT only (not UPDATE)
      - Even if duration is 0, user "viewed" the video
      - Guests can only increment views (not decrement)

    Watch Duration:
      - 0 = user clicked but left immediately
      - N = user watched N seconds
      - Used for recommendation taste vector (watched videos gain weight)

    Null Handling:
      - UPDATE with no watch_id → Error (misuse)
      - UPDATE with invalid watch_id → No-op or error
      - Missing guest_uuid → Error (required for audit trail)

    Edge Cases:
      - User clicks video but closes tab before iframe loads
        → INSERT succeeded, UPDATE never called
        → view_count increased, duration = 0
        → OK because view was attempted

      - User refreshes page mid-video
        → New INSERT, view count increases again
        → Two watch records created (expected behavior)

      - Duration > video_length
        → Should not happen (YouTube API bounds it)
        → Backend accepts it silently (no validation)

    ═══════════════════════════════════════════════════════════════════════════════════

    ARGS:
        request: WatchEventRequest
            - video_uuid (required): UUID from videos.id
            - guest_uuid (required): Guest identifier
            - watch_id (optional): From INSERT response, required for UPDATE
            - watch_duration_seconds (optional): From YouTube iframe API, UPDATE only

    RETURNS:
        WatchEventResponse:
            - watch_id: Returned on INSERT, echoed on UPDATE
            - success: Always true if no error
    """
    # MODE 1: INSERT
    if not request.watch_id:
        watch_id = await insert_watch_history(
            user_id=None,
            guest_uuid=request.guest_uuid,
            video_uuid=request.video_uuid
        )

        # Increment video view count (guests can only increase, not decrease)
        view_increment_success = await increment_video_views(request.video_uuid)
        if view_increment_success:
            print(f"[DEBUG] Incremented view count for video {request.video_uuid} (guest)")
        else:
            print(f"[WARNING] Failed to increment view count for video {request.video_uuid} (guest)")

        return WatchEventResponse(watch_id=watch_id, success=True)

    # MODE 2: UPDATE
    else:
        await update_watch_history(
            watch_id=request.watch_id,
            watch_duration_seconds=request.watch_duration_seconds or 0,
            # video_duration_seconds=request.video_duration_seconds
        )
        return WatchEventResponse(watch_id=request.watch_id, success=True)


# @router.get("/session/{guest_uuid}", response_model=GuestSessionResponse)
# async def get_guest_session(guest_uuid: str):
#     """
#     Return guest session info.
#     Guest data is managed via localStorage on the frontend.
#     """
#     return GuestSessionResponse(
#         guest_uuid=guest_uuid,
#         interaction_count=0,
#         created_at=datetime.utcnow()
#     )


# @router.delete("/session/{guest_uuid}", response_model=MessageResponse)
# async def delete_guest_session(guest_uuid: str):
#     """
#     Acknowledge guest session deletion.
#     Actual deletion happens via localStorage on the frontend.
#     """
#     return MessageResponse(message="Guest session deleted successfully")
