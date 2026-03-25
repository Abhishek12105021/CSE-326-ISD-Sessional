# User Setup Instructions

These are the manual steps you need to complete. I've implemented all the code - you just need to configure the external services.

---

## STEP 1: Create Supabase Project (5 minutes)

1. Go to [supabase.com](https://supabase.com) and sign in/sign up
2. Click **"New Project"**
3. Fill in:
   - **Name**: `youtube-clone` (or any name)
   - **Database Password**: Generate a strong password (save it!)
   - **Region**: Choose closest to you
4. Click **"Create new project"** and wait ~2 minutes

### Get Your Credentials

Once ready, go to **Project Settings > API** and copy:

| Credential | Where to Find | Used For |
|------------|---------------|----------|
| **Project URL** | `https://xxx.supabase.co` | Frontend + Backend |
| **anon public** | Under "Project API keys" | Frontend |
| **service_role** | Under "Project API keys" (click reveal) | Backend only |
| **JWT Secret** | Scroll down to "JWT Settings" | Backend JWT verification |

---

## STEP 2: Configure Google OAuth (10 minutes)

### 2A: Google Cloud Console

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project or select existing
3. Navigate to **APIs & Services > OAuth consent screen**
   - Choose **External**
   - App name: `YouTube Clone`
   - User support email: Your email
   - Developer contact: Your email
   - Click **Save and Continue**
   - Scopes: Click **Add or Remove Scopes**, select:
     - `email`
     - `profile`
     - `openid`
   - Click **Save and Continue** through the rest

4. Navigate to **APIs & Services > Credentials**
5. Click **Create Credentials > OAuth client ID**
   - Application type: **Web application**
   - Name: `YouTube Clone Web`
   - Authorized JavaScript origins:
     ```
     http://localhost:5173
     ```
   - Authorized redirect URIs:
     ```
     https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback
     ```
     (Replace `YOUR_PROJECT_REF` with your Supabase project reference)
6. Click **Create** and copy:
   - **Client ID**
   - **Client Secret**

### 2B: Supabase Auth Configuration

1. In Supabase Dashboard, go to **Authentication > Providers**
2. Find **Google** and click to expand
3. Toggle **Enable Sign in with Google** ON
4. Paste your **Client ID** and **Client Secret**
5. Click **Save**

---

## STEP 3: Run Database Schema (2 minutes)

1. In Supabase Dashboard, go to **SQL Editor**
2. Click **New Query**
3. Copy the entire SQL from `AUTH_IMPLEMENTATION_PLAN.md` (Step 1.3)
4. Click **Run** (or press Ctrl+Enter)
5. You should see "Success. No rows returned" - this is correct

### Verify Tables Created

Go to **Table Editor** and confirm these tables exist:
- `users`
- `user_preferences`
- `guest_sessions`
- `watch_history`
- `interactions`
- `subscriptions`
- `liked_videos`
- `playlists`
- `playlist_items`

---

## STEP 4: Configure Environment Variables

### Backend (.env)

Create/update `youtube-clone/backend/.env`:

```env
# Supabase Configuration
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# CORS
FRONTEND_URL=http://localhost:5173
```

### Frontend (.env)

Create/update `youtube-clone/.env`:

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-public-key
VITE_API_URL=http://localhost:8000
```

---

## STEP 5: Install Dependencies & Run

### Backend

```bash
cd youtube-clone/backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd youtube-clone
npm install
npm run dev
```

---

## STEP 6: Test the Flow

1. Open `http://localhost:5173`
2. You should see the home page with a "Sign in" button
3. Click "Sign in" - you'll be redirected to the sign-in page
4. Click "Continue with Google"
5. Complete Google OAuth flow
6. You should be redirected back and see your avatar in the navbar

---

## Troubleshooting

### "Invalid Redirect URI" Error
- Make sure the redirect URI in Google Cloud Console matches exactly:
  `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`

### "CORS Error" in Console
- Check that `FRONTEND_URL` in backend `.env` matches your frontend URL exactly
- Make sure backend is running on port 8000

### "401 Unauthorized" on API Calls
- Verify `SUPABASE_JWT_SECRET` is correct in backend `.env`
- Check that you're logged in (token exists)

### Database Tables Not Created
- Make sure you ran the full SQL schema
- Check for any errors in the SQL Editor output

### Google Sign-in Popup Blocked
- Allow popups for localhost in your browser

---

## Next Steps After Setup

Once authentication is working, you can:

1. **Test guest-to-user migration**: Browse as guest, then sign in
2. **Check database**: View `users`, `guest_sessions` tables in Supabase
3. **Implement video interactions**: Use the `interactions` table
4. **Build recommendation engine**: Use `interaction_count` and `recommendation_phase` fields

---

## Quick Reference: API Endpoints

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/health` | GET | No | Health check |
| `/api/auth/profile` | GET | Yes | Get user profile |
| `/api/auth/profile` | PUT | Yes | Update profile |
| `/api/auth/logout` | POST | Yes | Logout current session |
| `/api/auth/logout-all` | POST | Yes | Logout all sessions |
| `/api/guest/session` | POST | No | Acknowledge guest session |
| `/api/feed` | GET | Yes | Get personalized feed |
| `/api/guest/feed` | POST | No | Get guest feed |
| `/api/trending` | GET | No | Get trending videos |
| `/api/categories` | GET | No | Get video categories |
| `/api/guest/watch` | POST | No | Track watch events |

---

## Files I've Created

### Backend
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/core/__init__.py`
- `backend/app/core/supabase.py`
- `backend/app/api/__init__.py`
- `backend/app/api/deps.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/guest.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/auth.py`
- `backend/requirements.txt`
- `backend/.env.example`

### Frontend
- `src/lib/supabase.js`
- `src/context/AuthContext.jsx`
- `src/pages/SignIn/SignIn.jsx`
- `src/pages/SignIn/SignIn.css`
- `.env.example`

### Modified
- `src/App.jsx`
- `src/components/Navbar/Navbar.jsx`
- `src/components/Navbar/Navbar.css`
