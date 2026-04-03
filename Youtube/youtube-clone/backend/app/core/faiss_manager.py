"""
FAISS-based in-memory embedding manager for fast recommendation serving.

This module loads all video embeddings into RAM at server boot and provides
fast similarity search using Facebook's FAISS library instead of pgvector.

Performance improvement: 15-20s → 300-500ms per feed request
Memory footprint: ~100-150MB for 24K videos

Key Components:
- FAISS_INDEX: IndexFlatIP for inner product similarity search (cosine after normalization)
- UUID_TO_EMBEDDING: Dict for O(1) taste vector lookup
- UUID_TO_META: Dict with country_code and velocity_score for filtering
- USER_TASTE_VECTORS: In-memory taste vectors updated incrementally via EMA
"""
import numpy as np
import faiss
from typing import Optional
from uuid import UUID

# ==================== GLOBAL IN-MEMORY STRUCTURES ====================

# FAISS index for similarity search (initialized at boot)
FAISS_INDEX: Optional[faiss.IndexFlatIP] = None

# Video UUID → embedding mapping (for taste vector building)
UUID_TO_EMBEDDING: dict[str, np.ndarray] = {}

# Video UUID → metadata (country_code, velocity_score)
UUID_TO_META: dict[str, dict] = {}

# FAISS index position → Video UUID mapping
INDEX_TO_UUID: list[str] = []

# User ID → taste vector mapping (updated incrementally)
USER_TASTE_VECTORS: dict[str, np.ndarray] = {}


# ==================== INITIALIZATION ====================


async def initialize_faiss():
    """
    Load all video embeddings from Supabase into RAM and build FAISS index.

    Called ONCE at server boot via main.py lifespan event.

    Steps:
    1. Fetch all video embeddings, country_code, velocity_score from database
    2. Normalize embeddings for cosine similarity (FAISS uses inner product)
    3. Build FAISS IndexFlatIP index (exact search, no approximation)
    4. Populate UUID → embedding and UUID → metadata dictionaries

    Memory footprint: ~100-150MB for 24K videos × 1024 dims
    Boot time: Expected 3-5 seconds depending on network latency
    """
    global FAISS_INDEX, UUID_TO_EMBEDDING, UUID_TO_META, INDEX_TO_UUID

    from app.db import get_video_embeddings_for_boot
    import json

    print("[FAISS] Loading embeddings from database...")
    videos = await get_video_embeddings_for_boot(limit=50000)

    if not videos:
        raise RuntimeError("No videos found for FAISS initialization")

    print(f"[FAISS] Fetched {len(videos)} videos, building index...")

    # Build FAISS index incrementally to reduce peak RAM during boot.
    faiss_index: Optional[faiss.IndexFlatIP] = None
    pending_embeddings: list[np.ndarray] = []
    pending_batch_size = 1024
    dimension: Optional[int] = None
    valid_count = 0

    for video in videos:
        try:
            uuid_str = str(video['id'])

            # Parse embedding (may be JSON string or list)
            embedding = video.get('embedding')
            if embedding is None:
                continue

            if isinstance(embedding, str):
                embedding = json.loads(embedding)

            embedding = np.array(embedding, dtype=np.float32)

            # Validate dimension
            if embedding.shape[0] != 1024:
                print(f"[FAISS WARNING] Video {uuid_str} has wrong embedding dimension: {embedding.shape[0]}")
                continue

            # Normalize for cosine similarity (IndexFlatIP uses dot product)
            norm = np.linalg.norm(embedding)
            if norm < 1e-10:
                print(f"[FAISS WARNING] Video {uuid_str} has zero-norm embedding")
                continue

            embedding = embedding / norm

            if faiss_index is None:
                dimension = embedding.shape[0]
                faiss_index = faiss.IndexFlatIP(dimension)

            pending_embeddings.append(embedding)
            if len(pending_embeddings) >= pending_batch_size:
                faiss_index.add(np.vstack(pending_embeddings).astype('float32'))
                pending_embeddings.clear()

            UUID_TO_EMBEDDING[uuid_str] = embedding
            UUID_TO_META[uuid_str] = {
                'country_code': video.get('country_code', 'US'),
                'velocity_score': float(video.get('velocity_score', 0.0))
            }
            INDEX_TO_UUID.append(uuid_str)
            valid_count += 1

        except Exception as e:
            print(f"[FAISS WARNING] Failed to parse video {video.get('id')}: {e}")
            continue

    if valid_count == 0:
        raise RuntimeError("No valid embeddings found")

    # Flush any remaining normalized vectors.
    if pending_embeddings:
        faiss_index.add(np.vstack(pending_embeddings).astype('float32'))
        pending_embeddings.clear()

    FAISS_INDEX = faiss_index

    # Approximate memory used by stored float32 vectors in index.
    memory_mb = (valid_count * (dimension or 0) * 4) / 1e6
    print(f"[FAISS] Index ready: {valid_count} videos, {dimension} dims, {memory_mb:.1f} MB")


# ==================== SIMILARITY SEARCH ====================


def search_similar(
    taste_vector: np.ndarray,
    k: int = 100,
    filter_country: Optional[str] = None
) -> list[tuple[str, float]]:
    """
    Fast similarity search using FAISS.

    Args:
        taste_vector: 1024-dim user taste vector (will be normalized)
        k: Number of results to return
        filter_country: Optional country code filter (e.g., "US", "GB")

    Returns:
        List of (video_uuid, similarity_score) tuples, ordered by similarity descending

    Performance: < 10ms for 24K videos
    """
    if FAISS_INDEX is None:
        raise RuntimeError("FAISS index not initialized. Call initialize_faiss() first.")

    # Normalize taste vector
    taste_vector = taste_vector.astype(np.float32)
    norm = np.linalg.norm(taste_vector)
    if norm < 1e-10:
        raise ValueError("Taste vector has zero norm")

    taste_vector = taste_vector / norm
    taste_vector = taste_vector.reshape(1, -1)

    # Over-fetch for filtering (if country filter specified)
    fetch_k = k * 5 if filter_country else k
    fetch_k = min(fetch_k, len(INDEX_TO_UUID))  # Don't exceed index size

    # Search FAISS (returns distances and indices)
    distances, indices = FAISS_INDEX.search(taste_vector, fetch_k)

    results = []
    for idx, score in zip(indices[0], distances[0]):
        if idx < 0 or idx >= len(INDEX_TO_UUID):
            continue

        uuid_str = INDEX_TO_UUID[idx]
        meta = UUID_TO_META.get(uuid_str)

        if not meta:
            continue

        # Apply country filter if specified
        if filter_country and meta['country_code'] != filter_country:
            continue

        results.append((uuid_str, float(score)))

        if len(results) >= k:
            break

    return results


# ==================== TASTE VECTOR MANAGEMENT ====================


def get_taste_vector(user_id: str) -> Optional[np.ndarray]:
    """
    Get cached taste vector for user.

    Returns:
        - Taste vector if cached (normalized 1024-dim ndarray)
        - None if not cached (need to build from watch history)
    """
    return USER_TASTE_VECTORS.get(user_id)


def set_taste_vector(user_id: str, taste_vector: np.ndarray):
    """
    Set taste vector for user (used during lazy rebuild from history).

    Args:
        user_id: User ID
        taste_vector: 1024-dim taste vector (will be normalized)
    """
    taste_vector = taste_vector.astype(np.float32)
    norm = np.linalg.norm(taste_vector)
    if norm > 1e-10:
        taste_vector = taste_vector / norm

    USER_TASTE_VECTORS[user_id] = taste_vector


def update_taste_vector(user_id: str, video_uuid: str) -> np.ndarray:
    """
    Incremental EMA (Exponential Moving Average) taste vector update.

    O(1) operation - no database fetch required.

    Formula:
        new_taste = (1 - α) * old_taste + α * new_embedding
        α = 0.15 (learning rate)

    Args:
        user_id: User ID
        video_uuid: Video UUID that was just watched

    Returns:
        Updated taste vector (normalized)

    Raises:
        ValueError: If video embedding not found
    """
    ALPHA = 0.15

    new_embedding = UUID_TO_EMBEDDING.get(video_uuid)
    if new_embedding is None:
        raise ValueError(f"Video {video_uuid} not found in embedding cache")

    old_taste = USER_TASTE_VECTORS.get(user_id)

    if old_taste is None:
        # First watch - initialize with this embedding
        USER_TASTE_VECTORS[user_id] = new_embedding.copy()
        return USER_TASTE_VECTORS[user_id]

    # EMA update
    updated = (1 - ALPHA) * old_taste + ALPHA * new_embedding

    # Normalize
    norm = np.linalg.norm(updated)
    if norm > 1e-10:
        updated = updated / norm

    USER_TASTE_VECTORS[user_id] = updated
    return updated


# ==================== TRENDING & METADATA ====================


def get_trending(country: Optional[str] = None, top_n: int = 100) -> list[str]:
    """
    Get top trending video UUIDs from in-memory metadata.

    Args:
        country: Optional country code filter
        top_n: Number of trending videos to return

    Returns:
        List of video UUIDs ordered by velocity_score descending

    Performance: < 5ms for full scan (24K videos)
    """
    candidates = [
        (uuid, meta['velocity_score'])
        for uuid, meta in UUID_TO_META.items()
        if country is None or meta['country_code'] == country
    ]

    # Sort by velocity_score descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    return [uuid for uuid, _ in candidates[:top_n]]


def get_video_metadata(uuid: str) -> Optional[dict]:
    """Get cached metadata for a video (country_code, velocity_score)."""
    return UUID_TO_META.get(uuid)


def get_country_affinity(taste_vector: np.ndarray, countries: list[str], top_k: int = 3) -> dict[str, float]:
    """
    Compute affinity scores for countries using numpy dot product.

    Replaces 9 separate database calls with in-memory computation.

    Args:
        taste_vector: User's 1024-dim taste vector (normalized)
        countries: List of candidate countries (e.g., ["US", "GB", "KR"])
        top_k: Number of top countries to return

    Returns:
        Dict of {country_code: affinity_score}, sorted by affinity descending

    Performance: < 5ms for computing affinity across all countries
    """
    # Normalize taste vector
    taste_vector = taste_vector.astype(np.float32)
    norm = np.linalg.norm(taste_vector)
    if norm < 1e-10:
        return {}
    taste_vector = taste_vector / norm

    affinity_scores = {}

    for country in countries:
        # Get all embeddings for this country
        country_embeddings = [
            UUID_TO_EMBEDDING[uuid]
            for uuid, meta in UUID_TO_META.items()
            if meta['country_code'] == country
        ]

        if not country_embeddings:
            affinity_scores[country] = 0.0
            continue

        # Compute mean similarity (embeddings already normalized)
        country_matrix = np.vstack(country_embeddings)
        similarities = np.dot(country_matrix, taste_vector)
        affinity_scores[country] = float(np.mean(similarities))

    # Sort by affinity descending and return top_k
    sorted_countries = sorted(affinity_scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_countries[:top_k])


# ==================== UTILITY FUNCTIONS ====================


def get_index_stats() -> dict:
    """Get FAISS index statistics for debugging/monitoring."""
    return {
        "index_initialized": FAISS_INDEX is not None,
        "total_videos": len(INDEX_TO_UUID),
        "cached_users": len(USER_TASTE_VECTORS),
        "memory_mb_videos": len(UUID_TO_EMBEDDING) * 1024 * 4 / 1e6,  # float32 = 4 bytes
        "memory_mb_users": len(USER_TASTE_VECTORS) * 1024 * 4 / 1e6
    }
