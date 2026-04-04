# YouTube Clone - Full Stack Recommendation System

A full-stack YouTube clone with an AI-powered recommendation engine built as a CSE-326 Information System Design Sessional project.

## Overview

The system provides a complete video recommendation platform combining a modern React frontend, FastAPI backend, and machine learning-driven personalization using vector embeddings and a 3-phase recommendation strategy.

**Key Components:**
- React 18 single-page application frontend
- FastAPI backend with 3-phase recommendation engine
- Supabase PostgreSQL database with pgvector support
- 24,499 videos with 1024-dimensional embeddings (BGE-M3)
- FAISS in-memory index for fast similarity search

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- Python 3.12
- Supabase project with database and authentication
- Git for version control

### Local Development

**1. Backend Setup (Terminal 1)**

```bash
cd youtube-clone/backend

# Windows PowerShell
Set-ExecutionPolicy -Scope Process Bypass
.\run.ps1

# OR Manual: Create virtual environment and install dependencies
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Backend runs on `http://127.0.0.1:8000`

**2. Frontend Setup (Terminal 2)**

```bash
cd youtube-clone/frontend

# Windows PowerShell
.\run.ps1

# OR Manual
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`

**3. Environment Configuration**

Create `.env` files in both directories:

**`youtube-clone/frontend/.env`:**
```
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000
```

**`youtube-clone/backend/.env`:**
```
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
FRONTEND_URL=http://localhost:3000
```

**4. Database Setup**

Execute the SQL files in Supabase SQL Editor:
1. `Data/schema.sql` - Creates tables and indexes
2. `Data/recommend.sql` - Creates RPC functions

**5. Verify Setup**

- Frontend: http://localhost:3000
- Backend health: `curl http://127.0.0.1:8000/health`
- API docs: http://localhost:8000/docs

## Architecture

### Frontend Layer

**Technology:** React 18 + Vite + React Router (HashRouter)

**Pages:**
- Home feed with video grid and category filters
- Video player with recommendations
- Channel pages
- Search (semantic and full-text)
- Watch history
- User authentication

**Key Features:**
- Feature toggles for conditional component rendering
- Mock data support for development
- Pure CSS styling
- Responsive design

### Backend API

**Technology:** FastAPI + Uvicorn + Supabase

**Core Endpoints:**
- `GET /health` - Server status
- `GET /api/feed` - Authenticated personalized feed
- `POST /api/guest/feed` - Guest feed
- `POST /api/search` - Semantic search
- `POST /api/recommend` - Similar video recommendations
- `POST /api/watch-event` - Track user interactions
- `POST/GET /api/like`, `/api/dislike` - User preferences
- `POST /api/subscribe` - Channel subscriptions

**Recommendation Engine (3-Phase Strategy):**
1. **Phase 1 (Cold Start):** 50% global trending + 50% local trending
2. **Phase 2 (Warm-up):** 30% semantic + 40% trending + 30% local
3. **Phase 3 (Personalized):** 60% semantic (local) + 20% semantic (foreign) + 10% local + 10% global

**Core Services:**
- JWT authentication via Supabase
- FAISS-based similarity search (~5K sampled videos)
- Sentence Transformers for vector encoding
- Country-aware recommendations

### Database Layer

**Technology:** Supabase (PostgreSQL) + pgvector

**Key Tables:**
- `videos` - 24,499 videos with 1024-dim embeddings
- `users` - User profiles
- `user_preferences` - Theme and personalization settings
- `watch_history` - User viewing records
- `liked_videos` - User preferences
- `subscriptions` - Channel subscriptions
- `guest_sessions` - Anonymous user tracking

## Project Structure

```
Youtube/
├── README.md                           (this file)
├── Data/
│   ├── schema.sql                      (database schema)
│   ├── recommend.sql                   (RPC functions)
│   ├── processed_youtube_global.csv    (24,499 videos)
│   ├── CleanDataset.ipynb              (data cleaning)
│   ├── embed-engine-populate.ipynb     (embedding generation)
│   └── Verification/                   (video ID validation)
└── youtube-clone/
    ├── frontend/
    │   ├── src/
    │   │   ├── pages/                  (Home, VideoPlayer, Channel, Search, WatchHistory, SignIn)
    │   │   ├── components/             (Navbar, Sidebar, VideoCard, RegionSelector)
    │   │   ├── services/               (API, auth, guest services)
    │   │   ├── context/                (Auth, Theme state)
    │   │   ├── lib/                    (Supabase client)
    │   │   ├── config/                 (features, API endpoints)
    │   │   ├── hooks/                  (custom React hooks)
    │   │   ├── App.jsx                 (router)
    │   │   └── main.jsx                (entry point)
    │   ├── package.json
    │   ├── vite.config.js
    │   └── .env.example
    └── backend/
        ├── app/
        │   ├── main.py                 (FastAPI app)
        │   ├── config.py               (settings)
        │   ├── db.py                   (database queries)
        │   ├── core/
        │   │   ├── recommendation.py   (3-phase logic)
        │   │   ├── faiss_manager.py    (FAISS index)
        │   │   ├── embedding_service.py (Sentence Transformers)
        │   │   └── supabase.py         (Supabase client)
        │   ├── api/
        │   │   ├── routes/             (auth, feed, search, guest)
        │   │   └── deps.py             (JWT verification)
        │   └── schemas/                (request/response models)
        ├── requirements.txt
        ├── .env.example
        └── modal_app.py                (deployment script)
```

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Frontend** | React | 18.2.0 |
| **Frontend Build** | Vite | 5.0.8 |
| **Frontend Routing** | React Router DOM | 6.21.0 |
| **Frontend Auth** | Supabase JS | 2.39.0 |
| **Backend** | FastAPI | 0.109.0 |
| **Backend Server** | Uvicorn | 0.27.0 |
| **Recommendations** | FAISS | 1.7.4 |
| **Embeddings** | Sentence Transformers | 2.2.0+ |
| **Database** | PostgreSQL (Supabase) | Latest |
| **Vector Search** | pgvector | Latest |
| **Python Runtime** | Python | 3.12 |
| **Node Runtime** | Node.js | 18+ |

## Data Pipeline

### Data Preparation
- **`processed_youtube_global.csv`**: 24,499 videos from 10 countries (CA, DE, FR, GB, IN, JP, KR, MX, RU, US)
- Deduplication and verification
- Computed trending frequency and velocity scores
- Regional and category metadata

### Embedding Generation
- Model: BAAI/bge-m3
- Dimension: 1024
- Process: Loads cleaned CSV → generates embeddings → populates database
- Index: FAISS for fast similarity search

### Database Population
- Videos table contains complete metadata
- Vector embeddings stored in pgvector column
- RPC functions for semantic search and trending retrieval

## Key Features Implemented

- [x] Responsive YouTube-like UI with modern design
- [x] Authentication with session management
- [x] 3-phase personalized feed generation
- [x] Vector embedding-based recommendations
- [x] Full-text and semantic search
- [x] Watch history tracking
- [x] Video likes/dislikes system
- [x] Channel subscriptions
- [x] Guest-to-authenticated user migration
- [x] Feature toggle system for UI components
- [x] FAISS in-memory index for performance
- [x] 24,499 video database with embeddings

## Performance Metrics

| Operation | Time | Notes |
|-----------|------|-------|
| Feed Generation (Phase 1) | ~200ms | Cold start |
| Feed Generation (Phase 2) | ~400ms | Warm-up |
| Feed Generation (Phase 3) | ~800ms | Fully personalized |
| Semantic Search | 300-500ms | Vector + FAISS |
| FAISS Index Load | ~5-60s | First run downloads model (~1GB) |

## Frontend Pages

- **Home** - Video grid with category filters
- **Video Player** - Watch page with player and recommendations
- **Channel** - Creator page with videos and info
- **Search** - Semantic and full-text video search
- **Watch History** - User's viewed videos
- **Sign In** - Authentication entry point

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Server status check |
| GET | `/api/feed` | Authenticated user feed |
| POST | `/api/guest/feed` | Guest user feed |
| POST | `/api/search` | Search videos |
| POST | `/api/recommend` | Get similar videos |
| POST | `/api/watch-event` | Track watch events |
| POST | `/api/like` | Like video |
| POST | `/api/dislike` | Dislike video |
| POST | `/api/subscribe` | Subscribe to channel |
| GET | `/api/auth/profile` | User profile |
| POST | `/api/auth/logout` | Logout |

## Dependencies

**Frontend:**
- react, react-dom, react-router-dom
- @supabase/supabase-js
- react-icons
- vite

**Backend:**
- fastapi, uvicorn
- supabase, postgrest-py
- faiss-cpu
- sentence-transformers
- numpy
- python-jose
- python-dotenv

See `youtube-clone/frontend/package.json` and `youtube-clone/backend/requirements.txt` for complete lists.

## Database Schema

Defined in `Data/schema.sql`:
- `videos` table with 24,499 rows and 1024-dim embeddings
- `users`, `user_preferences`, `guest_sessions` for authentication
- `watch_history`, `liked_videos`, `subscriptions` for interactions
- RPC functions for semantic search and trending retrieval

See `Data/recommend.sql` for recommendation query functions.

## Project Status

**Complete:**
- Full-stack application shell
- Backend API with all endpoints
- 3-phase recommendation engine
- 24,499 video database
- Frontend UI for all major pages
- Authentication system
- FAISS search optimization

**Notes:**
- FAISS index limited to 5K sampled videos (RAM constraints)
- Some UI pages use mock data alongside live API
- First backend startup downloads embedding model (~1GB, subsequent starts are ~5s)

## Dataset Information

The video dataset contains:
- **24,499 videos** from 10 countries
- **1024-dimensional embeddings** (BGE-M3 model)
- Metadata: title, channel, category, views, likes, publish date
- Trending scores and regional velocity metrics
- Verified video IDs for embeddability

## File Guide

**Key Configuration:**
- `frontend/src/config/features.js` - Feature toggles
- `frontend/src/config/api.js` - API endpoints
- `backend/app/config.py` - Backend settings

**Core Logic:**
- `backend/app/core/recommendation.py` - 3-phase recommendation strategy
- `backend/app/core/faiss_manager.py` - FAISS index management
- `backend/app/core/embedding_service.py` - Vector generation

**API Routes:**
- `backend/app/api/routes/feed.py` - Feed endpoints
- `backend/app/api/routes/search.py` - Search and recommendations
- `backend/app/api/routes/auth.py` - Authentication
- `backend/app/api/routes/guest.py` - Guest endpoints

## Requirements

- Node.js 18+
- Python 3.12
- PostgreSQL database (Supabase)
- Internet connection (for model downloads)

## License

CSE-326 Information System Design Sessional Project

## Contact

For project inquiries or issues, refer to the project documentation or repository issues.
