"""
Query embedding service with ONNX-first loading and safe fallback.

Startup strategy:
1) Try loading quantized ONNX model from Hugging Face repo (fast path)
2) If unavailable/failing, fall back to local SentenceTransformer int8 quantization

Key:
- MODEL: Global sentence-transformer model (fallback backend)
- embed_query(text): Convert single query to normalized embedding
- embed_batch(texts): Batch embed multiple queries
"""
import os
from pathlib import Path

import numpy as np

# ==================== GLOBAL MODEL ====================

MODEL = None  # SentenceTransformer fallback model
MODEL_BACKEND = None  # "onnx_hf" or "sentence_transformer"
ORT_SESSION = None
TOKENIZER = None
ORT_INPUT_NAMES = set()

HF_ONNX_REPO_ID = os.getenv("EMBEDDING_HF_REPO_ID", "lahin001/bge-m3-onnx-int8")
HF_ONNX_FILENAME = os.getenv("EMBEDDING_HF_ONNX_FILE", "model_quantized.onnx")
HF_ONNX_REVISION = os.getenv("EMBEDDING_HF_REVISION")
HF_CACHE_DIR = os.getenv("EMBEDDING_HF_CACHE_DIR", "./models/hf_cache")
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
EMBEDDING_ALLOW_FALLBACK = os.getenv("EMBEDDING_ALLOW_FALLBACK", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


# ==================== INITIALIZATION ====================


async def load_model():
    """
    Load embedding backend at server startup.

    Priority:
    - Primary: Hugging Face ONNX repo (lahin001/bge-m3-onnx-int8)
    - Fallback: local dynamic int8 quantization from BAAI/bge-m3
    """
    global MODEL_BACKEND

    if MODEL_BACKEND is not None:
        print(f"[EMBEDDING] Model already loaded ({MODEL_BACKEND})")
        return

    try:
        _load_hf_onnx_backend()
        return
    except Exception as e:
        print(f"[EMBEDDING WARNING] HF ONNX load failed: {e}")
        if not EMBEDDING_ALLOW_FALLBACK:
            raise RuntimeError(
                "HF ONNX load failed and fallback is disabled. "
                "Set EMBEDDING_ALLOW_FALLBACK=true to enable fallback."
            ) from e

        print("[EMBEDDING] Falling back to local SentenceTransformer quantization...")

    _load_sentence_transformer_fallback()


def _load_hf_onnx_backend() -> None:
    """Download/load quantized ONNX artifacts from Hugging Face and initialize ORT."""
    global MODEL_BACKEND, ORT_SESSION, TOKENIZER, ORT_INPUT_NAMES

    import onnxruntime as ort
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer

    print(f"[EMBEDDING] Loading HF ONNX repo: {HF_ONNX_REPO_ID}")

    local_dir = snapshot_download(
        repo_id=HF_ONNX_REPO_ID,
        revision=HF_ONNX_REVISION,
        cache_dir=HF_CACHE_DIR,
        token=HF_TOKEN,
    )
    local_dir_path = Path(local_dir)

    onnx_path = local_dir_path / HF_ONNX_FILENAME
    if not onnx_path.exists():
        onnx_candidates = sorted(local_dir_path.glob("*.onnx"))
        if not onnx_candidates:
            raise FileNotFoundError(
                f"No ONNX file found in downloaded repo: {local_dir_path}"
            )
        onnx_path = onnx_candidates[0]

    TOKENIZER = AutoTokenizer.from_pretrained(local_dir_path, local_files_only=True)
    ORT_SESSION = ort.InferenceSession(
        str(onnx_path), providers=["CPUExecutionProvider"]
    )
    ORT_INPUT_NAMES = {i.name for i in ORT_SESSION.get_inputs()}

    MODEL_BACKEND = "onnx_hf"
    print(f"[EMBEDDING] Loaded HF ONNX model from: {onnx_path}")


def _load_sentence_transformer_fallback() -> None:
    """Fallback backend: dynamic int8 quantized SentenceTransformer on CPU."""
    global MODEL, MODEL_BACKEND

    try:
        import torch
        from sentence_transformers import SentenceTransformer
        from torch.nn import Linear
        from torch.quantization import quantize_dynamic

        print("[EMBEDDING] Fallback stage 1/3: downloading/loading BAAI/bge-m3 on CPU...")

        # Load bge-m3 model in float32 first
        MODEL = SentenceTransformer('BAAI/bge-m3', device='cpu')
        print("[EMBEDDING] Fallback stage 2/3: applying dynamic int8 quantization...")

        # Quantize the underlying transformer model (inside SentenceTransformer)
        quantized_model = quantize_dynamic(
            MODEL[0],  # First module is usually the transformer
            {Linear},  # Quantize linear layers
            dtype=torch.qint8  # 8-bit integer quantization
        )

        # Replace the quantized model back
        MODEL[0] = quantized_model
        MODEL_BACKEND = "sentence_transformer"

        print("[EMBEDDING] Fallback stage 3/3: model ready")
        print("[EMBEDDING] Model loaded successfully (int8 quantized, ~600MB)")
        print("[EMBEDDING] Device: cpu | Precision: int8 (dynamic)")

    except Exception as e:
        print(f"[EMBEDDING ERROR] Failed to load quantized model: {e}")
        print("[EMBEDDING] Falling back to float16 precision...")

        try:
            from sentence_transformers import SentenceTransformer
            MODEL = SentenceTransformer('BAAI/bge-m3', device='cpu')
            MODEL = MODEL.half()
            MODEL_BACKEND = "sentence_transformer"
            print("[EMBEDDING] Float16 model loaded successfully (~1.1GB)")
        except Exception as e2:
            print(f"[EMBEDDING ERROR] Float16 also failed: {e2}")
            raise


def _onnx_mean_pooling(last_hidden: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """Mean-pool token embeddings using attention mask."""
    mask = attention_mask[..., None].astype(np.float32)
    summed = (last_hidden * mask).sum(axis=1)
    denom = np.clip(mask.sum(axis=1), 1e-10, None)
    return summed / denom


def _embed_batch_onnx(texts: list[str]) -> np.ndarray:
    """Embed texts using ONNX Runtime + tokenizer artifacts from HF repo."""
    if ORT_SESSION is None or TOKENIZER is None:
        raise RuntimeError("ONNX backend is not initialized")

    inputs = TOKENIZER(texts, padding=True, truncation=True, return_tensors="np")
    ort_inputs = {name: inputs[name] for name in ORT_INPUT_NAMES if name in inputs}

    outputs = ORT_SESSION.run(None, ort_inputs)
    if not outputs:
        raise RuntimeError("ONNX inference returned no outputs")

    last_hidden = np.asarray(outputs[0], dtype=np.float32)
    if "attention_mask" in inputs:
        embeddings = _onnx_mean_pooling(last_hidden, inputs["attention_mask"])
    else:
        embeddings = last_hidden.mean(axis=1)

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (norms + 1e-10)
    return embeddings.astype(np.float32)


# ==================== EMBEDDING FUNCTIONS ====================


def embed_query(text: str) -> np.ndarray:
    """
    Embed a single search query to normalized 1024-dim vector.

    Args:
        text: Search query (e.g., "gaming videos")

    Returns:
        Normalized 1024-dim numpy array (float32)

    Raises:
        RuntimeError: If model not loaded
        ValueError: If text is empty
    """
    global MODEL, MODEL_BACKEND

    if MODEL_BACKEND is None:
        raise RuntimeError("Embedding model not loaded. Call load_model() first.")

    if not text or not text.strip():
        raise ValueError("Query text cannot be empty")

    if MODEL_BACKEND == "onnx_hf":
        return _embed_batch_onnx([text])[0]

    # SentenceTransformer fallback path
    if MODEL is None:
        raise RuntimeError("SentenceTransformer backend is not initialized")
    embedding = MODEL.encode(text, convert_to_numpy=True).astype(np.float32)

    # Normalize for cosine similarity
    norm = np.linalg.norm(embedding)
    if norm < 1e-10:
        raise ValueError("Query embedding has zero norm")

    embedding = embedding / norm

    return embedding


def embed_batch(texts: list[str]) -> np.ndarray:
    """
    Batch embed multiple queries (more efficient than calling embed_query N times).

    Args:
        texts: List of query strings

    Returns:
        N x 1024 normalized numpy array (float32)
    """
    global MODEL, MODEL_BACKEND

    if MODEL_BACKEND is None:
        raise RuntimeError("Embedding model not loaded. Call load_model() first.")

    if not texts:
        raise ValueError("Texts list cannot be empty")

    if MODEL_BACKEND == "onnx_hf":
        return _embed_batch_onnx(texts)

    # SentenceTransformer fallback path
    if MODEL is None:
        raise RuntimeError("SentenceTransformer backend is not initialized")
    embeddings = MODEL.encode(texts, convert_to_numpy=True).astype(np.float32)

    # Normalize each embedding
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (norms + 1e-10)

    return embeddings



