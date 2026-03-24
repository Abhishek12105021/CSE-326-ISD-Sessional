# YouTube Clone Backend

## Setup and Run

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

The server will be available at http://127.0.0.1:8000

### Using the Run Script
```bash
bash run.sh
```

## Environment Variables
Create a `.env` file with:
```
supabase_url=your_supabase_url
supabase_anon_key=your_anon_key
supabase_service_key=your_service_key
supabase_jwt_secret=your_jwt_secret
frontend_url=http://localhost:3000
```
