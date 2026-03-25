# YouTube Clone Backend

A FastAPI backend service for YouTube Clone featuring a sophisticated **3-phase recommendation engine** with cold-start strategy.

## Features

✅ **3-Phase Recommendation Engine**: Cold start → Warm-up → Personalized
✅ **24,499+ Video Database**: With BGE-M3 (1024-dim) embeddings
✅ **Supabase Integration**: PostgreSQL with pgvector for similarity search
✅ **Guest & Authenticated Users**: Separate personalization strategies
✅ **Watch History Tracking**: INSERT on click, UPDATE with YouTube API duration
✅ **Country Affinity**: Intelligent foreign content discovery
✅ **JWT Authentication**: Secure API access for authenticated features

---

## API Endpoints

### Feed Generation
- `GET /api/feed` - Personalized feed (authenticated users)
- `POST /api/guest/feed` - Guest feed with localStorage history
- `GET /api/trending` - Pure trending videos

### Utilities
- `GET /api/categories` - Available video categories
- `GET /health` - Health check

### Guest Interactions
- `POST /api/guest/watch` - Track watch events (INSERT/UPDATE)
- `POST /api/guest/session` - Session health check

### Authentication
- `GET /api/auth/profile` - Get user profile
- `PUT /api/auth/profile` - Update user profile
- `POST /api/auth/logout` - Logout current session
- `POST /api/auth/logout-all` - Logout all sessions

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Setup
Create `.env` file:
```env
supabase_url=https://xxxxx.supabase.co
supabase_anon_key=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
supabase_service_key=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
supabase_jwt_secret=your-jwt-secret
frontend_url=http://localhost:3000
```

### 3. Start Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

Server available at: **http://localhost:8000**

### 4. Quick Test
```bash
# Health check
curl http://localhost:8000/health

# Cold start feed (guest)
curl -X POST http://localhost:8000/api/guest/feed \
  -H "Content-Type: application/json" \
  -d '{"guest_uuid":"test-123","region":"US","watched_video_ids":[]}'
```

---

## Project Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── recommendation.py      # 3-phase feed generation logic
│   │   └── supabase.py            # Supabase client (existing)
│   ├── api/
│   │   ├── routes/
│   │   │   ├── feed.py            # Authenticated feed endpoints
│   │   │   ├── guest.py           # Guest feed + watch endpoints
│   │   │   ├── auth.py            # Authentication endpoints (existing)
│   │   │   └── deps.py            # JWT verification (existing)
│   ├── schemas/
│   │   ├── feed.py                # Feed request/response models
│   │   └── auth.py                # Auth models (existing)
│   ├── utils/
│   │   └── formatters.py          # View/timestamp/avatar formatters
│   ├── config.py                  # Settings management (existing)
│   ├── db.py                      # Database functions + RPC callers
│   └── main.py                    # FastAPI app entry point
├── requirements.txt               # Python dependencies
├── .env                          # Environment variables (create)
├── API_DOCUMENTATION.md          # Complete API reference
├── FEEDGENERATION_README.md      # Feed system overview
└── README.md                     # This file
```

---

## Database Schema

### Key Tables
- **`videos`** (24,499 rows): Video metadata + 1024-dim embeddings (BGE-M3)
- **`watch_history`**: User/guest watch tracking (INSERT on click, UPDATE on leave)
- **`users`**: User profiles with region information
- **`user_preferences`**: Theme, recommendation phase tracking
- **`guest_sessions`**: Guest UUID tracking

### RPC Functions
- **`search_videos(embedding, country, k)`**: Semantic similarity search using pgvector
- **`get_trending(country, k, pool_size, exclude_ids)`**: Randomized trending with exclusion

---

## Recommendation Phases

### Phase 1: Cold Start (0 interactions)
```
Strategy: 50% Global + 50% Local Trending
SQL Calls: get_trending(global) + get_trending(user_region)
```

### Phase 2: Warm-Up (1-4 interactions)
```
Strategy: 30% Vector + 40% Trending + 30% Local
SQL Calls: search_videos(taste) + 2x get_trending()
```

### Phase 3: Personalized (5+ interactions)
```
Strategy: 4-Bucket Distribution
- Bucket A (60%): search_videos(taste, user_region)
- Bucket B (20%): search_videos(taste, foreign_countries) [affinity-weighted]
- Bucket C (10%): get_trending(user_region)
- Bucket D (10%): get_trending(global_mix)
SQL Calls: 1-9 search_videos() + 2x get_trending()
```

---

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload)
uvicorn app.main:app --reload --port 8000

# Run for production
gunicorn app.main:app --workers 4 --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker

# Test specific endpoint
curl -X POST http://localhost:8000/api/guest/feed \
  -H "Content-Type: application/json" \
  -d '{"guest_uuid":"test","region":"US","watched_video_ids":[]}'

# Check logs (development)
tail -f logs/app.log
```

---

## Documentation

- **[API_DOCUMENTATION.md](./API_DOCUMENTATION.md)** - Complete API reference with examples
- **[FEEDGENERATION_README.md](./FEEDGENERATION_README.md)** - Detailed feed system overview
- **Interactive API Docs**: http://localhost:8000/docs (Swagger UI)
- **OpenAPI Schema**: http://localhost:8000/openapi.json

---

## Troubleshooting

### Common Issues

**"RPC function not found"**:
- Run SQL scripts in `../Data/recommend.sql` to create RPC functions
- Check Supabase dashboard → SQL Editor

**"Empty feed returned"**:
- Verify videos table has 24,499 rows
- Check if embeddings column is populated
- Test RPC functions manually in Supabase SQL editor

**"Slow response times"**:
- Phase 3 can be slow (requires country affinity calculation)
- Consider implementing caching or using edge functions

**Connection errors**:
- Verify `.env` file has correct Supabase credentials
- Check network connectivity to Supabase project

### Debug Mode
```bash
# Enable debug logging
PYTHONPATH=. python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
import uvicorn
uvicorn.run('app.main:app', host='0.0.0.0', port=8000, log_level='debug')
"
```

---

## Performance Metrics

| Phase | Avg Response Time | SQL Calls | Memory Usage |
|-------|-------------------|-----------|--------------|
| Phase 1 | ~200ms | 2 RPC calls | ~5MB |
| Phase 2 | ~400ms | 3 RPC + UUID fetch | ~10MB |
| Phase 3 | ~800ms | 11+ RPC + affinity calc | ~50MB |

**Note**: Phase 3 can be slower due to country affinity calculation (fetches 2,500+ embeddings per country).

---

## Deployment

### Production Checklist
- [ ] Set environment variables in production
- [ ] Use production Supabase instance
- [ ] Configure proper CORS origins
- [ ] Enable logging to file
- [ ] Set up monitoring (health checks)
- [ ] Configure rate limiting
- [ ] Set up SSL/TLS
- [ ] Use gunicorn with multiple workers

### Docker Support (Future)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

---

## Contributing

1. Follow PEP 8 style guidelines
2. Add type hints to new functions
3. Update documentation for any API changes
4. Test all changes with Postman before submitting
5. Update version number in `main.py` for releases

---

**Version**: 1.0.0
**Last Updated**: March 26, 2026
**Python**: 3.8+
**Framework**: FastAPI 0.109.0
