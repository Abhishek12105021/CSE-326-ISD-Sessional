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