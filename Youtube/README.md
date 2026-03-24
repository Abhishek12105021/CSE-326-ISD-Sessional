# YouTube Folder README

This folder contains the YouTube Recommendation and Personalization System work for the CSE-326 Information System Design Sessional project. It is not just a frontend clone. It combines:

1. A React + Vite YouTube-style client application
2. A FastAPI backend for authentication and guest-session handling
3. Supabase/PostgreSQL database assets for users, sessions, and recommendation data
4. Dataset-processing and recommendation-engine notebooks
5. Supporting setup and implementation documents

The folder is best understood as a project root for one feature domain of the course project: a YouTube-like product with authentication, personalization, and recommendation support.

## What Is Inside This Folder

```text
Youtube/
|-- AUTH_IMPLEMENTATION_PLAN.md
|-- USER_SETUP_INSTRUCTIONS.md
|-- README.md
|-- Data/
|   |-- schema.sql
|   |-- recommend.sql
|   |-- processed_youtube_global.csv
|   |-- CleanDataset.ipynb
|   |-- embed-engine-populate.ipynb
|   `-- Verification/
|       |-- mock.html
|       |-- verifier.html
|       |-- video_id_tester.html
|       `-- Verfied Video IDS/
|           |-- verified_embeds_CA.csv
|           |-- verified_embeds_DE.csv
|           |-- verified_embeds_FR.csv
|           |-- verified_embeds_GB.csv
|           |-- verified_embeds_IN.csv
|           |-- verified_embeds_JP.csv
|           |-- verified_embeds_KR.csv
|           |-- verified_embeds_MX.csv
|           |-- verified_embeds_RU.csv
|           `-- verified_embeds_US.csv
`-- youtube-clone/
    |-- README.md
    |-- DEPLOYMENT.md
    |-- package.json
    |-- vite.config.js
    |-- .env.example
    |-- backend/
    |   |-- requirements.txt
    |   |-- .env.example
    |   `-- app/
    |       |-- main.py
    |       |-- config.py
    |       |-- core/
    |       |   `-- supabase.py
    |       |-- api/
    |       |   |-- deps.py
    |       |   `-- routes/
    |       |       |-- auth.py
    |       |       `-- guest.py
    |       `-- schemas/
    `-- src/
        |-- App.jsx
        |-- features.config.js
        |-- context/
        |   `-- AuthContext.jsx
        |-- lib/
        |   `-- supabase.js
        |-- data/
        |   `-- sampleData.js
        |-- components/
        `-- pages/
```

## Project Purpose

The project appears to target a YouTube-like system with three main goals:

- Recreate a familiar browsing experience with a modern frontend UI
- Support guest and authenticated usage through Supabase Auth and a FastAPI backend
- Build a recommendation foundation using cleaned multi-country YouTube data, vector embeddings, and SQL functions for semantic retrieval plus trending injection

## High-Level Architecture

### 1. Frontend: `youtube-clone/`

The frontend is a React 18 application built with Vite. It uses:

- `react-router-dom` with `HashRouter`
- `@supabase/supabase-js` for Google sign-in and session handling
- `react-icons` for the UI icon set
- Pure CSS for styling

Current major routes in the app:

- `/` - home feed
- `/video/:id` - watch page
- `/channel/:channelId` - channel page
- `/search?q=...` - search page
- `/signin` - Google sign-in page
- `/shorts`, `/subscriptions`, `/history`, `/trending` - placeholder routes

Feature flags are centralized in `youtube-clone/src/features.config.js`, so pages/components can be disabled without removing the entire code path.

### 2. Backend: `youtube-clone/backend/`

The backend is a FastAPI service that verifies Supabase-issued JWTs and provides application-specific API endpoints. Its job is not to replace Supabase Auth. Instead, it trusts Supabase as the identity provider and adds app-level behavior around:

- profile retrieval and profile updates
- preference retrieval and preference updates
- guest session creation and lookup
- guest-to-user data migration
- logout and logout-all signaling

Current backend routes:

- `GET /health`
- `GET /api/auth/profile`
- `PUT /api/auth/profile`
- `GET /api/auth/preferences`
- `PUT /api/auth/preferences`
- `POST /api/auth/migrate-guest`
- `POST /api/auth/logout`
- `POST /api/auth/logout-all`
- `POST /api/guest/session`
- `GET /api/guest/session/{guest_uuid}`
- `DELETE /api/guest/session/{guest_uuid}`

### 3. Supabase and Database Layer

The Supabase side is split into two concerns:

- Auth and user/session tables described in `AUTH_IMPLEMENTATION_PLAN.md`
- Recommendation/video catalog schema in `Data/schema.sql` and `Data/recommend.sql`

This means the full system uses Supabase for:

- Google OAuth authentication
- PostgreSQL data storage
- row-level security
- vector similarity search via `pgvector`

### 4. Data and Recommendation Pipeline

The `Data/` folder contains the assets used to prepare and query recommendation data:

- cleaned global CSV data
- SQL schema for a `videos` table with 1024-dimensional embeddings
- SQL functions for similarity search and trending retrieval
- notebooks for cleaning, embedding, indexing, and populating the database
- verification artifacts for ensuring valid embeddable/usable video IDs by country

## Current Implementation Status

This is the most important thing to know before you start working in this folder.

### What is already implemented

- A polished frontend UI for home, video player, channel, search, and sign-in
- Google OAuth client integration through Supabase on the frontend
- A FastAPI auth layer that verifies Supabase JWTs
- Guest UUID generation and migration flow in the frontend auth context
- SQL assets for the recommendation schema and functions
- A fairly detailed authentication implementation plan document

### What is only partially connected

- The frontend browsing pages currently use local mock data from `youtube-clone/src/data/sampleData.js`
- The recommendation SQL is present, but the frontend is not yet querying those recommendation functions
- The backend supports auth/session APIs, but the frontend is not yet using backend-driven feeds or search results

### What is still missing or incomplete

- A real settings page route, even though the navbar/sidebar link to `/settings`
- End-to-end integration between the UI and the recommendation tables/functions
- A committed production ingestion script outside the notebooks
- A single source of truth document for setup; this README helps with that

## Important Port Note

Most runtime files now align on `http://localhost:3000`, but there are still some historical references to `5173` inside the older implementation-plan document.

- `youtube-clone/vite.config.js` runs the frontend on `http://localhost:3000`
- `youtube-clone/backend/app/config.py` now defaults `FRONTEND_URL` to `http://localhost:3000`
- `youtube-clone/backend/.env.example` now defaults `FRONTEND_URL` to `http://localhost:3000`

For local development, pick one port and keep everything aligned. Based on the current frontend code, the safest default is:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`

If you keep the current Vite config unchanged, use `3000` consistently in:

- Google OAuth authorized JavaScript origin
- backend `FRONTEND_URL`
- any frontend/backend setup instructions you follow manually

If you prefer `5173`, then change `vite.config.js` instead.

## Detailed Breakdown

### `AUTH_IMPLEMENTATION_PLAN.md`

This is the most detailed design/implementation document in the folder. It covers:

- the revised auth architecture
- why Supabase is the single source of truth for authentication
- user model design for guests and authenticated users
- SQL for user-related tables
- row-level security policy design
- helper triggers/functions such as:
  - `handle_new_user()`
  - `update_interaction_count()`
  - `migrate_guest_to_user(...)`
- backend file structure and code plan
- frontend integration steps
- testing checklist

If you want to understand the intended product behavior, read this file first.

### `USER_SETUP_INSTRUCTIONS.md`

This is now a deployment-first setup guide focused on:

- creating the Supabase project
- configuring Google OAuth for production
- setting Supabase Auth site/redirect URLs
- deploying the backend to Render
- deploying the frontend to Vercel
- configuring production environment variables
- testing the hosted app

It also includes a smaller local-testing appendix at the end.

### `Data/schema.sql`

This file creates the recommendation catalog table:

- `public.videos`

Key fields include:

- `video_id`
- `country_code`
- `title`
- `channel_title`
- `category_name`
- `thumbnail_link`
- `views`, `likes`, `dislikes`, `comment_count`
- `trending_frequency`
- `velocity_score`
- `embedding vector(1024)`

It also:

- enables the vector extension
- creates an HNSW index for cosine similarity search
- enables row-level security
- allows public read access to the `videos` table

### `Data/recommend.sql`

This file contains the main query functions for recommendation retrieval:

- `search_videos(...)`
  - semantic similarity search over `embedding vector(1024)`
  - optional country filtering
  - returns cosine similarity

- `get_trending(...)`
  - returns randomized results from the top trending pool
  - optional country filtering
  - supports exclusion lists to avoid overlap with semantic results

Together, these functions support a hybrid strategy:

- semantic personalization
- same-country bias when needed
- foreign discovery
- trending fallback/injection

### `Data/processed_youtube_global.csv`

This is the processed dataset used as a source for the recommendation system. Notebook output embedded in the repository indicates a prepared dataset of approximately:

- `24,499` rows
- `10` countries: `CA`, `DE`, `FR`, `GB`, `IN`, `JP`, `KR`, `MX`, `RU`, `US`

This dataset is the bridge between raw trending YouTube data and the final vector-search-ready `videos` table.

### `Data/CleanDataset.ipynb`

This notebook is part of the data-preparation stage. Based on its code/output, it handles tasks such as:

- loading country-specific trending data
- deduplicating videos
- filtering to verified video IDs
- computing `trending_frequency`
- computing normalized `velocity_score`
- assembling a `mega_string` text field
- assigning `country_code`
- producing the cleaned global CSV

### `Data/embed-engine-populate.ipynb`

This notebook covers the embedding and retrieval side. The code/output indicates that it:

- loads `processed_youtube_global.csv`
- uses `BAAI/bge-m3` embeddings
- generates `1024`-dimensional dense vectors
- builds FAISS indexes for exploration/testing
- demonstrates bucketed recommendation logic
- upserts the final recommendation rows into Supabase

The notebook output indicates successful population of about `24,499` rows into the `videos` table.

### `Data/Verification/`

This folder contains helper files used to validate video IDs and embed usability:

- `verifier.html`
- `video_id_tester.html`
- `mock.html`
- per-country verified ID CSVs in `Verfied Video IDS/`

These appear to support the filtering/verification step before videos are admitted into the cleaned recommendation dataset.

### `youtube-clone/`

This folder contains the runnable app code.

#### Frontend pages

- `Home` shows category pills, a Shorts section, and a grid of videos
- `Search` filters videos by title, channel, or category
- `VideoPlayer` shows a watch-page layout with recommended videos and nested comments
- `Channel` shows a banner, avatar, stats, tabs, and channel videos
- `SignIn` handles Google OAuth entry

#### Frontend auth flow

The frontend auth flow currently works like this:

1. Supabase initializes on app startup
2. If the user is not signed in, a guest UUID is created in `localStorage`
3. If the user signs in with Google, Supabase returns a session
4. If a previous guest UUID exists, the frontend calls `/api/auth/migrate-guest`
5. Navbar state updates based on authentication status

#### Frontend data mode

The UI pages currently render from `src/data/sampleData.js`, not the recommendation database. That sample file contains:

- mock videos
- mock comments with replies
- mock Shorts data
- category labels

This is important because it means the user experience currently demonstrates layout and interaction patterns more than live personalization.

#### Backend files

Important backend files:

- `backend/app/main.py` - FastAPI app entry point and router registration
- `backend/app/config.py` - environment-variable configuration
- `backend/app/api/deps.py` - Supabase JWT verification and current-user dependency
- `backend/app/api/routes/auth.py` - profile/preferences/migration/logout endpoints
- `backend/app/api/routes/guest.py` - guest-session endpoints
- `backend/app/core/supabase.py` - service-role Supabase client

## Database Model Summary

The full data model is spread across `Data/schema.sql` and `AUTH_IMPLEMENTATION_PLAN.md`.

### Recommendation/content table

- `videos`

### Authentication and personalization tables

- `users`
- `user_preferences`
- `guest_sessions`
- `watch_history`
- `interactions`
- `subscriptions`
- `liked_videos`
- `playlists`
- `playlist_items`

Conceptually:

- `users` extends `auth.users`
- `user_preferences` stores personalization state, theme, autoplay, and taste-vector information
- `guest_sessions` tracks anonymous users before sign-in
- `watch_history` and `interactions` provide the behavioral signal needed for recommendations
- `playlists`, `subscriptions`, and `liked_videos` support common YouTube-style user features

## How To Run This Project

There are two practical ways to approach this folder.

### Option A: Understand and review the project structure

If you are reading the folder for coursework, documentation, or architecture review:

1. Read `AUTH_IMPLEMENTATION_PLAN.md`
2. Read this `README.md`
3. Read `youtube-clone/README.md`
4. Read `youtube-clone/DEPLOYMENT.md` if deployment matters
5. Inspect `Data/schema.sql` and `Data/recommend.sql`

### Option B: Run the app locally

#### Prerequisites

- Node.js and npm
- Python 3.10+ recommended
- A Supabase project
- A Google Cloud OAuth client for Google sign-in

#### Step 1: Create environment files

Frontend:

```env
# youtube-clone/.env
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000
```

Backend:

```env
# youtube-clone/backend/.env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
FRONTEND_URL=http://localhost:3000
```

#### Step 2: Configure Supabase Auth and Google OAuth

Use `USER_SETUP_INSTRUCTIONS.md` for the full click-by-click deployment process.

Minimum items to configure:

- Supabase project URL
- anon key
- service role key
- JWT secret
- Google OAuth provider in Supabase
- Google OAuth authorized origin matching your frontend port
- Supabase callback URL in Google Cloud Console

#### Step 3: Run the SQL

For the full project, you should apply:

1. The auth/user SQL from `AUTH_IMPLEMENTATION_PLAN.md` Step 1.3
2. `Data/schema.sql`
3. `Data/recommend.sql`

Suggested order:

- run the auth schema first
- run the video/recommendation schema second
- run the recommendation functions third

If you only want the auth flow, the auth SQL is the critical part.

#### Step 4: Start the backend

```bash
cd youtube-clone/backend
python -m venv venv

# Windows
venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Step 5: Start the frontend

```bash
cd youtube-clone
npm install
npm run dev
```

With the current `vite.config.js`, the frontend should open on:

```text
http://localhost:3000
```

## Local Development Notes

- The frontend uses `HashRouter`, which makes static deployment easier
- `vite.config.js` currently uses `base: './'`
- `vercel.json` and `netlify.toml` are already present
- feature toggles live in `youtube-clone/src/features.config.js`
- the auth provider wraps the entire frontend app, so valid Supabase frontend env vars are important even before deeper auth testing

## Known Limitations and Risks

- The main feed/search/watch/channel pages are still mock-data-driven
- `/settings` is linked in the UI but not implemented as a route
- Existing setup docs disagree on frontend port
- The notebooks are the current source for ingestion logic; there is no dedicated production ingestion script in this folder
- Recommendation SQL exists, but there is no completed backend endpoint yet that serves personalized feed results into the React UI
- Public placeholder image services are used in the mock UI, so image loading depends on internet access

## Recommended Next Steps

If this folder is going to be continued or submitted as a stronger end-to-end system, the next high-value steps would be:

1. Update the remaining historical `5173` references in `AUTH_IMPLEMENTATION_PLAN.md`
2. Add backend feed/search/recommendation endpoints that call `search_videos()` and `get_trending()`
3. Replace `sampleData.js` usage with live API data
4. Implement the missing `/settings` route or remove the link
5. Convert the notebook ingestion logic into a scriptable pipeline
6. Add a concise architecture diagram or sequence diagram specifically for guest-to-user migration and recommendation retrieval

## Related Documents

- `Youtube/AUTH_IMPLEMENTATION_PLAN.md`
- `Youtube/USER_SETUP_INSTRUCTIONS.md`
- `Youtube/youtube-clone/README.md`
- `Youtube/youtube-clone/DEPLOYMENT.md`

## Summary

This `Youtube` folder already contains a solid foundation for a recommendation-oriented YouTube clone:

- a presentable frontend
- a real auth approach with Supabase + FastAPI
- a rich data model for anonymous and authenticated behavior
- vector-search-oriented recommendation assets

The biggest gap is integration. The UI, backend auth layer, and recommendation dataset all exist, but they are not yet fully connected into one live personalized application.
