# Vercel Deployment Guide — YouTube Clone Frontend

Deploy the React frontend to Vercel directly from your terminal — no GitHub setup required.

---

## Overview

**Stack:** React 18 + Vite + HashRouter  
**Hosting:** Vercel (free tier)  
**Method:** Vercel CLI (`vercel --prod`)

**Environment variables you need before starting:**

| Variable | Where to find it |
|---|---|
| `VITE_SUPABASE_URL` | Supabase Dashboard → Project Settings → API → Project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase Dashboard → Project Settings → API → `anon` `public` key |
| `VITE_API_URL` | Your Modal backend URL from backend deployment |

---

## Step 1 — Install the Vercel CLI

```bash
npm install -g vercel
```

Verify:
```bash
vercel --version
```

---

## Step 2 — Log in to Vercel

```bash
vercel login
```

This opens your browser. Sign up / log in at vercel.com, then come back to the terminal. Your credentials are saved automatically.

---

## Step 3 — Navigate to the frontend folder

```bash
cd path/to/Youtube/youtube-clone/frontend
```

---

## Step 4 — Set up your local `.env` with production values

The Vercel CLI reads your local `.env` file during setup. Edit `frontend/.env` so it points to the production backend:

```
VITE_SUPABASE_URL=https://your-project-id.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOi...
VITE_API_URL=https://nawrizaturjo03--youtube-clone-backend-web.modal.run
```

Replace the `VITE_API_URL` with your actual Modal backend URL.

> These values get embedded into the built bundle at deploy time. They are NOT secret — they are visible in the browser bundle. That is normal and expected for a Vite frontend.

---

## Step 5 — Deploy to production

From inside the `frontend/` folder, run:

```bash
vercel --prod
```

**First-time setup:** Vercel will ask you a few questions. Answer like this:

```
? Set up and deploy "frontend"? → Y
? Which scope? → your account name
? Link to existing project? → N
? What's your project's name? → youtube-clone-frontend   (or any name you want)
? In which directory is your code located? → ./            (press Enter, current dir)
? Want to modify these settings? → N
```

Vercel auto-detects Vite and sets:
- Build command: `vite build`
- Output directory: `dist`
- Install command: `npm install`

**What happens next:**
1. Vercel uploads your source code
2. Runs `npm install` + `vite build` on their servers
3. Publishes `dist/` globally

You get a URL at the end like:
```
https://youtube-clone-frontend.vercel.app
```

**Save that URL** — you need it for the next two steps.

---

## Step 6 — Add environment variables to Vercel

The CLI doesn't automatically push your `.env` to Vercel's servers (it only uses it locally). Add each variable manually:

```bash
vercel env add VITE_SUPABASE_URL
# Paste value when prompted, select: Production, Preview, Development → press Enter

vercel env add VITE_SUPABASE_ANON_KEY
# Paste value when prompted

vercel env add VITE_API_URL
# Paste your Modal backend URL
```

Then **redeploy** so the build picks up the env vars:

```bash
vercel --prod
```

> This second deploy is required because environment variables are embedded at build time. The first deploy may have used empty values if env vars weren't set yet.

---

## Step 7 — Update Supabase OAuth redirect URLs

Google sign-in won't work until Supabase knows your Vercel domain.

1. Go to [Supabase Dashboard](https://supabase.com/dashboard) → your project
2. **Authentication → URL Configuration**
3. Under **Redirect URLs**, add your Vercel URL:
   ```
   https://youtube-clone-frontend.vercel.app
   ```
4. Click **Save**

---

## Step 8 — Update backend CORS to allow your frontend URL

The backend blocks requests from unknown origins. Update it:

```bash
# From the backend folder
modal secret create youtube-clone-secrets \
  SUPABASE_URL="https://your-project-id.supabase.co" \
  SUPABASE_ANON_KEY="eyJhbGciOi..." \
  SUPABASE_SERVICE_KEY="eyJhbGciOi..." \
  SUPABASE_JWT_SECRET="your-jwt-secret" \
  HF_TOKEN="hf_xxxxxxxxxx" \
  FRONTEND_URL="https://youtube-clone-frontend.vercel.app"
```

Then redeploy the backend:

```bash
cd path/to/Youtube/youtube-clone/backend
modal deploy modal_app.py
```

---

## Step 9 — Verify

Open your Vercel URL and check:

- [ ] Home page loads with videos
- [ ] Search returns results
- [ ] Guest feed works (no login needed)
- [ ] Google sign-in completes without error
- [ ] After sign-in, personalized feed loads

---

## Future redeploys

Any time you change frontend code, redeploy with one command from the `frontend/` folder:

```bash
vercel --prod
```

---

## Useful CLI commands

```bash
vercel ls                    # List all your deployments
vercel logs youtube-clone-frontend   # View deployment logs
vercel env ls                # List env vars set on the project
vercel env rm VITE_API_URL   # Remove an env var
vercel --prod                # Redeploy production
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Blank white page | Env vars not set — run Step 6 then redeploy |
| API calls fail / CORS error | Backend `FRONTEND_URL` still set to `localhost` — follow Step 8 |
| Google sign-in redirect error | Vercel URL not in Supabase — follow Step 7 |
| "vite: command not found" during build | Make sure you're deploying from `frontend/` folder, not repo root |
| Build error: missing module | Run `npm install` locally first to verify no broken deps |
