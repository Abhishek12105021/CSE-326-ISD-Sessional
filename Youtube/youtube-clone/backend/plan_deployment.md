# Modal Deployment Guide — YouTube Clone Backend

This guide walks you through deploying the FastAPI backend on [Modal](https://modal.com/) from scratch. No prior Modal experience needed — follow each step in order.

---

## Overview

**What Modal does:** Runs your Python app in a managed cloud container. You write a `modal_app.py` file describing the container, and Modal handles the infrastructure.

**What the backend needs at runtime:**
- A container with all Python dependencies installed
- Supabase credentials (injected as environment variables via Modal Secrets)
- A persistent disk volume for the HuggingFace ONNX model (~600 MB) so it isn't re-downloaded on every cold start
- Enough RAM for FAISS index (~150 MB) + model (~600 MB) → we allocate 4 GB

**Files already created for you:**
- `backend/modal_app.py` — the Modal deployment entry point
- `backend/requirements-modal.txt` — lean dependency list (no PyTorch/sentence-transformers; ONNX is the primary backend)

---

## Pre-requisites

- Python 3.9+ installed on your machine
- A [Modal account](https://modal.com/) (free tier available)
- Your Supabase project credentials (from Supabase Dashboard → Project Settings → API)
- Your HuggingFace token (from huggingface.co → Settings → Access Tokens)

---

## Step 1 — Install the Modal CLI

```bash
pip install modal
```

Verify it installed:
```bash
modal --version
```

---

## Step 2 — Authenticate with Modal

```bash
modal token new
```

This opens your browser. Log in (or sign up) with your Modal account. Your token is saved automatically to `~/.modal.toml`. You only need to do this once per machine.

---

## Step 3 — Gather your credentials

You need these values before the next step. Find them at:

| Variable | Where to find it |
|---|---|
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Supabase Dashboard → Project Settings → API → `anon` `public` key |
| `SUPABASE_SERVICE_KEY` | Supabase Dashboard → Project Settings → API → `service_role` `secret` key |
| `SUPABASE_JWT_SECRET` | Supabase Dashboard → Project Settings → API → JWT Secret |
| `HF_TOKEN` | huggingface.co → Settings → Access Tokens → New token (read access is enough) |

---

## Step 4 — Create a Modal Secret

Modal Secrets are how you inject environment variables into your container. This replaces the `.env` file — the backend's `config.py` already reads from OS environment variables, so this works out of the box.

**Replace the placeholder values below with your real credentials:**

```bash
modal secret create youtube-clone-secrets \
  SUPABASE_URL="https://your-project-id.supabase.co" \
  SUPABASE_ANON_KEY="eyJhbGciOi..." \
  SUPABASE_SERVICE_KEY="eyJhbGciOi..." \
  SUPABASE_JWT_SECRET="your-jwt-secret" \
  HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxx" \
  FRONTEND_URL="http://localhost:3000"
```

> **Note on `FRONTEND_URL`:** This controls CORS. Set it to `http://localhost:3000` for now. After you deploy the frontend (e.g., on Vercel), you'll update it to the real frontend URL.

Verify the secret was created:
```bash
modal secret list
```

---

## Step 5 — Deploy

Navigate to the backend folder and run:

```bash
cd path/to/Youtube/youtube-clone/backend
modal deploy modal_app.py
```

**What happens during the first deploy (takes 5–8 minutes):**
1. Modal builds a container image: installs system packages + all Python dependencies
2. Creates a persistent Volume called `youtube-hf-model-cache` for the model files
3. Starts a container (first cold start: FAISS downloads embeddings from Supabase + downloads ONNX model)
4. Prints your live URL at the end

**Expected output at the end:**
```
✓ Created objects.
├── 🔨 Created mount ...
├── 🔨 Created function web
└── 🔨 Created web endpoint for web => https://your-username--youtube-clone-backend-web.modal.run
✓ App deployed! 🎉
```

**Save that URL** — you'll need it for the frontend config.

---

## Step 6 — Verify the deployment

Test the health endpoint:

```bash
curl https://your-username--youtube-clone-backend-web.modal.run/health
```

Expected response:
```json
{"status": "healthy", "auth_provider": "supabase"}
```

If you get a 502/timeout, the container may still be cold-starting. Wait 60 seconds and try again.

To watch the startup logs:
```bash
modal app logs youtube-clone-backend
```

A healthy cold start looks like:
```
[BOOT] Initializing FAISS index...
[FAISS] Fetched 24000 videos, building index...
[FAISS] Index ready: 24000 videos, 1024 dims, 96.0 MB
[BOOT] FAISS ready: 24000 videos, 96.0 MB
[BOOT] Loading embedding model...
[EMBEDDING] Loading HF ONNX repo: lahin001/bge-m3-onnx-int8
[EMBEDDING] Loaded HF ONNX model successfully
```

---

## Step 7 — Update the frontend to use the Modal URL

In your frontend project, set the backend API URL environment variable. For a Next.js project:

```bash
# In youtube-clone/frontend/.env.local (or your deployment platform's env vars)
NEXT_PUBLIC_API_URL=https://your-username--youtube-clone-backend-web.modal.run
```

Wherever you currently call the backend API, make sure it reads from this variable.

---

## Step 8 — Update CORS after deploying the frontend

Once your frontend is live (e.g., on Vercel at `https://your-app.vercel.app`), update the `FRONTEND_URL` in the Modal Secret so CORS works:

```bash
modal secret create youtube-clone-secrets \
  SUPABASE_URL="https://your-project-id.supabase.co" \
  SUPABASE_ANON_KEY="eyJhbGciOi..." \
  SUPABASE_SERVICE_KEY="eyJhbGciOi..." \
  SUPABASE_JWT_SECRET="your-jwt-secret" \
  HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxx" \
  FRONTEND_URL="https://your-app.vercel.app"
```

Then redeploy:
```bash
cd path/to/Youtube/youtube-clone/backend
modal deploy modal_app.py
```

---

## Useful Commands

```bash
# Check deployment status and URL
modal app list

# Stream live logs from the running container
modal app logs youtube-clone-backend

# Stop the app (billing stops when no containers are running)
modal app stop youtube-clone-backend

# Check what's stored in the model Volume
modal volume ls youtube-hf-model-cache /

# List your secrets
modal secret list

# Update a secret (re-run the create command — it overwrites)
modal secret create youtube-clone-secrets KEY="new-value" ...
```

---

## Redeploying After Code Changes

Any time you change backend code (in `app/`), redeploy with:

```bash
cd path/to/Youtube/youtube-clone/backend
modal deploy modal_app.py
```

Modal rebuilds only what changed. Code changes (not dependency changes) deploy in ~30 seconds.

---

## Understanding Cold Starts

**Cold start** = a request hits a container that isn't running yet. The backend needs ~30–60 seconds to:
1. Download FAISS embeddings from Supabase (~3–5 s)
2. Load the ONNX model from the Volume (~5–10 s, since it's already cached after first boot)

The `keep_warm=1` setting in `modal_app.py` keeps one container always alive so users never hit a cold start. This has a small continuous cost.

If you want to reduce costs and accept cold starts (e.g., during development), change `keep_warm=1` to `keep_warm=0` in `modal_app.py` and redeploy.

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `RuntimeError: Missing required env var: SUPABASE_URL` | Secret not created or wrong name | Re-run Step 4 exactly as shown |
| `curl` returns 502 or times out | Container still cold-starting | Wait 60s and retry; check logs with `modal app logs` |
| `ModuleNotFoundError: No module named 'app'` | Wrong working directory in container | Ensure `modal_app.py` is in the `backend/` folder when deploying |
| CORS errors in browser | `FRONTEND_URL` mismatch | Update secret with correct frontend URL, redeploy |
| Model download fails | Invalid or missing `HF_TOKEN` | Verify token has read access on huggingface.co; update secret |
| Image build fails on `faiss-cpu` | Missing `libgomp1` | Already handled in `modal_app.py`; check `apt_install(["libgomp1"])` is there |

---

## Cost Notes

- Modal charges per second of compute (CPU + RAM).
- `keep_warm=1` with 4 GB RAM = continuous billing even with no traffic.
- During development, consider `keep_warm=0` to avoid idle charges.
- Check your usage at: https://modal.com/usage
