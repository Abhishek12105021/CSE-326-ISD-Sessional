# Signup, Authentication & Login Implementation Plan (Revised)

## Overview

This document outlines the step-by-step implementation plan for adding authentication to the YouTube Clone application using **Supabase Auth** (native Google OAuth) with **FastAPI** as the application backend that verifies Supabase-issued tokens.

---

## Critical Design Decisions

### Why This Architecture?

| Concern | Previous Plan | Revised Plan |
|---------|---------------|--------------|
| **Auth Source** | Mixed (Supabase + Custom JWT) | Single source: **Supabase Auth only** |
| **Token Issuance** | FastAPI mints custom JWTs | Supabase issues JWTs; FastAPI only verifies |
| **Google OAuth** | Frontend `@react-oauth/google` → FastAPI | Frontend `supabase.auth.signInWithOAuth()` |
| **Refresh Tokens** | Custom table + hashing | Supabase handles automatically |
| **Incognito Detection** | `RequestFileSystem` API (deprecated) | Removed - browsers auto-isolate storage |
| **Guest Tracking** | Browser fingerprint (unreliable) | Explicit UUID in localStorage |

### User Types (Simplified)

| User Type | Description | Storage | Persistence |
|-----------|-------------|---------|-------------|
| **Guest** | Unauthenticated browsing | localStorage (`guest_id` UUID) | Until cleared |
| **Authenticated** | Signed in with Google | Supabase session (httpOnly cookie or localStorage) | Based on "Remember Me" |

> **Note:** "Incognito" is a browser mode, not a user type. Browsers already isolate private windows automatically. We don't need to detect or handle it specially.

---

## Architecture Diagram (Revised)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ AuthContext  │  │ SignInPage   │  │ GuestManager │  │ Navbar       │    │
│  │ (Supabase)   │  │ (Google)     │  │ (UUID)       │  │ (User Menu)  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│         │                  │                │                 │            │
│         └──────────────────┴────────────────┴─────────────────┘            │
│                                     │                                       │
│                    supabase.auth.signInWithOAuth({provider: 'google'})     │
│                                     │                                       │
│                          ┌──────────┴──────────┐                           │
│                          │  Supabase JS Client │                           │
│                          │  (Session Manager)  │                           │
│                          └──────────┬──────────┘                           │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                          Supabase Access Token (JWT)
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BACKEND (FastAPI)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      JWT Verification Middleware                      │  │
│  │            Verifies Supabase JWT using SUPABASE_JWT_SECRET           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         │                  │                │                 │            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ /api/profile │  │ /api/feed    │  │ /api/        │  │ /api/guest/  │    │
│  │              │  │              │  │ interactions │  │ migrate      │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                          Service Role Key (backend only)
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SUPABASE (BaaS)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Supabase     │  │  PostgreSQL  │  │   Row Level  │  │  Realtime    │    │
│  │  Auth        │  │   + pgvector │  │   Security   │  │  (optional)  │    │
│  │ (Google)     │  │   Database   │  │   (RLS)      │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# PHASE 1: SUPABASE PROJECT SETUP

## Step 1.1: Create Supabase Project

### Prerequisites
- Supabase account (free tier works)
- Access to Google Cloud Console

### Tasks
1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note down the following credentials from **Project Settings > API**:
   - **Project URL**: `https://<project-ref>.supabase.co`
   - **Anon Key**: Public key for client-side Supabase JS
   - **Service Role Key**: Private key for FastAPI backend (keep secret!)
   - **JWT Secret**: Found in **Project Settings > API > JWT Settings** (for FastAPI verification)
3. Wait for the project to finish provisioning (~2 minutes)

### Expected Outcome
- Active Supabase project with PostgreSQL database ready
- All 4 credentials noted down

---

## Step 1.2: Configure Google OAuth Provider in Supabase

### Prerequisites
- Step 1.1 completed
- Google Cloud Console access

### Tasks

**In Google Cloud Console:**
1. Create a new project or use existing
2. Navigate to **APIs & Services > OAuth consent screen**
   - Configure consent screen (External for testing)
   - Add scopes: `email`, `profile`, `openid`
3. Navigate to **APIs & Services > Credentials**
4. Create **OAuth 2.0 Client ID** (Web Application)
5. Add authorized redirect URIs:
   - `https://<project-ref>.supabase.co/auth/v1/callback`
   - `http://localhost:5173` (for local dev - Supabase handles the redirect)
6. Copy **Client ID** and **Client Secret**

**In Supabase Dashboard:**
1. Go to **Authentication > Providers**
2. Find **Google** in the list and click to expand
3. Toggle **Enable Sign in with Google**
4. Paste **Client ID** and **Client Secret**
5. Save

### Expected Outcome
- Google OAuth provider enabled in Supabase
- OAuth consent screen configured
- Redirect URIs properly set up

---

## Step 1.3: Create Database Schema (Complete)

### Prerequisites
- Steps 1.1, 1.2 completed

### Tasks

Run the following SQL in **Supabase SQL Editor**:

```sql
-- ============================================================
-- ENABLE EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USERS TABLE (extends Supabase auth.users)
-- ============================================================
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,

    -- Region for Cold Start recommendations
    region TEXT DEFAULT 'US',
    country TEXT DEFAULT 'United States',
    language TEXT DEFAULT 'en',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ DEFAULT NOW(),

    is_active BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- USER PREFERENCES TABLE
-- ============================================================
CREATE TABLE public.user_preferences (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,

    -- Display preferences
    theme TEXT DEFAULT 'dark' CHECK (theme IN ('light', 'dark', 'system')),
    autoplay BOOLEAN DEFAULT TRUE,
    restricted_mode BOOLEAN DEFAULT FALSE,

    -- Cold start phase tracking
    interaction_count INTEGER DEFAULT 0,
    recommendation_phase TEXT DEFAULT 'cold_start'
        CHECK (recommendation_phase IN ('cold_start', 'warm_up', 'personalized')),

    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- GUEST SESSIONS TABLE (for unauthenticated users)
-- ============================================================
CREATE TABLE public.guest_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guest_uuid TEXT NOT NULL UNIQUE,

    -- Context for recommendations
    region TEXT,
    country TEXT,
    language TEXT DEFAULT 'en',
    device_type TEXT,

    -- Cold start tracking
    interaction_count INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),

    -- Optional: link to user after signup
    converted_to_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL
);

-- ============================================================
-- WATCH HISTORY TABLE
-- ============================================================
CREATE TABLE public.watch_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- User reference (nullable for guests)
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    guest_uuid TEXT,

    -- Video reference
    video_id TEXT NOT NULL,

    -- Watch metrics
    watch_duration_seconds INTEGER DEFAULT 0,
    video_duration_seconds INTEGER,
    watch_percentage DECIMAL(5,2),

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    CONSTRAINT watch_history_user_check CHECK (
        (user_id IS NOT NULL AND guest_uuid IS NULL) OR
        (user_id IS NULL AND guest_uuid IS NOT NULL)
    )
);

-- ============================================================
-- INTERACTIONS TABLE (for recommendation engine)
-- ============================================================
CREATE TABLE public.interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- User reference (nullable for guests)
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    guest_uuid TEXT,

    -- Video reference
    video_id TEXT NOT NULL,

    -- Interaction type
    interaction_type TEXT NOT NULL CHECK (
        interaction_type IN (
            'view',
            'like',
            'dislike',
            'share',
            'save',
            'subscribe',
            'comment',
            'click',
            'skip',
            'not_interested',
            'dont_recommend'
        )
    ),

    -- Engagement metrics
    engagement_score DECIMAL(5,2),
    dwell_time_seconds INTEGER,

    -- Context
    source TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT interactions_user_check CHECK (
        (user_id IS NOT NULL AND guest_uuid IS NULL) OR
        (user_id IS NULL AND guest_uuid IS NOT NULL)
    )
);

-- ============================================================
-- SUBSCRIPTIONS TABLE
-- ============================================================
CREATE TABLE public.subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    channel_id TEXT NOT NULL,

    notification_level TEXT DEFAULT 'personalized'
        CHECK (notification_level IN ('all', 'personalized', 'none')),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, channel_id)
);

-- ============================================================
-- LIKED VIDEOS TABLE
-- ============================================================
CREATE TABLE public.liked_videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,

    liked_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, video_id)
);

-- ============================================================
-- PLAYLISTS TABLE
-- ============================================================
CREATE TABLE public.playlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    title TEXT NOT NULL,
    description TEXT,
    visibility TEXT DEFAULT 'private' CHECK (visibility IN ('public', 'unlisted', 'private')),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- PLAYLIST ITEMS TABLE
-- ============================================================
CREATE TABLE public.playlist_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    playlist_id UUID NOT NULL REFERENCES public.playlists(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,

    position INTEGER NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(playlist_id, video_id)
);

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================
CREATE INDEX idx_users_region ON public.users(region);
CREATE INDEX idx_users_last_login ON public.users(last_login_at);

CREATE INDEX idx_guest_sessions_uuid ON public.guest_sessions(guest_uuid);
CREATE INDEX idx_guest_sessions_active ON public.guest_sessions(last_active_at);

CREATE INDEX idx_watch_history_user ON public.watch_history(user_id);
CREATE INDEX idx_watch_history_guest ON public.watch_history(guest_uuid);
CREATE INDEX idx_watch_history_video ON public.watch_history(video_id);
CREATE INDEX idx_watch_history_started ON public.watch_history(started_at DESC);

CREATE INDEX idx_interactions_user ON public.interactions(user_id);
CREATE INDEX idx_interactions_guest ON public.interactions(guest_uuid);
CREATE INDEX idx_interactions_video ON public.interactions(video_id);
CREATE INDEX idx_interactions_type ON public.interactions(interaction_type);
CREATE INDEX idx_interactions_created ON public.interactions(created_at DESC);
CREATE INDEX idx_interactions_user_recent ON public.interactions(user_id, created_at DESC);

CREATE INDEX idx_subscriptions_user ON public.subscriptions(user_id);
CREATE INDEX idx_subscriptions_channel ON public.subscriptions(channel_id);

CREATE INDEX idx_liked_videos_user ON public.liked_videos(user_id);

CREATE INDEX idx_playlists_user ON public.playlists(user_id);
CREATE INDEX idx_playlist_items_playlist ON public.playlist_items(playlist_id);

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.guest_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.watch_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.liked_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.playlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.playlist_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" ON public.users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.users
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view own preferences" ON public.user_preferences
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own preferences" ON public.user_preferences
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own preferences" ON public.user_preferences
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own watch history" ON public.watch_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own watch history" ON public.watch_history
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own watch history" ON public.watch_history
    FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own interactions" ON public.interactions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own interactions" ON public.interactions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own subscriptions" ON public.subscriptions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own subscriptions" ON public.subscriptions
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own liked videos" ON public.liked_videos
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own liked videos" ON public.liked_videos
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own playlists" ON public.playlists
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own playlists" ON public.playlists
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Anyone can view public playlists" ON public.playlists
    FOR SELECT USING (visibility = 'public');

CREATE POLICY "Users can view own playlist items" ON public.playlist_items
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.playlists
            WHERE playlists.id = playlist_items.playlist_id
              AND playlists.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can manage own playlist items" ON public.playlist_items
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.playlists
            WHERE playlists.id = playlist_items.playlist_id
              AND playlists.user_id = auth.uid()
        )
    );

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    user_region TEXT;
BEGIN
    user_region := COALESCE(
        NEW.raw_user_meta_data->>'region',
        'US'
    );

    INSERT INTO public.users (id, email, display_name, avatar_url, region)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(
            NEW.raw_user_meta_data->>'full_name',
            NEW.raw_user_meta_data->>'name',
            split_part(NEW.email, '@', 1)
        ),
        NEW.raw_user_meta_data->>'avatar_url',
        user_region
    );

    INSERT INTO public.user_preferences (user_id)
    VALUES (NEW.id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_users_timestamp ON public.users;
CREATE TRIGGER update_users_timestamp
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS update_preferences_timestamp ON public.user_preferences;
CREATE TRIGGER update_preferences_timestamp
    BEFORE UPDATE ON public.user_preferences
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS update_playlists_timestamp ON public.playlists;
CREATE TRIGGER update_playlists_timestamp
    BEFORE UPDATE ON public.playlists
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE OR REPLACE FUNCTION public.update_interaction_count()
RETURNS TRIGGER AS $$
DECLARE
    current_count INTEGER;
    new_phase TEXT;
BEGIN
    IF NEW.user_id IS NOT NULL THEN
        UPDATE public.user_preferences
        SET interaction_count = interaction_count + 1
        WHERE user_id = NEW.user_id
        RETURNING interaction_count INTO current_count;

        IF current_count >= 5 THEN
            new_phase := 'personalized';
        ELSIF current_count >= 1 THEN
            new_phase := 'warm_up';
        ELSE
            new_phase := 'cold_start';
        END IF;

        UPDATE public.user_preferences
        SET recommendation_phase = new_phase
        WHERE user_id = NEW.user_id
          AND recommendation_phase != new_phase;

    ELSIF NEW.guest_uuid IS NOT NULL THEN
        UPDATE public.guest_sessions
        SET
            interaction_count = interaction_count + 1,
            last_active_at = NOW()
        WHERE guest_uuid = NEW.guest_uuid;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_interaction_created ON public.interactions;
CREATE TRIGGER on_interaction_created
    AFTER INSERT ON public.interactions
    FOR EACH ROW EXECUTE FUNCTION public.update_interaction_count();

CREATE OR REPLACE FUNCTION public.migrate_guest_to_user(
    p_guest_uuid TEXT,
    p_user_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE public.watch_history
    SET user_id = p_user_id, guest_uuid = NULL
    WHERE guest_uuid = p_guest_uuid;

    UPDATE public.interactions
    SET user_id = p_user_id, guest_uuid = NULL
    WHERE guest_uuid = p_guest_uuid;

    UPDATE public.guest_sessions
    SET converted_to_user_id = p_user_id
    WHERE guest_uuid = p_guest_uuid;

    UPDATE public.user_preferences
    SET interaction_count = (
        SELECT COUNT(*) FROM public.interactions WHERE user_id = p_user_id
    )
    WHERE user_id = p_user_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### Expected Outcome
- Complete database schema with all tables for auth + recommendation engine
- `users`, `user_preferences`, `guest_sessions` for identity
- `watch_history`, `interactions`, `subscriptions`, `liked_videos` for recommendations
- `playlists`, `playlist_items` for user collections
- Full RLS policies for client-side security
- Auto-triggers for user creation, interaction counting, and phase transitions
- Guest-to-user migration function

---

# PHASE 2: FASTAPI BACKEND SETUP

## Step 2.1: Initialize FastAPI Project

### Prerequisites
- Python 3.10+ installed
- pip or poetry package manager

### Tasks

1. **Create backend directory structure:**
```
youtube-clone/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   └── guest.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── supabase.py
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── auth.py
│   ├── requirements.txt
│   ├── .env
│   └── .env.example
└── src/  (existing frontend)
```

2. **Create `requirements.txt`:**
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
supabase==2.3.0
python-jose[cryptography]==3.3.0
httpx==0.26.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-multipart==0.0.6
```

3. **Create `.env.example`:**
```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_JWT_SECRET=your-jwt-secret

# CORS
FRONTEND_URL=http://localhost:5173
```

> **Note:** No custom JWT secrets needed - we verify Supabase's JWTs directly.

4. **Install dependencies:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Expected Outcome
- Backend project structure created
- All dependencies installed
- Environment variables template ready

---

## Step 2.2: Implement Core Configuration

### Prerequisites
- Step 2.1 completed

### Tasks

1. **Create `app/config.py`:**
```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    supabase_jwt_secret: str  # For verifying Supabase JWTs

    # CORS
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

2. **Create `app/core/supabase.py`:**
```python
from supabase import create_client, Client
from app.config import get_settings

settings = get_settings()

# Service role client for backend operations (bypasses RLS)
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_key
)

def get_supabase_admin() -> Client:
    """Get Supabase client with service role (bypasses RLS)."""
    return supabase_admin
```

3. **Create `app/main.py`:**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api.routes import auth, guest

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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "auth_provider": "supabase"}
```

### Expected Outcome
- Configuration management with Pydantic settings
- Supabase admin client initialization
- FastAPI app with CORS configured

---

## Step 2.3: Implement Auth Schemas

### Prerequisites
- Step 2.2 completed

### Tasks

**Create `app/schemas/auth.py`:**
```python
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    """User profile response."""
    user_id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    region: Optional[str] = None
    created_at: datetime


class UserPreferences(BaseModel):
    """User preferences."""
    theme: str = "dark"
    autoplay: bool = True
    restricted_mode: bool = False
    interaction_count: int = 0
    recommendation_phase: str = "cold_start"


class UpdateProfileRequest(BaseModel):
    """Request to update profile."""
    display_name: Optional[str] = None
    region: Optional[str] = None
    language: Optional[str] = None


class UpdatePreferencesRequest(BaseModel):
    """Request to update preferences."""
    theme: Optional[str] = None
    autoplay: Optional[bool] = None
    restricted_mode: Optional[bool] = None


class GuestSessionRequest(BaseModel):
    """Request to create guest session."""
    guest_uuid: str
    region: Optional[str] = None
    language: Optional[str] = None
    device_type: Optional[str] = None


class GuestSessionResponse(BaseModel):
    """Guest session response."""
    guest_uuid: str
    interaction_count: int = 0
    created_at: datetime


class MigrateGuestRequest(BaseModel):
    """Request to migrate guest data to user account."""
    guest_uuid: str


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True
```

### Expected Outcome
- Pydantic schemas for all auth-related requests/responses
- Type validation and serialization configured

---

## Step 2.4: Implement Auth Dependencies (Supabase JWT Verification)

### Prerequisites
- Step 2.3 completed

### Tasks

**Create `app/api/deps.py`:**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional
from app.config import get_settings
from app.core.supabase import get_supabase_admin

settings = get_settings()
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def verify_supabase_token(token: str) -> dict:
    """
    Verify a Supabase-issued JWT token.
    Returns the decoded payload if valid.
    """
    try:
        # Supabase uses HS256 with the JWT secret
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get current authenticated user.
    Verifies Supabase JWT and fetches user profile.
    """
    payload = verify_supabase_token(credentials.credentials)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Fetch user profile from database
    supabase = get_supabase_admin()
    result = supabase.table("users").select("*").eq("id", user_id).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return result.data


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(optional_security)
) -> Optional[dict]:
    """
    Dependency to optionally get current user.
    Returns None for unauthenticated requests (guest access).
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
```

### Expected Outcome
- `get_current_user` dependency verifies Supabase JWTs
- `get_optional_user` supports both authenticated and guest access
- No custom JWT issuance - pure verification

---

## Step 2.5: Implement Auth Routes

### Prerequisites
- Step 2.4 completed

### Tasks

**Create `app/api/routes/auth.py`:**
```python
from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime
from app.schemas.auth import (
    UserProfile,
    UserPreferences,
    UpdateProfileRequest,
    UpdatePreferencesRequest,
    MigrateGuestRequest,
    MessageResponse
)
from app.core.supabase import get_supabase_admin
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current user's profile.
    Token is verified by Supabase - this just fetches the profile data.
    """
    return UserProfile(
        user_id=current_user["id"],
        email=current_user["email"],
        display_name=current_user.get("display_name"),
        avatar_url=current_user.get("avatar_url"),
        region=current_user.get("region"),
        created_at=current_user["created_at"]
    )


@router.put("/profile", response_model=UserProfile)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's profile."""
    supabase = get_supabase_admin()

    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_data["updated_at"] = datetime.utcnow().isoformat()

    result = supabase.table("users").update(update_data).eq(
        "id", current_user["id"]
    ).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

    updated = result.data[0]
    return UserProfile(
        user_id=updated["id"],
        email=updated["email"],
        display_name=updated.get("display_name"),
        avatar_url=updated.get("avatar_url"),
        region=updated.get("region"),
        created_at=updated["created_at"]
    )


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(current_user: dict = Depends(get_current_user)):
    """Get current user's preferences."""
    supabase = get_supabase_admin()

    result = supabase.table("user_preferences").select("*").eq(
        "user_id", current_user["id"]
    ).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found"
        )

    return UserPreferences(**result.data)


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(
    request: UpdatePreferencesRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's preferences."""
    supabase = get_supabase_admin()

    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_data["updated_at"] = datetime.utcnow().isoformat()

    result = supabase.table("user_preferences").update(update_data).eq(
        "user_id", current_user["id"]
    ).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )

    return UserPreferences(**result.data[0])


@router.post("/migrate-guest", response_model=MessageResponse)
async def migrate_guest_data(
    request: MigrateGuestRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Migrate guest session data to authenticated user.
    Call this after a guest user signs up to preserve their history.
    """
    supabase = get_supabase_admin()

    # Check if guest session exists
    guest_result = supabase.table("guest_sessions").select("*").eq(
        "guest_uuid", request.guest_uuid
    ).single().execute()

    if not guest_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    if guest_result.data.get("converted_to_user_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guest session already migrated"
        )

    # Call migration function
    result = supabase.rpc(
        "migrate_guest_to_user",
        {"p_guest_uuid": request.guest_uuid, "p_user_id": current_user["id"]}
    ).execute()

    return MessageResponse(
        message=f"Successfully migrated guest data to user {current_user['id']}",
        success=True
    )


@router.post("/logout", response_model=MessageResponse)
async def logout_current_session(current_user: dict = Depends(get_current_user)):
    """
    Logout current session.
    Note: Actual session invalidation is handled by Supabase on the frontend.
    This endpoint can be used for logging/analytics.
    """
    supabase = get_supabase_admin()

    # Update last login timestamp
    supabase.table("users").update({
        "last_login_at": datetime.utcnow().isoformat()
    }).eq("id", current_user["id"]).execute()

    return MessageResponse(message="Logged out successfully")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_sessions(current_user: dict = Depends(get_current_user)):
    """
    Logout all sessions for the current user.
    Note: This signals intent - frontend should call supabase.auth.signOut({ scope: 'global' })
    """
    # This is primarily for audit logging
    # Actual global signout is handled client-side via Supabase
    return MessageResponse(
        message="All sessions marked for logout. Frontend should call supabase.auth.signOut({ scope: 'global' })"
    )
```

### Expected Outcome
- `/api/auth/profile` - Get/update user profile
- `/api/auth/preferences` - Get/update user preferences
- `/api/auth/migrate-guest` - Migrate guest data after signup
- `/api/auth/logout` - Logout current session
- `/api/auth/logout-all` - Logout all sessions (signals intent)

---

## Step 2.6: Implement Guest Routes

### Prerequisites
- Step 2.5 completed

### Tasks

**Create `app/api/routes/guest.py`:**
```python
from fastapi import APIRouter, HTTPException, status
from datetime import datetime
from app.schemas.auth import (
    GuestSessionRequest,
    GuestSessionResponse,
    MessageResponse
)
from app.core.supabase import get_supabase_admin

router = APIRouter()


@router.post("/session", response_model=GuestSessionResponse)
async def create_guest_session(request: GuestSessionRequest):
    """
    Create or update a guest session.
    Called when an unauthenticated user visits the site.
    """
    supabase = get_supabase_admin()

    # Check if guest session already exists
    existing = supabase.table("guest_sessions").select("*").eq(
        "guest_uuid", request.guest_uuid
    ).execute()

    if existing.data:
        # Update existing session
        result = supabase.table("guest_sessions").update({
            "last_active_at": datetime.utcnow().isoformat(),
            "region": request.region or existing.data[0].get("region"),
            "device_type": request.device_type or existing.data[0].get("device_type"),
        }).eq("guest_uuid", request.guest_uuid).execute()

        session = result.data[0]
    else:
        # Create new session
        result = supabase.table("guest_sessions").insert({
            "guest_uuid": request.guest_uuid,
            "region": request.region,
            "language": request.language or "en",
            "device_type": request.device_type,
        }).execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create guest session"
            )

        session = result.data[0]

    return GuestSessionResponse(
        guest_uuid=session["guest_uuid"],
        interaction_count=session.get("interaction_count", 0),
        created_at=session["created_at"]
    )


@router.get("/session/{guest_uuid}", response_model=GuestSessionResponse)
async def get_guest_session(guest_uuid: str):
    """Get guest session info."""
    supabase = get_supabase_admin()

    result = supabase.table("guest_sessions").select("*").eq(
        "guest_uuid", guest_uuid
    ).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    return GuestSessionResponse(
        guest_uuid=result.data["guest_uuid"],
        interaction_count=result.data.get("interaction_count", 0),
        created_at=result.data["created_at"]
    )


@router.delete("/session/{guest_uuid}", response_model=MessageResponse)
async def delete_guest_session(guest_uuid: str):
    """
    Delete guest session and all associated data.
    Use when user explicitly clears data or after migration.
    """
    supabase = get_supabase_admin()

    # Delete interactions
    supabase.table("interactions").delete().eq("guest_uuid", guest_uuid).execute()

    # Delete watch history
    supabase.table("watch_history").delete().eq("guest_uuid", guest_uuid).execute()

    # Delete guest session
    supabase.table("guest_sessions").delete().eq("guest_uuid", guest_uuid).execute()

    return MessageResponse(message="Guest session deleted successfully")
```

### Expected Outcome
- `/api/guest/session` - Create/update guest session
- `/api/guest/session/{uuid}` - Get guest session info
- `/api/guest/session/{uuid}` (DELETE) - Delete guest data

---

# PHASE 3: FRONTEND INTEGRATION

## Step 3.1: Install Frontend Dependencies

### Prerequisites
- Phase 2 completed
- Existing React frontend

### Tasks

```bash
cd youtube-clone
npm install @supabase/supabase-js
```

> **Note:** We use Supabase JS client directly - no need for `@react-oauth/google`.

### Expected Outcome
- Supabase JS client library installed

---

## Step 3.2: Create Supabase Client

### Prerequisites
- Step 3.1 completed

### Tasks

**Create `src/lib/supabase.js`:**
```javascript
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,  // Uses localStorage by default
    detectSessionInUrl: true,  // For OAuth redirect handling
  },
});
```

### Expected Outcome
- Supabase client configured with auto refresh and session persistence

---

## Step 3.3: Create Auth Context

### Prerequisites
- Step 3.2 completed

### Tasks

**Create `src/context/AuthContext.jsx`:**
```jsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { supabase } from '../lib/supabase';

const AuthContext = createContext(null);

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Guest UUID management
const GuestManager = {
  STORAGE_KEY: 'youtube_clone_guest_id',

  getGuestId() {
    let guestId = localStorage.getItem(this.STORAGE_KEY);
    if (!guestId) {
      guestId = crypto.randomUUID();
      localStorage.setItem(this.STORAGE_KEY, guestId);
    }
    return guestId;
  },

  clearGuestId() {
    localStorage.removeItem(this.STORAGE_KEY);
  },

  hasGuestId() {
    return !!localStorage.getItem(this.STORAGE_KEY);
  },
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [guestId, setGuestId] = useState(null);

  // Initialize auth state
  useEffect(() => {
    // Check for existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);

      // If no authenticated user, get/create guest ID
      if (!session?.user) {
        setGuestId(GuestManager.getGuestId());
      }

      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        setSession(session);
        setUser(session?.user ?? null);

        if (event === 'SIGNED_IN' && session?.user) {
          // Clear guest ID on sign in
          const previousGuestId = GuestManager.getGuestId();

          // Migrate guest data if exists
          if (GuestManager.hasGuestId()) {
            try {
              await migrateGuestData(previousGuestId, session.access_token);
              GuestManager.clearGuestId();
            } catch (error) {
              console.error('Guest migration failed:', error);
            }
          }

          setGuestId(null);
        } else if (event === 'SIGNED_OUT') {
          // Create new guest ID on sign out
          setGuestId(GuestManager.getGuestId());
        }
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  // API helper with auth
  const authFetch = useCallback(async (endpoint, options = {}) => {
    const accessToken = session?.access_token;

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
        ...options.headers,
      },
    });

    return response;
  }, [session]);

  // Migrate guest data to user account
  const migrateGuestData = async (guestUuid, accessToken) => {
    const response = await fetch(`${API_BASE_URL}/api/auth/migrate-guest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ guest_uuid: guestUuid }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Migration failed');
    }

    return response.json();
  };

  // Sign in with Google
  const signInWithGoogle = async (options = {}) => {
    const { rememberMe = true } = options;

    // If user doesn't want to be remembered, we'll handle logout differently
    // Supabase always persists by default, but we can manually clear on tab close

    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}`,
        queryParams: {
          access_type: 'offline',
          prompt: 'consent',
        },
      },
    });

    if (error) {
      console.error('Google sign in error:', error);
      return { success: false, error: error.message };
    }

    return { success: true, data };
  };

  // Sign out
  const signOut = async (scope = 'local') => {
    const { error } = await supabase.auth.signOut({ scope });

    if (error) {
      console.error('Sign out error:', error);
      return { success: false, error: error.message };
    }

    return { success: true };
  };

  // Sign out from all devices
  const signOutAll = async () => {
    return signOut('global');
  };

  // Get user profile from backend
  const getProfile = async () => {
    const response = await authFetch('/api/auth/profile');
    if (response.ok) {
      return response.json();
    }
    throw new Error('Failed to fetch profile');
  };

  // Update user profile
  const updateProfile = async (updates) => {
    const response = await authFetch('/api/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
    if (response.ok) {
      return response.json();
    }
    throw new Error('Failed to update profile');
  };

  const value = {
    // State
    user,
    session,
    loading,
    isAuthenticated: !!user,
    guestId,

    // Auth methods
    signInWithGoogle,
    signOut,
    signOutAll,

    // Profile methods
    getProfile,
    updateProfile,

    // API helper
    authFetch,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

### Expected Outcome
- Auth context using Supabase native auth
- Automatic session management
- Guest UUID tracking with migration on signup
- API helper that attaches Supabase tokens

---

## Step 3.4: Create Sign In Page

### Prerequisites
- Step 3.3 completed

### Tasks

**Create `src/pages/SignIn/SignIn.jsx`:**
```jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './SignIn.css';

function SignIn() {
  const navigate = useNavigate();
  const { signInWithGoogle, isAuthenticated, loading } = useAuth();
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState(null);
  const [isSigningIn, setIsSigningIn] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (!loading && isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, loading, navigate]);

  const handleGoogleSignIn = async () => {
    setError(null);
    setIsSigningIn(true);

    const result = await signInWithGoogle({ rememberMe });

    if (!result.success) {
      setError(result.error);
      setIsSigningIn(false);
    }
    // On success, Supabase redirects to Google and back
  };

  if (loading) {
    return (
      <div className="signin-container">
        <div className="signin-card">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="signin-container">
      <div className="signin-card">
        <div className="signin-header">
          <svg className="youtube-logo" viewBox="0 0 90 20" preserveAspectRatio="xMidYMid meet">
            <g>
              <path d="M27.9727 3.12324C27.6435 1.89323 26.6768 0.926623 25.4468 0.597366C23.2197 2.24288e-07 14.285 0 14.285 0C14.285 0 5.35042 2.24288e-07 3.12323 0.597366C1.89323 0.926623 0.926623 1.89323 0.597366 3.12324C2.24288e-07 5.35042 0 10 0 10C0 10 2.24288e-07 14.6496 0.597366 16.8768C0.926623 18.1068 1.89323 19.0734 3.12323 19.4026C5.35042 20 14.285 20 14.285 20C14.285 20 23.2197 20 25.4468 19.4026C26.6768 19.0734 27.6435 18.1068 27.9727 16.8768C28.5701 14.6496 28.5701 10 28.5701 10C28.5701 10 28.5677 5.35042 27.9727 3.12324Z" fill="#FF0000"/>
              <path d="M11.4253 14.2854L18.8477 10.0004L11.4253 5.71533V14.2854Z" fill="white"/>
            </g>
            <g>
              <path d="M34.6024 19.4043L35.8917 3.34314H39.3481L40.6374 19.4043H38.4008L38.1989 15.7162H37.0413L36.8394 19.4043H34.6024ZM37.1878 13.6867L37.6201 6.57647L38.054 13.6867H37.1878Z" fill="white"/>
              <path d="M41.4697 19.4043V3.34314H45.1077V8.45486H46.3436V3.34314H49.9816V19.4043H46.3436V11.6115H45.1077V19.4043H41.4697Z" fill="white"/>
              <path d="M53.4997 19.4043V6.50034H51.2627V3.34314H59.3747V6.50034H57.1377V19.4043H53.4997Z" fill="white"/>
              <path d="M60.1401 19.4043V3.34314H63.7781V10.6468L65.7841 3.34314H69.4221L67.0031 11.9628L69.4221 19.4043H65.7841L63.7781 12.7831V19.4043H60.1401Z" fill="white"/>
            </g>
          </svg>
          <h1>Sign in</h1>
          <p>to continue to YouTube</p>
        </div>

        {error && (
          <div className="signin-error">
            {error}
          </div>
        )}

        <div className="signin-options">
          <button
            className="google-signin-btn"
            onClick={handleGoogleSignIn}
            disabled={isSigningIn}
          >
            <svg className="google-icon" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            {isSigningIn ? 'Signing in...' : 'Continue with Google'}
          </button>

          <label className="remember-me">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
            />
            <span>Remember me on this device</span>
          </label>
        </div>

        <div className="signin-footer">
          <p>
            By signing in, you agree to our{' '}
            <a href="/terms">Terms of Service</a> and{' '}
            <a href="/privacy">Privacy Policy</a>.
          </p>
        </div>
      </div>
    </div>
  );
}

export default SignIn;
```

**Create `src/pages/SignIn/SignIn.css`:**
```css
.signin-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #0f0f0f;
  padding: 20px;
}

.signin-card {
  background: #212121;
  border-radius: 8px;
  padding: 48px;
  max-width: 400px;
  width: 100%;
  text-align: center;
}

.signin-header {
  margin-bottom: 32px;
}

.youtube-logo {
  width: 90px;
  height: 20px;
  margin-bottom: 24px;
}

.signin-header h1 {
  color: #fff;
  font-size: 24px;
  font-weight: 400;
  margin: 0 0 8px;
}

.signin-header p {
  color: #aaa;
  font-size: 16px;
  margin: 0;
}

.signin-error {
  background: #5c2828;
  color: #f88;
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 16px;
  font-size: 14px;
}

.signin-options {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.google-signin-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
  max-width: 300px;
  padding: 12px 24px;
  background: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  color: #3c4043;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
}

.google-signin-btn:hover:not(:disabled) {
  background: #f8f9fa;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.google-signin-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.google-icon {
  width: 18px;
  height: 18px;
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #aaa;
  font-size: 14px;
  cursor: pointer;
}

.remember-me input {
  accent-color: #3ea6ff;
}

.signin-footer {
  margin-top: 32px;
  font-size: 12px;
  color: #717171;
}

.signin-footer a {
  color: #3ea6ff;
  text-decoration: none;
}

.signin-footer a:hover {
  text-decoration: underline;
}
```

### Expected Outcome
- Sign in page with Google OAuth button
- "Remember me" checkbox option
- YouTube-style dark theme design
- Proper redirect after authentication

---

## Step 3.5: Update Navbar for Auth

### Prerequisites
- Step 3.4 completed

### Tasks

**Update `src/components/Navbar/Navbar.jsx`** - Add these imports and auth integration:

```jsx
// Add to existing imports
import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FaUserCircle } from 'react-icons/fa';
import { useAuth } from '../../context/AuthContext';

// Inside the component function, add:
function Navbar({ onMenuClick }) {
  const navigate = useNavigate();
  const { user, isAuthenticated, signOut, loading } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);

  // Close menu on click outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSignOut = async () => {
    await signOut();
    setShowUserMenu(false);
    navigate('/');
  };

  // ... existing code ...

  // Replace the user avatar/sign-in section in JSX with:
  return (
    // ... existing navbar structure ...
    <div className="navbar-right">
      {/* ... existing buttons ... */}

      {loading ? (
        <div className="user-loading" />
      ) : isAuthenticated ? (
        <div className="user-menu-container" ref={userMenuRef}>
          <button
            className="user-avatar-btn"
            onClick={() => setShowUserMenu(!showUserMenu)}
            aria-label="Account menu"
          >
            <img
              src={user?.user_metadata?.avatar_url || `https://ui-avatars.com/api/?name=${user?.email || 'User'}&background=random`}
              alt="User avatar"
              className="user-avatar"
            />
          </button>

          {showUserMenu && (
            <div className="user-dropdown">
              <div className="user-info">
                <img
                  src={user?.user_metadata?.avatar_url || `https://ui-avatars.com/api/?name=${user?.email || 'User'}&background=random`}
                  alt=""
                  className="dropdown-avatar"
                />
                <div className="user-details">
                  <p className="user-name">
                    {user?.user_metadata?.full_name || user?.email?.split('@')[0]}
                  </p>
                  <p className="user-email">{user?.email}</p>
                </div>
              </div>

              <div className="dropdown-divider" />

              <button onClick={() => { navigate('/channel/mine'); setShowUserMenu(false); }}>
                Your channel
              </button>
              <button onClick={() => { navigate('/settings'); setShowUserMenu(false); }}>
                Settings
              </button>

              <div className="dropdown-divider" />

              <button onClick={handleSignOut}>
                Sign out
              </button>
            </div>
          )}
        </div>
      ) : (
        <Link to="/signin" className="sign-in-btn">
          <FaUserCircle size={24} />
          <span>Sign in</span>
        </Link>
      )}
    </div>
  );
}
```

**Add to `src/components/Navbar/Navbar.css`:**
```css
/* User Menu Styles */
.user-menu-container {
  position: relative;
}

.user-avatar-btn {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  border-radius: 50%;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}

.user-loading {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #383838;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.user-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: #282828;
  border-radius: 12px;
  min-width: 280px;
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.4);
  z-index: 1000;
  overflow: hidden;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
}

.dropdown-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

.user-details {
  flex: 1;
  min-width: 0;
}

.user-name {
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-email {
  color: #aaa;
  font-size: 14px;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-divider {
  height: 1px;
  background: #383838;
  margin: 0;
}

.user-dropdown button {
  display: block;
  width: 100%;
  padding: 12px 16px;
  background: none;
  border: none;
  color: #f1f1f1;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s;
}

.user-dropdown button:hover {
  background: #383838;
}

.sign-in-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #3ea6ff;
  border-radius: 18px;
  color: #3ea6ff;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.sign-in-btn:hover {
  background: rgba(62, 166, 255, 0.1);
}
```

### Expected Outcome
- Navbar shows user avatar when logged in
- Dropdown menu with profile, settings, and sign out
- Sign in button when not authenticated
- Loading state while checking auth

---

## Step 3.6: Update App.jsx Router

### Prerequisites
- Steps 3.3, 3.4, 3.5 completed

### Tasks

**Update `src/App.jsx`:**
```jsx
import { useState } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar/Navbar';
import Sidebar from './components/Sidebar/Sidebar';
import Home from './pages/Home/Home';
import VideoPlayer from './pages/VideoPlayer/VideoPlayer';
import Channel from './pages/Channel/Channel';
import Search from './pages/Search/Search';
import SignIn from './pages/SignIn/SignIn';
import './index.css';

// Protected route wrapper
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <div className="loading-screen">Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/signin" replace />;
  }

  return children;
}

// Main app layout
function AppLayout() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <>
      <Navbar onMenuClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)} />
      <div className="app-container">
        <Sidebar collapsed={isSidebarCollapsed} />
        <main className={`main-content ${isSidebarCollapsed ? 'expanded' : ''}`}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/video/:id" element={<VideoPlayer />} />
            <Route path="/channel/:channelId" element={<Channel />} />
            <Route path="/search" element={<Search />} />
            {/* Add more routes as needed */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <HashRouter>
        <Routes>
          {/* Sign in page (standalone layout) */}
          <Route path="/signin" element={<SignIn />} />

          {/* Main app with navbar/sidebar */}
          <Route path="/*" element={<AppLayout />} />
        </Routes>
      </HashRouter>
    </AuthProvider>
  );
}

export default App;
```

### Expected Outcome
- AuthProvider wraps the entire app
- Sign in page renders standalone (no navbar/sidebar)
- Main layout includes navbar and sidebar
- Protected route helper available for guarded pages

---

## Step 3.7: Add Environment Variables

### Prerequisites
- Step 3.6 completed

### Tasks

**Create `youtube-clone/.env`:**
```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000
```

**Update `.gitignore`:**
```
# Environment variables
.env
.env.local
.env.*.local
```

### Expected Outcome
- Frontend environment variables configured
- Sensitive keys excluded from version control

---

# PHASE 4: TESTING & INTEGRATION

## Step 4.1: Run Backend Server

### Prerequisites
- Phase 2 fully completed
- `.env` configured with real Supabase credentials

### Tasks

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

### Expected Outcome
- Backend running on `http://localhost:8000`
- Health check at `http://localhost:8000/health` returns `{"status": "healthy", "auth_provider": "supabase"}`
- API docs at `http://localhost:8000/docs`

---

## Step 4.2: Run Frontend Development Server

### Prerequisites
- Phase 3 fully completed
- Backend running

### Tasks

```bash
cd youtube-clone
npm run dev
```

### Expected Outcome
- Frontend running on `http://localhost:5173`
- Sign in page accessible at `http://localhost:5173/#/signin`

---

## Step 4.3: End-to-End Testing Checklist

### Prerequisites
- Steps 4.1, 4.2 completed

### Test Cases

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | **Guest Browsing** | Open app without signing in | Home feed loads, Sign in button visible, guest_id in localStorage |
| 2 | **Guest Session Created** | Check backend on guest visit | `guest_sessions` table has entry with guest_uuid |
| 3 | **Google Sign In** | Click Sign in → Google OAuth | Redirected to Google, then back to home with user avatar |
| 4 | **User Profile Created** | Check database | `users` and `user_preferences` tables have entries |
| 5 | **Guest Data Migrated** | Sign in after guest activity | `interactions` and `watch_history` migrated, `guest_sessions.converted_to_user_id` set |
| 6 | **Session Persistence** | Close tab, reopen | Still logged in (localStorage session) |
| 7 | **Incognito Isolation** | Login in incognito, close window | Session cleared (browser handles automatically) |
| 8 | **Token Auto-Refresh** | Wait for access token expiry | Supabase auto-refreshes, no logout |
| 9 | **Sign Out (Current)** | Click Sign out | Logged out, redirected to home, new guest_id created |
| 10 | **Sign Out (All Devices)** | Call signOutAll() | Session invalidated globally |
| 11 | **Protected API Route** | Access `/api/auth/profile` without token | Returns 401 Unauthorized |
| 12 | **Protected API with Token** | Access `/api/auth/profile` with token | Returns user profile |

### Expected Outcome
- All test cases pass
- Auth flow works correctly
- Guest data migration preserves recommendation history

---

# SUMMARY

## Implementation Checklist

| Phase | Step | Description | Status |
|-------|------|-------------|--------|
| **1** | 1.1 | Create Supabase Project | ⬜ |
| **1** | 1.2 | Configure Google OAuth in Supabase | ⬜ |
| **1** | 1.3 | Create Complete Database Schema | ⬜ |
| **2** | 2.1 | Initialize FastAPI Project | ⬜ |
| **2** | 2.2 | Implement Core Configuration | ⬜ |
| **2** | 2.3 | Implement Auth Schemas | ⬜ |
| **2** | 2.4 | Implement Auth Dependencies (JWT Verification) | ⬜ |
| **2** | 2.5 | Implement Auth Routes | ⬜ |
| **2** | 2.6 | Implement Guest Routes | ⬜ |
| **3** | 3.1 | Install Frontend Dependencies | ⬜ |
| **3** | 3.2 | Create Supabase Client | ⬜ |
| **3** | 3.3 | Create Auth Context | ⬜ |
| **3** | 3.4 | Create Sign In Page | ⬜ |
| **3** | 3.5 | Update Navbar for Auth | ⬜ |
| **3** | 3.6 | Update App.jsx Router | ⬜ |
| **3** | 3.7 | Add Environment Variables | ⬜ |
| **4** | 4.1 | Run Backend Server | ⬜ |
| **4** | 4.2 | Run Frontend Server | ⬜ |
| **4** | 4.3 | End-to-End Testing | ⬜ |

## Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Auth Provider** | Supabase Auth (native) | Single source of truth, handles OAuth complexity |
| **Token Issuance** | Supabase only | FastAPI only verifies, no dual JWT systems |
| **Incognito Detection** | Removed | Browsers auto-isolate; unnecessary complexity |
| **Guest Tracking** | Explicit UUID | Reliable, doesn't depend on fingerprinting |
| **Token Storage** | localStorage (Supabase default) | Browsers handle incognito isolation automatically |
| **Logout Scope** | Current vs All | Separate endpoints for different use cases |

## Files Created/Modified

### New Files (Backend)
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/core/supabase.py`
- `backend/app/schemas/auth.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/guest.py`
- `backend/app/api/deps.py`
- `backend/requirements.txt`
- `backend/.env`

### New Files (Frontend)
- `src/lib/supabase.js`
- `src/context/AuthContext.jsx`
- `src/pages/SignIn/SignIn.jsx`
- `src/pages/SignIn/SignIn.css`
- `.env`

### Modified Files (Frontend)
- `src/App.jsx`
- `src/components/Navbar/Navbar.jsx`
- `src/components/Navbar/Navbar.css`

## Database Tables

| Table | Purpose | Auth Related |
|-------|---------|--------------|
| `users` | User profiles | Yes |
| `user_preferences` | Settings + taste vector | Yes |
| `guest_sessions` | Anonymous tracking | Yes |
| `watch_history` | Video watch records | Recommendations |
| `interactions` | Engagement signals | Recommendations |
| `subscriptions` | Channel subscriptions | Recommendations |
| `liked_videos` | Liked videos | Recommendations |
| `playlists` | User playlists | User data |
| `playlist_items` | Playlist contents | User data |

## Estimated Time

| Phase | Description | Time |
|-------|-------------|------|
| Phase 1 | Supabase Setup | 1-2 hours |
| Phase 2 | FastAPI Backend | 3-4 hours |
| Phase 3 | Frontend Integration | 3-4 hours |
| Phase 4 | Testing | 2-3 hours |
| **Total** | | **9-13 hours** |
