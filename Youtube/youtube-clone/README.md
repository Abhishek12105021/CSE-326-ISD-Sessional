# YouTube Clone

Full-stack YouTube-style course project with:

- `frontend/` - React + Vite client
- `backend/` - FastAPI API with **3-phase recommendation engine**
- Supabase Auth for Google sign-in
- Supabase/Postgres as the app database
- **24,499+ video database** with BGE-M3 embeddings

## Agent Summary

This section is intentionally structured so a coding agent can scan it quickly.

```text
PROJECT_NAME: youtube-clone
PROJECT_TYPE: full-stack web app
FRONTEND_DIR: frontend
BACKEND_DIR: backend
FRONTEND_PORT: 3000
BACKEND_PORT: 8000
FRONTEND_FRAMEWORK: React 18 + Vite
BACKEND_FRAMEWORK: FastAPI
AUTH_PROVIDER: Supabase Auth (Google OAuth)
ROUTER: HashRouter
PRIMARY_RUN_GUIDE: RUN_INSTRUCTIONS.md
PRIMARY_DEPLOY_GUIDE: ../deployment_guide.md
BACKEND_RUN_SCRIPT_WINDOWS: backend/run.ps1
FRONTEND_RUN_SCRIPT_WINDOWS: frontend/run.ps1
BACKEND_ENTRYPOINT: backend/app/main.py
FRONTEND_ENTRYPOINT: frontend/src/main.jsx
FRONTEND_ENV_FILE: frontend/.env
BACKEND_ENV_FILE: backend/.env
FRONTEND_REQUIRED_ENV_KEYS: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL
BACKEND_REQUIRED_ENV_KEYS: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SUPABASE_JWT_SECRET, FRONTEND_URL
KNOWN_LIMITATION: frontend still uses mock/sample data, backend recommendation API ready for integration
```

## Current Structure

```text
youtube-clone/
|-- README.md
|-- RUN_INSTRUCTIONS.md
|-- DEPLOYMENT.md
|-- vercel.json
|-- netlify.toml
|-- frontend/
|   |-- .env
|   |-- .env.example
|   |-- package.json
|   |-- package-lock.json
|   |-- vite.config.js
|   |-- run.ps1
|   |-- index.html
|   `-- src/
|       |-- main.jsx
|       |-- App.jsx
|       |-- lib/supabase.js
|       |-- context/AuthContext.jsx
|       |-- components/
|       `-- pages/
`-- backend/
    |-- .env
    |-- .env.example
    |-- requirements.txt
    |-- run.ps1
    |-- run.sh
    `-- app/
        |-- main.py
        |-- config.py
        |-- api/
        |   |-- deps.py
        |   `-- routes/
        |       |-- auth.py
        |       `-- guest.py
        |-- core/supabase.py
        `-- schemas/
```

## What This Project Does

### Frontend

The frontend provides a YouTube-like UI with:

- home feed
- watch page
- channel page
- search page
- sign-in page
- placeholder routes for Shorts, Subscriptions, History, and Trending

It uses:

- `react-router-dom`
- `@supabase/supabase-js`
- `react-icons`
- pure CSS

### Backend

The backend verifies Supabase JWTs and exposes app-level routes for:

- profile read/update
- guest session acknowledgement (POST)
- logout/logout-all signaling
- **personalized video feed generation (NEW!)**
- **watch history tracking (NEW!)**
- **3-phase recommendation engine (NEW!)**

Health endpoint:

```text
GET /health
```

## Quick Start

For the full local run guide, use:

- `RUN_INSTRUCTIONS.md`

### Windows PowerShell

Backend:

```powershell
cd "C:\D drive\L3-T2\CSE326 Information System Design Sessional\CSE-326-ISD-Sessional\Youtube\youtube-clone\backend"
Set-ExecutionPolicy -Scope Process Bypass
.\run.ps1
```

Frontend:

```powershell
cd "C:\D drive\L3-T2\CSE326 Information System Design Sessional\CSE-326-ISD-Sessional\Youtube\youtube-clone\frontend"
Set-ExecutionPolicy -Scope Process Bypass
.\run.ps1
```

Open:

```text
http://localhost:3000
```

Backend health:

```text
http://127.0.0.1:8000/health
```

## Environment Variables

Do not commit real secrets to version control.

### Frontend

File:

```text
frontend/.env
```

Required keys:

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-public-key
VITE_API_URL=http://localhost:8000
```

### Backend

File:

```text
backend/.env
```

Required keys:

```env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
FRONTEND_URL=http://localhost:3000
```

## Google Sign-In Requirements

Google sign-in will not work unless Supabase and Google OAuth are configured correctly.

Minimum local config:

- Supabase Site URL: `http://localhost:3000`
- Supabase Redirect URL: `http://localhost:3000`
- Google OAuth Authorized JavaScript origin: `http://localhost:3000`
- Google OAuth Redirect URI: `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`

## Important Files

If you are exploring or modifying the project, start here:

- `frontend/src/App.jsx`
- `frontend/src/context/AuthContext.jsx`
- `frontend/src/lib/supabase.js`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/core/supabase.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/guest.py` (Updated with feed generation!)
- `RUN_INSTRUCTIONS.md`

## Current State

What is real:

- frontend app shell
- Supabase-based Google sign-in integration
- FastAPI auth/session backend
- guest session handling
- **3-phase recommendation engine backend (NEW!)**
- **24,499 video database with embeddings (NEW!)**
- **personalized feed generation API (NEW!)**

What is still partial:

- main pages still rely on local sample/mock data for browsing (frontend integration pending)
- some routes like settings are not fully implemented
- video search functionality (future work)

## Known Gotchas

- Use `python -m uvicorn`, not plain `uvicorn`, if running manually
- Use Python `3.12` for the backend virtual environment
- Frontend must have `@supabase/supabase-js` installed in `frontend/node_modules`
- Placeholder Supabase values will break Google sign-in immediately
- If `.env` values change, restart both backend and frontend

## Related Docs

- `RUN_INSTRUCTIONS.md`
- `DEPLOYMENT.md`
- `../README.md`
- `../deployment_guide.md`
