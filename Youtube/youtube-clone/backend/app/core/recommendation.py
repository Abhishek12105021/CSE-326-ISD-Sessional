import numpy as np
import random
from typing import Optional
from app.db import (
    get_videos_by_uuids,
    search_videos_semantic,
    get_trending_videos,
    get_all_country_embeddings
)


async def build_taste_vector_from_uuids(video_uuids: list[str]) -> Optional[np.ndarray]:
    """
    Build taste vector from list of video UUIDs.

    Steps:
    1. Fetch video rows by UUID (includes embeddings)
    2. Extract embedding column from each row
    3. Mean pool all embeddings
    4. Normalize to unit vector
    5. Return (1024,) numpy array

    Returns None if no valid embeddings found.
    """
    if not video_uuids:
        return None

    # Fetch full video rows by UUID
    video_rows = await get_videos_by_uuids(video_uuids)

    if not video_rows:
        return None

    # Extract embeddings
    vectors = [row["embedding"] for row in video_rows if row.get("embedding")]

    if not vectors:
        return None

    # Convert to numpy
    vectors = np.array(vectors, dtype=np.float32)

    # Mean pool
    taste = vectors.mean(axis=0)  # (1024,)

    # Normalize
    taste = taste / np.linalg.norm(taste)

    return taste


async def compute_country_affinity(
    taste_vector: np.ndarray,
    foreign_countries: list[str]
) -> dict[str, float]:
    """
    Compute affinity scores for each foreign country.

    Algorithm (from notebook):
    1. For each country, fetch ALL video embeddings
    2. Compute: similarity = embedding · taste_vector
    3. Affinity = mean(similarities)

    Returns: {"GB": 0.5941, "CA": 0.5783, ...}
    """
    taste_vector = taste_vector.flatten()
    country_affinity = {}

    for country in foreign_countries:
        embeddings = await get_all_country_embeddings(country)

        if not embeddings:
            country_affinity[country] = 0.0
            continue

        vecs = np.array(embeddings, dtype=np.float32)
        sims = np.dot(vecs, taste_vector)
        affinity = float(np.mean(sims))
        country_affinity[country] = affinity

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
        pool_size=100,
        exclude_ids=[]
    )

    used_ids = [v["video_id"] for v in global_trending]
    local_trending = await get_trending_videos(
        filter_country=user_region,
        match_count=n_local,
        pool_size=50,
        exclude_ids=used_ids
    )

    all_videos = global_trending + local_trending
    random.shuffle(all_videos)

    return all_videos[:total]


async def generate_phase2_feed(
    taste_vector: np.ndarray,
    user_region: str,
    total: int = 30
) -> list[dict]:
    """
    Phase 2: Warm-Up (1-4 interactions)

    30% Vector Search + 40% Trending + 30% Local
    """
    n_vector = round(total * 0.3)
    n_trending = round(total * 0.4)
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
        pool_size=100,
        exclude_ids=list(used_ids)
    )
    used_ids.update(v["video_id"] for v in trending)

    local = await get_trending_videos(
        filter_country=user_region,
        match_count=n_local,
        pool_size=50,
        exclude_ids=list(used_ids)
    )

    all_videos = vector_results + trending + local
    return all_videos[:total]


async def generate_phase3_feed(
    taste_vector: np.ndarray,
    user_region: str,
    total: int = 30
) -> list[dict]:
    """
    Phase 3: Fully Personalized (5+ interactions)

    4-Bucket Strategy from notebook:
    - Bucket A (60%): Semantic / Same Region
    - Bucket B (20%): Semantic / Foreign Mix (affinity-weighted)
    - Bucket C (10%): Trending / User Region
    - Bucket D (10%): Trending / Global Mix
    """
    N_A = round(total * 0.6)  # 18
    N_B = round(total * 0.2)  # 6
    N_C = round(total * 0.1)  # 3
    N_D = total - N_A - N_B - N_C  # 3

    # ===========================================
    # BUCKET A: Semantic / Same Region (60%)
    # ===========================================
    bucket_a = await search_videos_semantic(
        query_embedding=taste_vector.tolist(),
        filter_country=user_region,
        match_count=N_A
    )
    used_ids = {v["video_id"] for v in bucket_a}

    # ===========================================
    # BUCKET B: Semantic / Mixed Foreign (20%)
    # ===========================================
    all_foreign = ["GB", "CA", "JP", "DE", "FR", "IN", "KR", "MX", "RU"]
    foreign = [c for c in all_foreign if c != user_region]

    # Compute affinity
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
    bucket_b = []
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
    # BUCKET C: Trending / User Region (10%)
    # ===========================================
    bucket_c = await get_trending_videos(
        filter_country=user_region,
        match_count=N_C,
        pool_size=50,
        exclude_ids=list(used_ids)
    )
    used_ids.update(v["video_id"] for v in bucket_c)

    # ===========================================
    # BUCKET D: Trending / Global Mix (10%)
    # ===========================================
    bucket_d = await get_trending_videos(
        filter_country=None,
        match_count=N_D,
        pool_size=150,
        exclude_ids=list(used_ids)
    )

    all_videos = bucket_a + bucket_b + bucket_c + bucket_d
    return all_videos[:total]
