# CI/CD Context Card — YouTube Clone Project

> Paste this block at the TOP of every new CI/CD chat session.

---

## Stack Overview

| Layer       | Platform                         | Config File                               |
| ----------- | -------------------------------- | ----------------------------------------- |
| Frontend    | Vercel (primary) / Netlify (alt) | `vercel.json`, `netlify.toml`             |
| Backend API | Render / Railway (FastAPI)       | No Dockerfile yet — must create           |
| Database    | Supabase (PostgreSQL + pgvector) | SQL files in `Data/`                      |
| ML Model    | HuggingFace Hub                  | `lahin001/bge-m3-onnx-int8` (public repo) |

---

## Repo Structure (key paths)

```
Youtube/
├── Data/                             # SQL schemas + ML datasets
│   ├── schema.sql                    # Videos table + pgvector HNSW index
│   ├── recommend.sql                 # RPC functions
│   └── user_auth.sql
└── youtube-clone/
    ├── vercel.json                   # Vercel SPA config
    ├── netlify.toml
    ├── frontend/                     # React + Vite
    │   ├── package.json
    │   ├── vite.config.js
    │   └── src/
    └── backend/                      # FastAPI + ONNX
        ├── requirements.txt
        └── app/
            ├── main.py               # FastAPI + FAISS lifespan
            ├── core/embedding_service.py  # HF ONNX loading
            └── core/faiss_manager.py
```

---

## Build & Run Commands

### Frontend

```bash
cd Youtube/youtube-clone/frontend
npm install
npm run build          # → dist/
npm run dev            # port 3000
```

### Backend

```bash
cd Youtube/youtube-clone/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # dev
gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT  # prod
```

---

## Environment Variables

### Frontend (.env)

| Variable               | Required | Notes                                          |
| ---------------------- | -------- | ---------------------------------------------- |
| VITE_SUPABASE_URL      | Yes      | Supabase project URL                           |
| VITE_SUPABASE_ANON_KEY | Yes      | Supabase public anon key                       |
| VITE_API_URL           | Yes      | Backend URL (e.g. https://your-app.render.com) |

### Backend (.env)

| Variable                 | Required | Notes                                      |
| ------------------------ | -------- | ------------------------------------------ |
| SUPABASE_URL             | Yes      |                                            |
| SUPABASE_ANON_KEY        | Yes      |                                            |
| SUPABASE_SERVICE_KEY     | Yes      | Admin key                                  |
| SUPABASE_JWT_SECRET      | Yes      | For token verification                     |
| FRONTEND_URL             | Yes      | CORS — must match Vercel domain exactly    |
| EMBEDDING_HF_REPO_ID     | No       | Default: lahin001/bge-m3-onnx-int8         |
| EMBEDDING_HF_ONNX_FILE   | No       | Default: model_quantized.onnx              |
| EMBEDDING_HF_CACHE_DIR   | No       | Default: ./models/hf_cache                 |
| HF_TOKEN                 | No       | Only if private HF repo                    |
| EMBEDDING_ALLOW_FALLBACK | No       | Default: true (uses sentence-transformers) |

---

## GitHub Secrets Needed (to add in repo settings)

```
VERCEL_TOKEN
VERCEL_ORG_ID
VERCEL_PROJECT_ID
RENDER_API_KEY (or RAILWAY_TOKEN)
RENDER_SERVICE_ID
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_KEY
SUPABASE_JWT_SECRET
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
VITE_API_URL
FRONTEND_URL
```

---

## CI/CD Gaps — Must Create

| Item                             | Priority | Status         |
| -------------------------------- | -------- | -------------- |
| `backend/Dockerfile`             | HIGH     | ❌ Not created |
| `.github/workflows/frontend.yml` | HIGH     | ❌ Not created |
| `.github/workflows/backend.yml`  | HIGH     | ❌ Not created |
| `.github/workflows/supabase.yml` | MEDIUM   | ❌ Not created |
| `pytest` test suite (backend)    | HIGH     | ❌ Missing     |
| `vitest` test suite (frontend)   | HIGH     | ❌ Missing     |
| ESLint config (frontend)         | MEDIUM   | ❌ Missing     |
| Ruff/Black config (backend)      | MEDIUM   | ❌ Missing     |

---

## Special Considerations

- **ML model cold start**: Backend downloads ~100–150MB ONNX model on first start. Consider pre-baking into Docker image with `huggingface_hub.snapshot_download()` at build time.
- **FAISS index**: Initialized at app startup via lifespan in `main.py`. Must be available at runtime.
- **CORS**: `FRONTEND_URL` env var must match deployed Vercel domain EXACTLY (no trailing slash).
- **Supabase migrations**: Currently manual (run SQL in Supabase dashboard). CI should validate SQL syntax but not auto-apply to production.
- **HuggingFace model**: `lahin001/bge-m3-onnx-int8` is a PUBLIC repo — no HF_TOKEN needed for CI.
- **Python version**: 3.11 recommended. FAISS + ONNX have platform-specific wheels.
- **Node version**: 18+ required for Vite 5.

---

## Decisions Log

<!-- Add entries as chats progress -->

- [ ] Choose backend hosting: Render vs Railway (decide in Chat 2)
- [ ] Decide: pre-bake HF model in Docker or download at runtime
- [ ] Decide: Supabase migrations strategy (manual vs Supabase CLI in CI)

---

## Chat Progress Tracker

| Chat   | Goal                                           | Status  |
| ------ | ---------------------------------------------- | ------- |
| Chat 1 | Codebase analysis + this context card          | ✅ Done |
| Chat 2 | `backend/Dockerfile` + backend deploy workflow | ⏳ Next |
| Chat 3 | Frontend Vercel CI/CD workflow                 | ⬜      |
| Chat 4 | Supabase migration CI + secrets setup          | ⬜      |
| Chat 5 | Lint, tests, full integration + review         | ⬜      |

---

## Starter Prompt for Next Chat

```
Paste this entire CICD_CONTEXT_CARD.md, then add:

"We are on Chat 2. Chat 1 completed: full codebase analysis.
Today's goal: Create backend/Dockerfile and .github/workflows/backend.yml
for deploying the FastAPI backend to [Render/Railway].
Key constraints: Python 3.11, FAISS-cpu, ONNX runtime, HuggingFace model
lahin001/bge-m3-onnx-int8 (~150MB). Consider pre-baking the model in the
Docker image. The health endpoint is at /health."
```
