# Run Instructions

This file explains how to run the `youtube-clone` project on a local machine.

The project now has two separate parts:

- `frontend/` - React + Vite app
- `backend/` - FastAPI API

You need to run both.

## Recommended Way

If you are using Windows PowerShell, use the included run scripts.

### Terminal 1: Start the Backend

```powershell
cd "C:\D drive\L3-T2\CSE326 Information System Design Sessional\CSE-326-ISD-Sessional\Youtube\youtube-clone\backend"
Set-ExecutionPolicy -Scope Process Bypass
.\run.ps1
```

What this does:

- creates `.venv` with Python 3.12 if it does not exist
- installs backend requirements
- starts FastAPI on port `8000`

### Terminal 2: Start the Frontend

```powershell
cd "C:\D drive\L3-T2\CSE326 Information System Design Sessional\CSE-326-ISD-Sessional\Youtube\youtube-clone\frontend"
Set-ExecutionPolicy -Scope Process Bypass
.\run.ps1
```

What this does:

- installs `node_modules` if missing
- starts Vite on port `3000`

### Open the App

Open:

```text
http://localhost:3000
```

Backend health check:

```text
http://127.0.0.1:8000/health
```

## Manual Way

Use this if you do not want to use the scripts.

### Backend Manual Commands

```powershell
cd "C:\D drive\L3-T2\CSE326 Information System Design Sessional\CSE-326-ISD-Sessional\Youtube\youtube-clone\backend"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Important:

- use `python -m uvicorn`
- do not use plain `uvicorn app.main:app ...`

This avoids global Python/package mismatch issues.

### Frontend Manual Commands

```powershell
cd "C:\D drive\L3-T2\CSE326 Information System Design Sessional\CSE-326-ISD-Sessional\Youtube\youtube-clone\frontend"
npm install
npm run dev
```

## Required Environment Files

Make sure these files exist:

- `backend/.env`
- `frontend/.env`

### Backend `.env`

File:

```text
youtube-clone/backend/.env
```

Example:

```env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
FRONTEND_URL=http://localhost:3000
```

### Frontend `.env`

File:

```text
youtube-clone/frontend/.env
```

Example:

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-public-key
VITE_API_URL=http://localhost:8000
```

## Important Note About Supabase Values

If your backend `.env` still contains placeholders like:

- `YOUR_PROJECT_REF`
- `your-anon-public-key`
- `your-service-role-key`
- `your-jwt-secret`

then:

- the backend may start
- but auth and database-backed API calls will fail

So before testing login, replace those placeholders with real values from Supabase.

## Expected Ports

- frontend: `3000`
- backend: `8000`

## How to Stop

Press:

```text
Ctrl + C
```

in each terminal.

## Quick Troubleshooting

### PowerShell says script execution is disabled

Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Then run the script again.

### Backend says module is missing

Run the backend through the project venv:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

or use:

```powershell
.\run.ps1
```

### Backend says Supabase config is invalid

Check `backend/.env` and replace placeholder values with real values from Supabase.

### Frontend cannot reach backend

Check:

```env
VITE_API_URL=http://localhost:8000
```

inside `frontend/.env`.

### CORS error from backend

Check:

```env
FRONTEND_URL=http://localhost:3000
```

inside `backend/.env`.

## Short Version

If everything is already configured, just run:

### Backend

```powershell
cd "C:\D drive\L3-T2\CSE326 Information System Design Sessional\CSE-326-ISD-Sessional\Youtube\youtube-clone\backend"
.\run.ps1
```

### Frontend

```powershell
cd "C:\D drive\L3-T2\CSE326 Information System Design Sessional\CSE-326-ISD-Sessional\Youtube\youtube-clone\frontend"
.\run.ps1
```

Then open:

```text
http://localhost:3000
```
