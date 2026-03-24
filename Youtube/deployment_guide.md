# Deployment Setup Instructions

This guide is now written for deployment, not just local development.

Recommended deployment stack for this project:

- Supabase for database + authentication
- Render for the FastAPI backend
- Vercel for the React/Vite frontend

That choice matches the current codebase well:

- the frontend already includes `vercel.json`
- the app is a Vite SPA with `HashRouter`
- the backend only needs a standard Python web service
- Supabase is already the auth/database source of truth

---

## Deployment Architecture

Your deployed system should look like this:

```text
Frontend (Vercel)
https://your-frontend-name.vercel.app
        |
        | calls
        v
Backend API (Render)
https://your-backend-name.onrender.com
        |
        | reads/writes
        v
Supabase
https://YOUR_PROJECT_REF.supabase.co
```

Google OAuth flow:

1. User clicks Sign in on the deployed frontend
2. Supabase handles Google OAuth
3. Supabase redirects the user back to your deployed frontend URL
4. Frontend uses the Supabase session token
5. Backend verifies the Supabase-issued JWT

---

## Before You Start

You need:

- a GitHub repository with this project pushed
- a Supabase account
- a Google Cloud project
- a Render account
- a Vercel account

Important current project note:

- `youtube-clone/vite.config.js` uses port `3000` for local dev
- so if you keep local testing enabled, use `http://localhost:3000`, not `5173`

---

## STEP 1: Create the Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Create a new project
3. Save these values from **Project Settings > API**

You will need all four:

| Variable | Example |
|----------|---------|
| `SUPABASE_URL` | `https://YOUR_PROJECT_REF.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anon public key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `SUPABASE_JWT_SECRET` | JWT secret from Supabase API settings |

Do not expose `SUPABASE_SERVICE_KEY` publicly. It is backend-only.

---

## STEP 2: Run the SQL in Supabase

Open **Supabase Dashboard > SQL Editor** and run the SQL in this order.

### 2A. Auth/User Schema

Run the SQL from:

- `Youtube/AUTH_IMPLEMENTATION_PLAN.md`
- specifically the SQL block in **Step 1.3**

This creates the user/session/personalization tables such as:

- `users`
- `user_preferences`
- `guest_sessions`
- `watch_history`
- `interactions`
- `subscriptions`
- `liked_videos`
- `playlists`
- `playlist_items`

### 2B. Recommendation Catalog Schema

Run:

- `Youtube/Data/schema.sql`

This creates:

- `public.videos`
- vector index
- public read policy

### 2C. Recommendation Functions

Run:

- `Youtube/Data/recommend.sql`

This creates:

- `search_videos(...)`
- `get_trending(...)`

### Verify

After running the SQL, make sure these exist in Supabase:

- all auth/personalization tables from the auth plan
- the `videos` table
- the `search_videos` function
- the `get_trending` function

---

## STEP 3: Configure Google OAuth for Production

### 3A. In Google Cloud Console

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create or select a project
3. Open **APIs & Services > OAuth consent screen**
4. Configure the app as **External**
5. Add scopes:
   - `email`
   - `profile`
   - `openid`

### 3B. Create the OAuth Client

Go to **APIs & Services > Credentials** and create a **Web application** OAuth client.

Use these values:

#### Authorized JavaScript origins

Add:

```text
http://localhost:3000
https://your-frontend-name.vercel.app
```

If you later add a custom domain, add that too.

#### Authorized redirect URIs

Add:

```text
https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback
```

That is the important redirect URI. Do not replace it with the frontend URL.

### 3C. Add Google Provider in Supabase

In **Supabase Dashboard > Authentication > Providers > Google**:

1. Enable Google provider
2. Paste the Google **Client ID**
3. Paste the Google **Client Secret**
4. Save

---

## STEP 4: Configure Supabase Auth URLs

In **Supabase Dashboard > Authentication > URL Configuration**:

### Site URL

Set:

```text
https://your-frontend-name.vercel.app
```

### Redirect URLs

Add at least:

```text
http://localhost:3000
https://your-frontend-name.vercel.app
```

If you later use a custom frontend domain, add it here too.

Why this matters:

- the frontend calls `supabase.auth.signInWithOAuth(...)`
- the app redirects back to `window.location.origin`
- Supabase must allow that origin

---

## STEP 5: Deploy the Backend to Render

The backend folder is:

```text
Youtube/youtube-clone/backend
```

### 5A. Create the Render Service

1. Go to [render.com](https://render.com)
2. Click **New +**
3. Choose **Web Service**
4. Connect your GitHub repo

### 5B. Render Service Settings

Use these values:

| Setting | Value |
|---------|-------|
| Root Directory | `Youtube/youtube-clone/backend` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

If Render asks for a health check path, use:

```text
/health
```

### 5C. Backend Environment Variables in Render

Add these environment variables exactly:

| Key | Value |
|-----|-------|
| `SUPABASE_URL` | `https://YOUR_PROJECT_REF.supabase.co` |
| `SUPABASE_ANON_KEY` | your Supabase anon key |
| `SUPABASE_SERVICE_KEY` | your Supabase service role key |
| `SUPABASE_JWT_SECRET` | your Supabase JWT secret |
| `FRONTEND_URL` | `https://your-frontend-name.vercel.app` |

Important:

- `FRONTEND_URL` must be your deployed Vercel frontend URL
- if you change the frontend URL later, update this value in Render too

### 5D. Save the Backend URL

After deployment, Render will give you a URL like:

```text
https://your-backend-name.onrender.com
```

Save it. You need it for the frontend env vars.

---

## STEP 6: Deploy the Frontend to Vercel

The frontend folder is:

```text
Youtube/youtube-clone
```

### 6A. Create the Vercel Project

1. Go to [vercel.com](https://vercel.com)
2. Click **Add New Project**
3. Import your GitHub repository

### 6B. Vercel Project Settings

Use these values:

| Setting | Value |
|---------|-------|
| Root Directory | `Youtube/youtube-clone` |
| Framework Preset | `Vite` |
| Build Command | `npm run build` |
| Output Directory | `dist` |

The project already includes:

- `vercel.json`

So SPA fallback routing is already prepared.

### 6C. Frontend Environment Variables in Vercel

Add these environment variables exactly:

| Key | Value |
|-----|-------|
| `VITE_SUPABASE_URL` | `https://YOUR_PROJECT_REF.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | your Supabase anon key |
| `VITE_API_URL` | `https://your-backend-name.onrender.com` |

Important:

- `VITE_API_URL` must point to the deployed backend, not localhost

### 6D. Save the Frontend URL

After deployment, Vercel will give you a URL like:

```text
https://your-frontend-name.vercel.app
```

---

## STEP 7: Final Cross-Check After Both Deployments

After both frontend and backend are deployed, check these four places one more time.

### Backend (Render)

Make sure:

```text
FRONTEND_URL=https://your-frontend-name.vercel.app
```

### Frontend (Vercel)

Make sure:

```text
VITE_API_URL=https://your-backend-name.onrender.com
```

### Supabase Auth URL Configuration

Make sure:

- Site URL is your Vercel frontend URL
- Redirect URLs include your Vercel frontend URL

### Google Cloud OAuth

Make sure:

- Authorized JavaScript origins include your Vercel frontend URL
- Authorized redirect URI includes the Supabase callback URL

---

## STEP 8: Test the Deployed App

### Test 1: Backend Health

Open:

```text
https://your-backend-name.onrender.com/health
```

Expected response:

```json
{
  "status": "healthy",
  "auth_provider": "supabase"
}
```

### Test 2: Frontend Loads

Open:

```text
https://your-frontend-name.vercel.app
```

You should see the home page.

### Test 3: Google Sign-In

1. Click **Sign in**
2. Click **Continue with Google**
3. Finish the Google OAuth flow
4. You should be redirected back to the frontend
5. Your avatar/menu should appear in the navbar

### Test 4: Authenticated API

After sign-in, open browser devtools and verify authenticated requests go to:

```text
https://your-backend-name.onrender.com/api/auth/...
```

---

## Production Environment Variables Summary

Use this as your final checklist.

### Render backend env vars

```env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
FRONTEND_URL=https://your-frontend-name.vercel.app
```

### Vercel frontend env vars

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
VITE_API_URL=https://your-backend-name.onrender.com
```

---

## If You Also Want Local Testing Later

For local testing, use:

### Backend local `.env`

```env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
FRONTEND_URL=http://localhost:3000
```

### Frontend local `.env`

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
VITE_API_URL=http://localhost:8000
```

If you switch between local and deployed environments often, remember:

- local frontend uses `3000`
- deployed frontend uses your Vercel URL
- backend `FRONTEND_URL` must match the environment you are currently testing

---

## Troubleshooting

### Google says "redirect_uri_mismatch"

Check that Google Cloud has:

```text
https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback
```

in **Authorized redirect URIs** exactly.

### Sign-in succeeds but app does not return correctly

Check:

- Supabase **Site URL**
- Supabase **Redirect URLs**
- Google **Authorized JavaScript origins**

They must all include your deployed frontend domain.

### Backend returns CORS errors

Check Render env var:

```text
FRONTEND_URL=https://your-frontend-name.vercel.app
```

If it points to localhost or an old domain, requests will fail.

### Frontend cannot reach backend

Check Vercel env var:

```text
VITE_API_URL=https://your-backend-name.onrender.com
```

Do not leave this as `http://localhost:8000` in production.

### Backend returns 401 Unauthorized

Usually one of these is wrong:

- `SUPABASE_JWT_SECRET`
- Supabase session token is missing
- user tables/triggers were not created from the auth SQL

### Frontend build passes but auth behaves strangely

Check that:

- Vercel env vars were added to the correct environment
- you redeployed after changing env vars
- Supabase provider config is saved

---

## Quick Deployment Order

If you just want the shortest version, do this:

1. Create Supabase project
2. Run auth SQL from `AUTH_IMPLEMENTATION_PLAN.md`
3. Run `Data/schema.sql`
4. Run `Data/recommend.sql`
5. Configure Google OAuth in Google Cloud
6. Enable Google provider in Supabase
7. Set Supabase Site URL + Redirect URLs
8. Deploy backend on Render with the backend env vars
9. Deploy frontend on Vercel with the frontend env vars
10. Update any final URLs if the generated domains changed
11. Test `/health`, home page, and Google sign-in

---

## Files Relevant to Deployment

- `Youtube/AUTH_IMPLEMENTATION_PLAN.md`
- `Youtube/Data/schema.sql`
- `Youtube/Data/recommend.sql`
- `Youtube/youtube-clone/vercel.json`
- `Youtube/youtube-clone/netlify.toml`
- `Youtube/youtube-clone/vite.config.js`
- `Youtube/youtube-clone/backend/app/main.py`
- `Youtube/youtube-clone/backend/app/config.py`

---

## Final Note

This project can be deployed cleanly with the stack above, but the app is currently a hybrid state:

- authentication is real
- backend auth APIs are real
- recommendation SQL is real
- the main browsing UI still uses mock sample data

So deployment will give you a real hosted app with real sign-in and backend integration, but not yet a fully database-driven personalized feed.
