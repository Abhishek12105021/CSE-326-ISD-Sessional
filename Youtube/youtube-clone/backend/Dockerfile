# YouTube Clone Backend - FastAPI + FAISS + ONNX
# Optimized for Render/Railway deployment

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies for FAISS/ONNX
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser . .

# Pre-download HuggingFace model at build time (~150MB)
# This eliminates cold-start delays in production
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='lahin001/bge-m3-onnx-int8', local_dir='./models/bge-m3-onnx-int8', local_dir_use_symlinks=False)"

# Set model cache directory to the pre-downloaded location
ENV EMBEDDING_HF_CACHE_DIR=/app/models

# Switch to non-root user
USER appuser

# Expose port (Render/Railway will set PORT env var)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${PORT:-8000}/health || exit 1'

# Start command - uses $PORT from Render/Railway, defaults to 8000
CMD ["sh", "-c", "gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 120 --keep-alive 5"]
