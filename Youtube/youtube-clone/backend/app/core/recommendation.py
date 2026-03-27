import numpy as np
import random
import time
from typing import Optional
from datetime import datetime, timedelta
from app.db import (
    get_watch_history,
    get_user_liked_videos_with_timestamps
)
from app.core import faiss_manager

# Weight multiplier for liked videos (explicit positive signal)
LIKE_WEIGHT_MULTIPLIER = 2.0

# Decay constant: 14 days (in seconds) - gentler decay to prevent dilution
# Videos from 14 days ago get ~0.5 weight of today
# Videos from 30 days ago still get ~0.15 weight (meaningful contribution)
DECAY_SECONDS = 14 * 24 * 3600


def _compute_time_decay(timestamp_str: Optional[str], now: datetime) -> float:
    """
    Compute exponential time decay weight from timestamp.

    Formula: exp(-age_seconds / DECAY_SECONDS)
    - 14 days ago -> ~0.5 weight
    - 30 days ago -> ~0.15 weight
    - 60 days ago -> ~0.02 weight

    Args:
        timestamp_str: ISO format timestamp string
        now: Current datetime for age calculation

    Returns:
        Decay weight between 0 and 1
    """
    if not timestamp_str:
        return 1.0

    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        # Handle timezone-aware vs naive datetime
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        age_seconds = max(0, (now - ts).total_seconds())
        return float(np.exp(-age_seconds / DECAY_SECONDS))
    except Exception:
        return 1.0


async def get_taste_vector_for_feed(user_id: str) -> tuple[Optional[np.ndarray], int]:
    """
    Get taste vector for feed generation (FAISS-optimized).

    Strategy:
    1. Check if taste vector is cached in faiss_manager (O(1) dict lookup)
    2. If cached, return immediately
    3. If not cached, rebuild from watch history and likes (lazy rebuild)
    4. Cache the rebuilt taste vector for future requests

    This replaces build_taste_vector_for_authenticated_user() with FAISS-based approach.

    Args:
        user_id: Authenticated user's UUID

    Returns:
        Tuple of:
        - taste_vector: (1024,) normalized numpy array, or None if no data
        - interaction_count: Total unique video interactions (for phase determination)
    """
    # Step 1: Check cache
    cached_taste = faiss_manager.get_taste_vector(user_id)
    if cached_taste is not None:
        # Get interaction count from history (fast, metadata only)
        watch_history = await get_watch_history(user_id, limit=1000)
        liked_videos = await get_user_liked_videos_with_timestamps(user_id, limit=500)
        interaction_count = len(set([h["video_id"] for h in watch_history] + [l["video_id"] for l in liked_videos]))
        print(f"[TASTE VECTOR] Using cached taste vector for user {user_id[:8]} ({interaction_count} interactions)")
        return cached_taste, interaction_count

    # Step 2: Lazy rebuild from history (first request after server restart)
    print(f"[TASTE VECTOR] Cache miss - rebuilding from history for user {user_id[:8]}...")
    total_start = time.time()

    # Fetch watch history and likes
    watch_history = await get_watch_history(user_id, limit=1000)
    liked_videos = await get_user_liked_videos_with_timestamps(user_id, limit=500)

    # Build unified video weight map
    video_weights: dict[str, float] = {}
    now = datetime.utcnow()

    # Process watch history
    max_duration = 1
    if watch_history:
        max_duration = max(
            max_duration,
            max(h.get("watch_duration_seconds", 0) for h in watch_history)
        )

    for entry in watch_history:
        video_id = entry["video_id"]
        started_at = entry.get("started_at")
        duration = entry.get("watch_duration_seconds", 0)

        # Compute time decay
        time_decay = _compute_time_decay(started_at, now)

        # Compute duration boost (sqrt normalization)
        duration_boost = np.sqrt(max(duration / max(max_duration, 1), 0.1))

        # Base weight for watched videos
        weight = time_decay * (1.0 + duration_boost)

        # Keep max weight if video appears multiple times
        video_weights[video_id] = max(video_weights.get(video_id, 0), weight)

    watched_count = len(video_weights)

    # Process liked videos (with multiplier)
    liked_added = 0
    for entry in liked_videos:
        video_id = entry["video_id"]
        liked_at = entry.get("liked_at")

        # Compute time decay
        time_decay = _compute_time_decay(liked_at, now)

        # Apply LIKE_WEIGHT_MULTIPLIER
        like_weight = time_decay * LIKE_WEIGHT_MULTIPLIER

        # If video was both watched AND liked, take the HIGHER weight
        current_weight = video_weights.get(video_id, 0)
        if video_id not in video_weights:
            liked_added += 1
        video_weights[video_id] = max(current_weight, like_weight)

    if not video_weights:
        print(f"[TASTE VECTOR] No interactions found for user {user_id[:8]}")
        return None, 0

    # Build taste vector from embeddings (in-memory via FAISS manager)
    vectors = []
    weights = []

    for video_id, weight in video_weights.items():
        embedding = faiss_manager.UUID_TO_EMBEDDING.get(video_id)
        if embedding is not None:
            vectors.append(embedding)
            weights.append(weight)

    if not vectors:
        print(f"[TASTE VECTOR] No valid embeddings found for user {user_id[:8]}")
        return None, len(video_weights)

    vectors_arr = np.array(vectors, dtype=np.float32)
    weights_arr = np.array(weights, dtype=np.float32)
    weights_arr = weights_arr / weights_arr.sum()  # Normalize

    # Weighted average: (N, 1024).T @ (N,) -> (1024,)
    taste = (vectors_arr.T @ weights_arr).astype(np.float32)
    taste = taste / np.linalg.norm(taste)  # Unit normalize

    interaction_count = len(video_weights)
    total_elapsed = (time.time() - total_start) * 1000

    print(f"[TASTE VECTOR] Rebuilt taste vector: {interaction_count} interactions, {total_elapsed:.1f}ms")

    # Cache the rebuilt taste vector
    faiss_manager.set_taste_vector(user_id, taste)

    return taste, interaction_count


async def build_taste_vector_for_authenticated_user(
    user_id: str
) -> tuple[Optional[np.ndarray], int]:
    """
    Build taste vector for authenticated users by fetching all signals from DB.

    Unlike build_taste_vector_from_uuids(), this function:
    1. Does NOT take a list of video UUIDs as input
    2. Fetches ALL watch history from DB
    3. Fetches ALL liked videos from DB with timestamps
    4. Applies time-decay to both signals
    5. Applies LIKE_WEIGHT_MULTIPLIER (2.0x) to liked videos
    6. Combines into a single weighted taste vector

    Liked videos are given higher weight because they represent explicit
    positive signals, while watch history may include videos the user
    didn't enjoy.

    Args:
        user_id: Authenticated user's UUID

    Returns:
        Tuple of:
        - taste_vector: (1024,) normalized numpy array, or None if no data
        - interaction_count: Total unique video interactions (for phase determination)
    """
    total_start = time.time()
    print(f"\n{'='*60}")
    print(f"[TASTE VECTOR] Building taste vector for user {user_id[:8]}...")
    print(f"{'='*60}")

    # Step 1: Fetch all watch history
    step_start = time.time()
    watch_history = await get_watch_history(user_id, limit=1000)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[Step 1/5] Fetched watch history: {len(watch_history)} entries ({step_elapsed:.1f}ms)")

    # Step 2: Fetch all liked videos with timestamps
    step_start = time.time()
    liked_videos = await get_user_liked_videos_with_timestamps(user_id, limit=500)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[Step 2/5] Fetched liked videos: {len(liked_videos)} entries ({step_elapsed:.1f}ms)")

    # Step 3: Build unified video weight map
    step_start = time.time()
    video_weights: dict[str, float] = {}
    now = datetime.utcnow()

    # Process watch history
    max_duration = 1
    if watch_history:
        max_duration = max(
            max_duration,
            max(h.get("watch_duration_seconds", 0) for h in watch_history)
        )

    for entry in watch_history:
        video_id = entry["video_id"]
        started_at = entry.get("started_at")
        duration = entry.get("watch_duration_seconds", 0)

        # Compute time decay
        time_decay = _compute_time_decay(started_at, now)

        # Compute duration boost (sqrt normalization)
        duration_boost = np.sqrt(max(duration / max(max_duration, 1), 0.1))

        # Base weight for watched videos
        weight = time_decay * (1.0 + duration_boost)

        # Keep max weight if video appears multiple times
        video_weights[video_id] = max(video_weights.get(video_id, 0), weight)

    watched_count = len(video_weights)

    # Process liked videos (with multiplier)
    liked_added = 0
    for entry in liked_videos:
        video_id = entry["video_id"]
        liked_at = entry.get("liked_at")

        # Compute time decay
        time_decay = _compute_time_decay(liked_at, now)

        # Apply LIKE_WEIGHT_MULTIPLIER
        like_weight = time_decay * LIKE_WEIGHT_MULTIPLIER

        # If video was both watched AND liked, take the HIGHER weight
        # (liked weight is almost always higher due to multiplier)
        current_weight = video_weights.get(video_id, 0)
        if video_id not in video_weights:
            liked_added += 1
        video_weights[video_id] = max(current_weight, like_weight)

    step_elapsed = (time.time() - step_start) * 1000
    print(f"[Step 3/5] Computed weights: {len(video_weights)} unique videos "
          f"(watched: {watched_count}, liked-only: {liked_added}, multiplier: {LIKE_WEIGHT_MULTIPLIER}x) ({step_elapsed:.1f}ms)")

    if not video_weights:
        total_elapsed = (time.time() - total_start) * 1000
        print(f"[TASTE VECTOR] No interactions found. Total: {total_elapsed:.1f}ms")
        print(f"{'='*60}\n")
        return None, 0

    # Step 4: Fetch embeddings for all videos
    step_start = time.time()
    video_ids = list(video_weights.keys())
    video_rows = await get_videos_by_uuids(video_ids)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[Step 4/5] Fetched embeddings: {len(video_rows)}/{len(video_ids)} videos ({step_elapsed:.1f}ms)")

    if not video_rows:
        total_elapsed = (time.time() - total_start) * 1000
        print(f"[TASTE VECTOR] No embeddings found. Total: {total_elapsed:.1f}ms")
        print(f"{'='*60}\n")
        return None, len(video_weights)

    # Step 5: Build weighted average
    step_start = time.time()
    vectors = []
    weights = []

    for row in video_rows:
        video_id = row["id"]
        if row.get("embedding") and video_id in video_weights:
            vectors.append(row["embedding"])
            weights.append(video_weights[video_id])

    if not vectors:
        total_elapsed = (time.time() - total_start) * 1000
        print(f"[TASTE VECTOR] No valid embeddings. Total: {total_elapsed:.1f}ms")
        print(f"{'='*60}\n")
        return None, len(video_weights)

    vectors_arr = np.array(vectors, dtype=np.float32)
    weights_arr = np.array(weights, dtype=np.float32)
    weights_arr = weights_arr / weights_arr.sum()  # Normalize

    # Weighted average: (N, 1024).T @ (N,) -> (1024,)
    taste = (vectors_arr.T @ weights_arr).astype(np.float32)
    taste = taste / np.linalg.norm(taste)  # Unit normalize

    interaction_count = len(video_weights)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[Step 5/5] Built taste vector: shape={taste.shape}, norm={np.linalg.norm(taste):.4f} ({step_elapsed:.1f}ms)")

    total_elapsed = (time.time() - total_start) * 1000
    print(f"[TASTE VECTOR] Complete! Interactions: {interaction_count}, Total: {total_elapsed:.1f}ms")
    print(f"{'='*60}\n")

    return taste, interaction_count


async def build_taste_vector_from_uuids(
    video_uuids: list[str],
    watch_history: Optional[list[dict]] = None,
    use_recency_weighting: bool = True
) -> Optional[np.ndarray]:
    """
    Build taste vector from list of video UUIDs with recency weighting.

    Improvements over simple mean pooling:
    1. Recent videos have higher weight (exponential decay)
    2. Videos watched longer have higher weight
    3. Weights normalized to sum to 1.0
    4. Better captures current user preferences as history grows

    Args:
        video_uuids: List of video UUIDs in reverse chronological order (newest first)
        watch_history: Watch history details with timestamps and duration
        use_recency_weighting: Enable exponential decay weighting (default True)

    Returns:
        (1024,) normalized numpy array, or None if no valid embeddings
    """
    if not video_uuids:
        return None

    # Fetch full video rows by UUID
    video_rows = await get_videos_by_uuids(video_uuids)

    if not video_rows:
        return None

    # Extract embeddings and build index map
    vectors = []
    uuid_to_embedding = {}
    for row in video_rows:
        if row.get("embedding"):
            vectors.append(row["embedding"])
            uuid_to_embedding[row["id"]] = row["embedding"]

    if not vectors:
        return None

    # Convert to numpy (ordered by video_uuids order)
    vectors = np.array(
        [uuid_to_embedding[uid] for uid in video_uuids if uid in uuid_to_embedding],
        dtype=np.float32
    )

    # Compute recency weights if watch_history provided
    if use_recency_weighting and watch_history and len(watch_history) > 0:
        weights = _compute_recency_weights(watch_history, len(vectors))
    else:
        # Fallback: linear decay if no detailed history
        weights = _compute_linear_decay_weights(len(vectors))

    # Apply weights: (N, 1024) @ (N,) -> (1024,)
    weights = weights / weights.sum()  # normalize
    taste = (vectors.T @ weights).astype(np.float32)

    # Normalize to unit vector
    taste = taste / np.linalg.norm(taste)

    return taste


def _compute_recency_weights(watch_history: list[dict], n_videos: int) -> np.ndarray:
    """
    Compute exponential decay weights based on watch timestamp and duration.

    Algorithm:
    1. Parse timestamps (newest first, assumed)
    2. Compute time decay: exp(-t / decay_constant)
    3. Apply duration boost: sqrt(watch_duration_seconds / max_duration)
    4. Combine: weight = time_decay * (1 + duration_boost)

    This ensures:
    - Recent watches have ~2x weight of older watches
    - Long-watched videos have higher influence
    - Very old watches decay close to 0
    """
    if not watch_history:
        return np.ones(n_videos, dtype=np.float32)

    weights = []
    now = datetime.utcnow()
    max_duration = max(
        h.get("watch_duration_seconds", 0) for h in watch_history[:n_videos]
    )
    max_duration = max(max_duration, 1)  # avoid division by zero

    # Decay constant: 7 days (in seconds)
    # Videos from 7 days ago get ~0.37 weight of today
    DECAY_SECONDS = 7 * 24 * 3600

    for i, history in enumerate(watch_history[:n_videos]):
        # Time decay
        started_at = history.get("started_at")
        if not started_at:
            time_decay = 1.0
        else:
            try:
                watch_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                age_seconds = max(0, (now - watch_time).total_seconds())
                time_decay = np.exp(-age_seconds / DECAY_SECONDS)
            except:
                time_decay = 1.0

        # Duration boost: fully watched videos (60% of content) get +50%
        duration_seconds = history.get("watch_duration_seconds", 0)
        duration_boost = np.sqrt(max(duration_seconds / max_duration, 0.1))

        # Combine weights
        weight = time_decay * (1.0 + duration_boost)
        weights.append(weight)

    return np.array(weights, dtype=np.float32)


def _compute_linear_decay_weights(n_videos: int) -> np.ndarray:
    """
    Fallback: linear decay from newest to oldest.
    Newest video gets weight n, oldest gets weight 1.
    """
    weights = np.linspace(n_videos, 1, n_videos, dtype=np.float32)
    return weights


async def compute_country_affinity(
    taste_vector: np.ndarray,
    foreign_countries: list[str]
) -> dict[str, float]:
    """
    Compute affinity scores for each foreign country.

    OPTIMIZED: Uses caching + sampling instead of fetching all embeddings.

    Algorithm:
    1. Check cache (valid for 1 hour)
    2. If cached, return immediately
    3. Otherwise: sample 500 embeddings per country instead of all 5000
    4. Compute: similarity = embedding · taste_vector
    5. Affinity = mean(similarities)
    6. Cache result

    Returns: {"GB": 0.5941, "CA": 0.5783, ...}
    """
    global _COUNTRY_AFFINITY_CACHE, _CACHE_TIMESTAMP

    # Check cache validity
    now = datetime.utcnow()
    if _CACHE_TIMESTAMP and (now - _CACHE_TIMESTAMP).total_seconds() < _CACHE_TTL_SECONDS:
        # Return cached values for requested countries
        return {c: _COUNTRY_AFFINITY_CACHE.get(c, 0.5) for c in foreign_countries}

    # Recompute affinity for all countries
    taste_vector = taste_vector.flatten()
    country_affinity = {}

    for country in foreign_countries:
        try:
            # Fetch embeddings (RPC will sample if needed)
            embeddings = await get_all_country_embeddings(country)

            if not embeddings:
                country_affinity[country] = 0.5  # neutral affinity
                continue

            # Sample ~500 embeddings if there are more
            if len(embeddings) > 500:
                sample_indices = np.random.choice(len(embeddings), size=500, replace=False)
                embeddings = [embeddings[i] for i in sample_indices]

            vecs = np.array(embeddings, dtype=np.float32)
            sims = np.dot(vecs, taste_vector)
            affinity = float(np.mean(sims))
            country_affinity[country] = affinity
        except Exception as e:
            # On error, assign neutral affinity
            print(f"[WARNING] Failed to compute affinity for {country}: {e}")
            country_affinity[country] = 0.5

    # Cache results
    _COUNTRY_AFFINITY_CACHE = country_affinity
    _CACHE_TIMESTAMP = now

    return country_affinity


async def generate_phase1_feed(
    user_region: str,
    watched_video_ids: list[str] = [],
    total: int = 30
) -> list[str]:
    """
    Phase 1: Absolute Cold Start (0 interactions)

    50% Global Trending + 50% Local Trending

    Returns list of video UUIDs (not full video objects - metadata fetched separately)

    Deduplicates results and limits watched video recurrence to max 10%.
    """
    if watched_video_ids is None:
        watched_video_ids = []

    n_global = total // 2
    n_local = total - n_global

    print(f"[PHASE 1] Cold Start | Bucket allocation → Global: {n_global} | Local ({user_region}): {n_local}")

    # Get trending from FAISS manager (in-memory) - over-fetch and filter
    global_trending_candidates = [
        uuid for uuid in faiss_manager.get_trending(country=None, top_n=300)
        if uuid not in watched_video_ids
    ]
    global_trending = random.sample(global_trending_candidates, min(n_global, len(global_trending_candidates)))
    print(f"[BUCKET GLOBAL] Trending (global) → {len(global_trending)} videos (after filtering {len(watched_video_ids)} excluded)")

    used_ids = set(global_trending)
    local_trending_candidates = [
        uuid for uuid in faiss_manager.get_trending(country=user_region, top_n=200)
        if uuid not in used_ids and uuid not in watched_video_ids
    ]
    local_trending = random.sample(local_trending_candidates, min(n_local, len(local_trending_candidates)))
    print(f"[BUCKET LOCAL] Trending ({user_region}) → {len(local_trending)} videos")

    all_video_ids = global_trending + local_trending
    random.shuffle(all_video_ids)

    # Deduplicate (safety check)
    seen_ids = set()
    deduped = []
    for vid in all_video_ids:
        if vid not in seen_ids:
            deduped.append(vid)
            seen_ids.add(vid)

    # No need for watched video filtering - already done
    final_video_ids = deduped[:total]
    print(f"[PHASE 1] Returning {len(final_video_ids)} video UUIDs (excluded {len(watched_video_ids)} watched videos)")

    return final_video_ids


async def generate_phase2_feed(
    taste_vector: np.ndarray,
    user_region: str,
    watched_video_ids: list[str] = [],
    interaction_count: int = 0,
    total: int = 30
) -> list[str]:
    """
    Phase 2: Warm-Up (1-4 interactions)

    Adaptive allocation based on interaction count:
    - 1-2 interactions: 20% vector search + 50% trending + 30% local
    - 3-4 interactions: 40% vector search + 35% trending + 25% local

    Returns list of video UUIDs (not full video objects - metadata fetched separately)

    Deduplicates results and limits watched video recurrence to max 10%.
    """
    if watched_video_ids is None:
        watched_video_ids = []

    # Increase vector search weight as history grows
    if interaction_count <= 2:
        n_vector = round(total * 0.2)
        n_trending = round(total * 0.5)
        n_local = total - n_vector - n_trending
        phase_label = "Early Warm-Up (1-2 interactions)"
    else:  # 3-4
        n_vector = round(total * 0.4)
        n_trending = round(total * 0.35)
        n_local = total - n_vector - n_trending
        phase_label = "Strong Warm-Up (3-4 interactions)"

    print(f"[PHASE 2] {phase_label} | Bucket allocation → Semantic: {n_vector} | Global Trending: {n_trending} | Local ({user_region}): {n_local}")

    # Semantic search via FAISS (global, no country filter) - over-fetch 15x
    vector_results = faiss_manager.search_similar(
        taste_vector=taste_vector,
        k=max(n_vector * 15, 100),  # Aggressive over-fetch for large exclusion lists
        filter_country=None
    )
    # Filter out watched videos and limit to n_vector
    vector_uuids = [uuid for uuid, score in vector_results if uuid not in watched_video_ids][:n_vector]
    print(f"[BUCKET SEMANTIC] Semantic search (global) → {len(vector_uuids)} videos (after filtering {len(watched_video_ids)} excluded)")
    used_ids = set(vector_uuids)

    # Trending global - over-fetch and filter
    trending_candidates = [
        uuid for uuid in faiss_manager.get_trending(country=None, top_n=300)
        if uuid not in used_ids and uuid not in watched_video_ids
    ]
    trending = random.sample(trending_candidates, min(n_trending, len(trending_candidates)))
    print(f"[BUCKET TRENDING] Trending (global) → {len(trending)} videos")
    used_ids.update(trending)

    # Local trending - over-fetch and filter
    local_candidates = [
        uuid for uuid in faiss_manager.get_trending(country=user_region, top_n=200)
        if uuid not in used_ids and uuid not in watched_video_ids
    ]
    local = random.sample(local_candidates, min(n_local, len(local_candidates)))
    print(f"[BUCKET LOCAL] Trending ({user_region}) → {len(local)} videos")

    all_video_ids = vector_uuids + trending + local

    # Deduplicate (safety check)
    seen_ids = set()
    deduped = []
    for vid in all_video_ids:
        if vid not in seen_ids:
            deduped.append(vid)
            seen_ids.add(vid)

    # No need for watched video filtering - already done in each bucket
    final_video_ids = deduped[:total]
    print(f"[PHASE 2] Returning {len(final_video_ids)} video UUIDs (excluded {len(watched_video_ids)} watched videos)")

    return final_video_ids


async def generate_phase3_feed(
    taste_vector: np.ndarray,
    user_region: str,
    watched_video_ids: list[str] = [],
    interaction_count: int = 5,
    total: int = 30
) -> list[str]:
    """
    Phase 3: Fully Personalized (5+ interactions)

    Adaptive 4-Bucket Strategy that increases personalization with history:

    5-9 interactions (Early Personalization):
    - Bucket A (60%): Semantic / Same Region
    - Bucket B (20%): Semantic / Foreign Mix
    - Bucket C (10%): Trending / User Region
    - Bucket D (10%): Trending / Global Mix

    10-19 interactions (Strong Personalization):
    - Bucket A (70%): Semantic / Same Region
    - Bucket B (15%): Semantic / Foreign Mix
    - Bucket C (10%): Trending / User Region
    - Bucket D (5%): Trending / Global Mix

    20+ interactions (Heavy Personalization):
    - Bucket A (75%): Semantic / Same Region
    - Bucket B (15%): Semantic / Foreign Mix
    - Bucket C (7%): Trending / User Region
    - Bucket D (3%): Trending / Global Mix

    Returns list of video UUIDs (not full video objects - metadata fetched separately)

    Deduplicates results and limits watched video recurrence to max 10%.
    """
    if watched_video_ids is None:
        watched_video_ids = []

    # Determine allocation based on interaction count
    if interaction_count < 10:
        N_A = round(total * 0.60)
        N_B = round(total * 0.20)
        N_C = round(total * 0.10)
        phase_label = "Early Personalization"
    elif interaction_count < 20:
        N_A = round(total * 0.70)
        N_B = round(total * 0.15)
        N_C = round(total * 0.10)
        phase_label = "Strong Personalization"
    else:  # 20+
        N_A = round(total * 0.75)
        N_B = round(total * 0.15)
        N_C = round(total * 0.07)
        phase_label = "Heavy Personalization"

    N_D = total - N_A - N_B - N_C

    # Log bucket allocation
    print(f"[PHASE 3] {phase_label} | Bucket allocation → A: {N_A} | B: {N_B} | C: {N_C} | D: {N_D} | Total: {total}")

    # ===========================================
    # BUCKET A: Semantic / Same Region (60-75%)
    # ===========================================
    # Over-fetch to account for watched/excluded videos (15x multiplier)
    bucket_a_results = faiss_manager.search_similar(
        taste_vector=taste_vector,
        k=max(N_A * 15, 150),  # Aggressive over-fetch for large exclusion lists
        filter_country=user_region
    )
    # Filter out watched videos and limit to N_A
    bucket_a = [uuid for uuid, score in bucket_a_results if uuid not in watched_video_ids][:N_A]
    used_ids = set(bucket_a)
    print(f"[BUCKET A] Semantic / Same Region ({user_region}) → {len(bucket_a)} videos (after filtering {len(watched_video_ids)} excluded)")

    # ===========================================
    # BUCKET B: Semantic / Mixed Foreign (15-20%)
    # ===========================================
    all_foreign = ["GB", "CA", "JP", "DE", "FR", "IN", "KR", "MX", "RU"]
    foreign = [c for c in all_foreign if c != user_region]

    bucket_b = []

    # For early personalization (5-9 interactions), use simple random distribution
    # to avoid expensive country affinity computation
    if interaction_count < 10:
        # Random country selection (fast path)
        n_countries = min(max(1, N_B // 3), len(foreign))  # 1-3 countries
        chosen = np.random.choice(foreign, size=n_countries, replace=False).tolist()

        # Distribute slots evenly
        slots = {cc: N_B // n_countries for cc in chosen}
        leftover = N_B % n_countries
        for i in range(leftover):
            slots[chosen[i]] += 1

        print(f"[BUCKET B] Semantic / Mixed Foreign (early, random) → {len(chosen)} countries: {list(slots.keys())}")
    else:
        # For strong personalization (10+), compute affinity via FAISS manager
        country_affinity = faiss_manager.get_country_affinity(taste_vector, foreign, top_k=min(5, len(foreign)))

        # Log affinity scores
        affinity_str = " | ".join(f"{cc}: {v:.4f}" for cc, v in sorted(country_affinity.items(), key=lambda x: -x[1]))
        print(f"[BUCKET B] Country affinity scores: {affinity_str}")

        # Convert to probabilities
        affinity_vals = np.array([country_affinity.get(c, 0.5) for c in foreign])
        weights = affinity_vals - affinity_vals.min() + 1e-3
        weights = weights / weights.sum()

        # Probabilistic selection (no replacement)
        n_countries = min(N_B, len(foreign))
        chosen = np.random.choice(foreign, size=n_countries, replace=False, p=weights).tolist()

        # Distribute slots
        slots = {cc: 1 for cc in chosen}
        leftover = N_B - n_countries
        if leftover > 0:
            sorted_c = sorted(chosen, key=lambda c: -country_affinity.get(c, 0.5))
            for cc in sorted_c[:leftover]:
                slots[cc] += 1

        print(f"[BUCKET B] Semantic / Mixed Foreign (strong/heavy) → Slot allocation: {slots}")

    # Fetch per country via FAISS
    for country, n_slots in slots.items():
        results = faiss_manager.search_similar(
            taste_vector=taste_vector,
            k=max((n_slots + 5) * 10, 50),  # 10x over-fetch for large exclusion lists
            filter_country=country
        )
        for uuid, score in results:
            if uuid not in used_ids and uuid not in watched_video_ids and len(bucket_b) < N_B:
                bucket_b.append(uuid)
                used_ids.add(uuid)

    print(f"[BUCKET B] Fetched {len(bucket_b)} videos from foreign countries")

    # ===========================================
    # BUCKET C: Trending / User Region (7-10%)
    # ===========================================
    # Over-fetch and filter watched videos
    bucket_c_candidates = [
        uuid for uuid in faiss_manager.get_trending(country=user_region, top_n=200)
        if uuid not in used_ids and uuid not in watched_video_ids
    ]
    bucket_c = random.sample(bucket_c_candidates, min(N_C, len(bucket_c_candidates)))
    used_ids.update(bucket_c)
    print(f"[BUCKET C] Trending / User Region ({user_region}) → {len(bucket_c)} videos")

    # ===========================================
    # BUCKET D: Trending / Global Mix (3-10%)
    # ===========================================
    # Over-fetch and filter watched videos
    bucket_d_candidates = [
        uuid for uuid in faiss_manager.get_trending(country=None, top_n=300)
        if uuid not in used_ids and uuid not in watched_video_ids
    ]
    bucket_d = random.sample(bucket_d_candidates, min(N_D, len(bucket_d_candidates)))
    print(f"[BUCKET D] Trending / Global Mix → {len(bucket_d)} videos")

    all_video_ids = bucket_a + bucket_b + bucket_c + bucket_d

    # Deduplicate (shouldn't be needed since we track used_ids, but safety check)
    seen_ids = set()
    deduped = []
    for vid in all_video_ids:
        if vid not in seen_ids:
            deduped.append(vid)
            seen_ids.add(vid)

    # No need for watched video filtering - already done in each bucket
    final_video_ids = deduped[:total]
    print(f"[PHASE 3] Returning {len(final_video_ids)} video UUIDs (excluded {len(watched_video_ids)} watched videos)")

    return final_video_ids
