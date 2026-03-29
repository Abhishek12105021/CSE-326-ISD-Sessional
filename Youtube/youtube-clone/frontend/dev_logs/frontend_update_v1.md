## **manual logs**

**known issues:**

1. 1 ta video o cholenai (iframe diye) [fixed]
2. signin kora jaitese na (still checking on this issue) [unsolved]
3. search not functional yet [fixed]
4. feed display has error which shows "You've reached the end" message instead of infinite scroll [fixed]
5. watch history te time update hoitese na [unsolved]

**known working:**

1. video load hocche
2. guest feed show hoitese
3. watch history update hoy
4. interaction update hoy
5. recommendation load hoy (both, lazy)
6. according to the loigc, watch history based feed update is implemented [but not tested yet]
   
**unknown issues:**
- need to test all other endpoints and fix the signin to get the authenticated user's workflow to test them


## **Claude Logs**

### What was changed (logically)

**1. API Config & Service Layer (`src/config/api.js`, `src/services/api.service.js`)**
- Added all missing endpoint constants: `GUEST_RELOAD`, `FEED_RELOAD`, `VIDEO_GET`, `WATCH`, `LIKE`, `DISLIKE`, `SUBSCRIBE`, `SUBSCRIPTIONS`, `SEARCH`, `SEARCH_RELOAD`, `RECOMMEND`, `RECOMMEND_RELOAD`, `WATCH_HISTORY`, `LIKES`, `CHANNELS`
- Rewrote the `request()` method to auto-parse JSON responses and throw on non-2xx HTTP status
- Added optional body support to the `delete()` method (required for like/dislike/subscribe DELETE endpoints)

**2. Auth Context (`src/context/AuthContext.jsx`)**
- Added `getWatchedVideoIds()` helper that reads localStorage watch history and returns an array of video UUIDs
- Exposed it via the context so Home can pass watch history to guest feed endpoints for personalization

**3. Global Spinner (`src/index.css`)**
- Added `.loading-spinner` CSS class with red spin animation — shared across Home, VideoPlayer, and Search pages

**4. Home Page (`src/pages/Home/Home.jsx`)**
- Replaced all hardcoded sample data with real API calls
- Fetches categories once from `GET /api/categories`; prepends "All"; filtering is client-side
- Branches feed fetch by auth state: authenticated uses `GET /api/feed` with JWT; guest uses `POST /api/guest/feed` with `{guest_uuid, region, watched_video_ids}`
- Guest feed passes `watched_video_ids` from localStorage so the backend can phase into personalized recommendations after enough watch history builds up
- Infinite scroll: window scroll listener calls reload endpoints (`/api/reload` or `/api/guest/reload`) with `excluded_video_ids` to prevent duplicates; appends new videos to state
- Fixed infinite scroll threshold: changed `fetched.length >= 30` to `fetched.length > 0` so the backend's variable-size responses (phase-based algorithm) don't prematurely end pagination

**5. Video Player (`src/pages/VideoPlayer/VideoPlayer.jsx`)**
- Fetches full video metadata via `POST /api/get` with the UUID from the URL (`/video/:id`)
- Embeds the actual YouTube video using a plain `<iframe>` with `video.video_id` (the 11-char YouTube ID, separate from the UUID)
- Two-phase watch tracking: INSERT on video load (saves `watch_id`), UPDATE on component unmount with elapsed seconds
- Saves video to localStorage watch history on load (feeds back into guest feed personalization)
- Loads recommendations via `POST /api/recommend?video_id=&limit=15` (query params, not body — backend uses FastAPI `Query()`)
- Infinite scroll on window loads more recommendations via `POST /api/reload-recommend` with exclusions
- Like/dislike toggle (POST/DELETE) for authenticated users only; subscription toggle similarly
- Subscribe button checks current state on mount via `GET /api/subscriptions`
- Comments section still uses static sample data (no comments API exists in the backend)

**6. Search Page (`src/pages/Search/Search.jsx`)**
- Replaced client-side filter with real search API
- Fixed 422 error: backend uses `Query()` params, so search is called as `POST /api/search?q=&limit=25` (params in URL, not request body)
- Infinite scroll reload via `POST /api/reload-search` with `{q, excluded_video_ids, limit}`
- "No results found" and "No more results" states handled

**7. OAuth Callback Fix (`src/App.jsx`, `src/pages/SignIn/SignIn.jsx`)**
- Added `NotFoundOrAuthCallback` component to the `*` catch-all route
- After Google sign-in, Supabase returns tokens in the URL hash; HashRouter treats this as an unknown route — the component detects the session becoming active and redirects to home
- OAuth errors (e.g. "Database error saving new user") are extracted from the URL and redirected to `/signin?auth_error=...` for display instead of showing a blank "Page Not Found"
