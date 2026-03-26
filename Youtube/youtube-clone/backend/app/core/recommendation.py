import numpy as np
import random
from typing import Optional
from datetime import datetime, timedelta
from app.db import (
    get_videos_by_uuids,
    search_videos_semantic,
    get_trending_videos,
    get_all_country_embeddings,
    get_watch_history
)

# Simple in-memory cache for country affinity (per session)
_COUNTRY_AFFINITY_CACHE = {}
_CACHE_TIMESTAMP = None
_CACHE_TTL_SECONDS = 3600  # 1 hour


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


async def generate_phase1_feed(user_region: str, total: int = 30) -> list[dict]:
    """
    Phase 1: Absolute Cold Start (0 interactions)

    50% Global Trending + 50% Local Trending
    """
    n_global = total // 2
    n_local = total - n_global

    global_trending = await get_trending_videos(
        filter_country=None,
        match_count=n_global,
        pool_size=60,  # Reduced from 100
        exclude_ids=[]
    )

    used_ids = [v["video_id"] for v in global_trending]
    local_trending = await get_trending_videos(
        filter_country=user_region,
        match_count=n_local,
        pool_size=30,  # Reduced from 50
        exclude_ids=used_ids
    )

    all_videos = global_trending + local_trending
    random.shuffle(all_videos)

    return all_videos[:total]


async def generate_phase2_feed(
    taste_vector: np.ndarray,
    user_region: str,
    interaction_count: int = 0,
    total: int = 30
) -> list[dict]:
    """
    Phase 2: Warm-Up (1-4 interactions)

    Adaptive allocation based on interaction count:
    - 1-2 interactions: 20% vector search + 50% trending + 30% local
    - 3-4 interactions: 40% vector search + 35% trending + 25% local

    As users watch more, we increase trust in the taste vector.
    """
    # Increase vector search weight as history grows
    if interaction_count <= 2:
        n_vector = round(total * 0.2)
        n_trending = round(total * 0.5)
        n_local = total - n_vector - n_trending
    else:  # 3-4
        n_vector = round(total * 0.4)
        n_trending = round(total * 0.35)
        n_local = total - n_vector - n_trending

    vector_results = await search_videos_semantic(
        query_embedding=taste_vector.tolist(),
        filter_country=None,  # global for diversity
        match_count=n_vector
    )
    used_ids = {v["video_id"] for v in vector_results}

    trending = await get_trending_videos(
        filter_country=None,
        match_count=n_trending,
        pool_size=60,  # Reduced from 100
        exclude_ids=list(used_ids)
    )
    used_ids.update(v["video_id"] for v in trending)

    local = await get_trending_videos(
        filter_country=user_region,
        match_count=n_local,
        pool_size=30,  # Reduced from 50
        exclude_ids=list(used_ids)
    )

    all_videos = vector_results + trending + local
    return all_videos[:total]


async def generate_phase3_feed(
    taste_vector: np.ndarray,
    user_region: str,
    interaction_count: int = 5,
    total: int = 30
) -> list[dict]:
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
    """
    # Determine allocation based on interaction count
    if interaction_count < 10:
        N_A = round(total * 0.60)
        N_B = round(total * 0.20)
        N_C = round(total * 0.10)
    elif interaction_count < 20:
        N_A = round(total * 0.70)
        N_B = round(total * 0.15)
        N_C = round(total * 0.10)
    else:  # 20+
        N_A = round(total * 0.75)
        N_B = round(total * 0.15)
        N_C = round(total * 0.07)

    N_D = total - N_A - N_B - N_C

    # ===========================================
    # BUCKET A: Semantic / Same Region (60-75%)
    # ===========================================
    bucket_a = await search_videos_semantic(
        query_embedding=taste_vector.tolist(),
        filter_country=user_region,
        match_count=N_A
    )
    used_ids = {v["video_id"] for v in bucket_a}

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
    else:
        # For strong personalization (10+), compute affinity and use weighted distribution
        country_affinity = await compute_country_affinity(taste_vector, foreign)

        # Convert to probabilities
        affinity_vals = np.array([country_affinity[c] for c in foreign])
        weights = affinity_vals - affinity_vals.min() + 1e-3
        weights = weights / weights.sum()

        # Probabilistic selection (no replacement)
        n_countries = min(N_B, len(foreign))
        chosen = np.random.choice(foreign, size=n_countries, replace=False, p=weights).tolist()

        # Distribute slots
        slots = {cc: 1 for cc in chosen}
        leftover = N_B - n_countries
        if leftover > 0:
            sorted_c = sorted(chosen, key=lambda c: -country_affinity[c])
            for cc in sorted_c[:leftover]:
                slots[cc] += 1

    # Fetch per country
    for country, n_slots in slots.items():
        results = await search_videos_semantic(
            query_embedding=taste_vector.tolist(),
            filter_country=country,
            match_count=n_slots + 2
        )
        for v in results:
            if v["video_id"] not in used_ids and len(bucket_b) < N_B:
                bucket_b.append(v)
                used_ids.add(v["video_id"])

    # ===========================================
    # BUCKET C: Trending / User Region (7-10%)
    # ===========================================
    bucket_c = await get_trending_videos(
        filter_country=user_region,
        match_count=N_C,
        pool_size=30,  # Reduced from 50
        exclude_ids=list(used_ids)
    )
    used_ids.update(v["video_id"] for v in bucket_c)

    # ===========================================
    # BUCKET D: Trending / Global Mix (3-10%)
    # ===========================================
    bucket_d = await get_trending_videos(
        filter_country=None,
        match_count=N_D,
        pool_size=80,  # Reduced from 150
        exclude_ids=list(used_ids)
    )

    all_videos = bucket_a + bucket_b + bucket_c + bucket_d
    return all_videos[:total]
