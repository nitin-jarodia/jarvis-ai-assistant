"""
File Service for Jarvis AI Assistant.

Handles:
  - Text extraction from PDF and TXT files
  - Text chunking with overlap
  - Sentence embedding via sentence-transformers (lazy singleton)
  - FAISS vector index building and in-memory caching
  - Semantic chunk retrieval for RAG
"""

from __future__ import annotations

import io
import logging
import struct
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────────

CHUNK_SIZE    = 600    # characters (~150 tokens)
CHUNK_OVERLAP = 100    # characters of overlap between chunks
TOP_K_CHUNKS  = 4      # chunks sent to the LLM per query
EMBED_MODEL   = "all-MiniLM-L6-v2"  # 80 MB, 384-dim, fast
EMBED_DIM     = 384

# ─── Lazy Singletons ──────────────────────────────────────────────────────────

_embed_model = None   # sentence_transformers.SentenceTransformer

def _get_embed_model():
    """Lazy-load the sentence-transformer model once."""
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer  # noqa
        logger.info("Loading embedding model '%s'…", EMBED_MODEL)
        _embed_model = SentenceTransformer(EMBED_MODEL)
        logger.info("Embedding model loaded.")
    return _embed_model


# ─── Index Cache ────────────────────────────────────────────────────────
# Maps file_id → (np.ndarray matrix, list[chunk_text])

_index_cache: dict[str, tuple[np.ndarray, list[str]]] = {}


def evict_index(file_id: str) -> None:
    """Remove a file's matrix index from memory."""
    _index_cache.pop(file_id, None)
    logger.debug("Evicted FAISS index for file_id=%s", file_id)


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text(file_content: bytes, filename: str) -> str:
    """Extract plain text from PDF or TXT file bytes."""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "txt":
        return _extract_txt(file_content)
    elif ext == "pdf":
        return _extract_pdf(file_content)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")


def _extract_txt(content: bytes) -> str:
    try:
        return content.decode("utf-8", errors="replace").strip()
    except Exception as e:
        raise ValueError(f"Failed to read TXT file: {e}") from e


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader  # noqa
        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        full_text = "\n\n".join(pages)
        if not full_text.strip():
            raise ValueError("PDF appears to have no extractable text (may be scanned).")
        return full_text
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {e}") from e


# ─── Text Chunking ────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks.
    Strategy: character-level sliding window with sentence-boundary preference.
    """
    text = _clean_text(text)
    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + CHUNK_SIZE, length)

        # Prefer to break at sentence/paragraph boundary within last 100 chars
        if end < length:
            boundary = _find_boundary(text, end, lookback=100)
            if boundary:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break
        start = end - CHUNK_OVERLAP  # overlap

    return chunks


def _clean_text(text: str) -> str:
    """Normalize whitespace and remove junk characters."""
    import re
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Normalize tabs and carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    # Collapse multiple spaces (not newlines)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


def _find_boundary(text: str, pos: int, lookback: int) -> int | None:
    """Find the last sentence/paragraph boundary before pos."""
    window = text[max(0, pos - lookback): pos]
    for sep in ("\n\n", ".\n", ". ", "? ", "! ", "\n"):
        idx = window.rfind(sep)
        if idx != -1:
            return pos - lookback + idx + len(sep)
    return None


# ─── Embeddings ───────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> np.ndarray:
    """
    Embed a list of texts.
    Returns float32 array of shape (N, EMBED_DIM), L2-normalized.
    """
    model = _get_embed_model()
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return vectors.astype(np.float32)


def embedding_to_bytes(vec: np.ndarray) -> bytes:
    """Serialize a float32 embedding vector to bytes for SQLite storage."""
    return vec.astype(np.float32).tobytes()


def bytes_to_embedding(blob: bytes) -> np.ndarray:
    """Deserialize bytes back to a float32 numpy vector."""
    n = len(blob) // 4  # float32 = 4 bytes
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)


# ─── Search Index ─────────────────────────────────────────────────────────────

def _load_index_from_db(file_id: str, db: "Session") -> tuple[np.ndarray, list[str]] | None:
    """Load all chunks for a file_id from the DB and build the NumPy matrix."""
    from backend import crud  # local import to avoid circular dependency

    chunks = crud.get_file_chunks(db, file_id)
    if not chunks:
        return None

    texts: list[str] = []
    embeddings: list[np.ndarray] = []

    for chunk in chunks:
        texts.append(chunk.content)
        embeddings.append(bytes_to_embedding(chunk.embedding))

    matrix = np.stack(embeddings, axis=0).astype(np.float32)
    return matrix, texts


# ─── Retrieval ────────────────────────────────────────────────────────────────

def retrieve_chunks(query: str, file_id: str, db: "Session", top_k: int = TOP_K_CHUNKS) -> list[str]:
    """
    Embed query, perform cosine similarity, return top-k most relevant text chunks.
    Index matrix is loaded from DB on first call then cached in memory.
    """
    # Build or retrieve cached matrix
    if file_id not in _index_cache:
        logger.info("Building NumPy matrix index for file_id=%s…", file_id)
        result = _load_index_from_db(file_id, db)
        if result is None:
            logger.warning("No chunks found in DB for file_id=%s", file_id)
            return []
        _index_cache[file_id] = result
        logger.info("Matrix index cached for file_id=%s (%d chunks)", file_id, len(result[1]))

    matrix, chunk_texts = _index_cache[file_id]

    # Embed the query
    q_vec = embed_texts([query])  # shape (1, EMBED_DIM)

    # Search using NumPy dot product (since vectors are L2-normalized, dot product == cosine similarity)
    # q_vec: (1, dim), matrix: (N, dim). Result: (1, N)
    scores = np.dot(q_vec, matrix.T)[0]
    
    # Get top-k indices
    k = min(top_k, len(chunk_texts))
    # argpartition is faster than argsort for finding top k
    if len(scores) > k:
        indices = np.argpartition(scores, -k)[-k:]
        # Sort these k indices by descending score
        indices = indices[np.argsort(-scores[indices])]
    else:
        indices = np.argsort(-scores)

    # Filter out low-confidence matches (score < 0.2 cosine similarity)
    results: list[str] = []
    for idx in indices:
        score = scores[idx]
        if score > 0.2:
            results.append(chunk_texts[idx])

    logger.debug(
        "Retrieval for file_id=%s: %d/%d chunks selected (scores: %s)",
        file_id, len(results), k,
        [f"{scores[idx]:.3f}" for idx in indices[:len(results)]],
    )
    return results
