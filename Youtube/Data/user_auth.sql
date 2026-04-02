-- ============================================================
-- ENABLE EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USERS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    region TEXT DEFAULT 'US',
    country TEXT DEFAULT 'United States',
    LANGUAGE TEXT DEFAULT 'en',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- WATCH HISTORY TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.watch_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    watch_duration_seconds INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

-- ============================================================
-- SUBSCRIPTIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    channel_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, channel_id)
);

-- ============================================================
-- LIKED VIDEOS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.liked_videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    liked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, video_id)
);

-- ============================================================
-- DISLIKED VIDEOS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS public.disliked_videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    disliked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, video_id)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_users_region ON public.users (region);

CREATE INDEX IF NOT EXISTS idx_users_last_login ON public.users (last_login_at);

CREATE INDEX IF NOT EXISTS idx_watch_history_user ON public.watch_history (user_id);

CREATE INDEX IF NOT EXISTS idx_watch_history_video ON public.watch_history (video_id);

CREATE INDEX IF NOT EXISTS idx_watch_history_started ON public.watch_history (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON public.subscriptions (user_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_channel ON public.subscriptions (channel_id);

CREATE INDEX IF NOT EXISTS idx_liked_videos_user ON public.liked_videos (user_id);

CREATE INDEX IF NOT EXISTS idx_liked_videos_video ON public.liked_videos (video_id);

CREATE INDEX IF NOT EXISTS idx_disliked_videos_user ON public.disliked_videos (user_id);

CREATE INDEX IF NOT EXISTS idx_disliked_videos_video ON public.disliked_videos (video_id);

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
    )
    ON CONFLICT (id) DO NOTHING;

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