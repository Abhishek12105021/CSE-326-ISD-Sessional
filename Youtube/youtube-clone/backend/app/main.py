from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, feed, guest, search
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown tasks.

    Startup:
    - Initialize FAISS index with all video embeddings from database
    - Loads ~100-150MB into RAM for fast similarity search
    - Load sentence-transformer model for query embedding

    Shutdown:
    - Optional: Save user taste vectors to database (not implemented yet)
    """
    # Startup
    print("[BOOT] Initializing FAISS index...")
    from app.core import embedding_service, faiss_manager
    await faiss_manager.initialize_faiss()

    # Print stats
    stats = faiss_manager.get_index_stats()
    print(f"[BOOT] FAISS index ready: {stats['total_videos']} videos, {stats['memory_mb_videos']:.1f} MB")

    # Load embedding model for search/recommend endpoints
    print("[BOOT] Loading embedding model...")
    await embedding_service.load_model()

    yield

    # Shutdown
    print("[SHUTDOWN] Server stopping...")
    # TODO: Optional - save USER_TASTE_VECTORS to database for faster restart


app = FastAPI(
    title="YouTube Clone API",
    version="1.0.0",
    description="Backend API for YouTube Clone - Verifies Supabase Auth tokens",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(guest.router, prefix="/api/guest", tags=["Guest"])
app.include_router(feed.router, prefix="/api", tags=["Feed"])
app.include_router(search.router, prefix="/api", tags=["Search & Recommendations"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "auth_provider": "supabase"}
