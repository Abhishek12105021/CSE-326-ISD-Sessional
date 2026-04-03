import os
import sys
import modal

# ─── App definition ───────────────────────────────────────────────────────────
app = modal.App("youtube-clone-backend")

# ─── Container image ──────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(["libgomp1", "git"])
    .pip_install_from_requirements("requirements-modal.txt")
    .add_local_dir("app", remote_path="/backend/app")
)

# ─── Persistent volume for HuggingFace model cache ────────────────────────────
model_volume = modal.Volume.from_name(
    "youtube-hf-model-cache", create_if_missing=True
)

# ─── FastAPI ASGI entry point ─────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("youtube-clone-secrets")],
    volumes={"/models": model_volume},
    memory=4096,
    timeout=600,
    min_containers=1,  # ✅ updated (was keep_warm)
)
@modal.concurrent(max_inputs=20)  # ✅ NEW replacement
@modal.asgi_app()
def web():
    # Set HF cache directory (uses Modal volume)
    os.environ.setdefault("EMBEDDING_HF_CACHE_DIR", "/models/hf_cache")

    # Ensure Python can find your app module
    sys.path.insert(0, "/backend")

    # Import FastAPI app
    from app.main import app as fastapi_app
    return fastapi_app