CREATE TABLE public.disliked_videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,

    disliked_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, video_id)
);