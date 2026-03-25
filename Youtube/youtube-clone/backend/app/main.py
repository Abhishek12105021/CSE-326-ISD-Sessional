from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api.routes import auth, guest, feed

settings = get_settings()

app = FastAPI(
    title="YouTube Clone API",
    version="1.0.0",
    description="Backend API for YouTube Clone - Verifies Supabase Auth tokens"
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "auth_provider": "supabase"}
