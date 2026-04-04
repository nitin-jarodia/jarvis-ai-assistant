"""
File Service for Jarvis AI Assistant.

Handles:
  - Upload validation
  - Text extraction from PDF and TXT files
  - Word-based chunking
  - Lightweight relevance scoring for document chat
"""

from __future__ import annotations

import io
import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────────

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "txt"}
ALLOWED_CONTENT_TYPES = {
    "pdf": {"application/pdf", "application/x-pdf"},
    "txt": {"text/plain", "application/octet-stream", ""},
}
TARGET_CHUNK_WORDS = 650
CHUNK_OVERLAP_WORDS = 100
MIN_CHUNK_WORDS = 80
TOP_K_CHUNKS = 5
MIN_RELEVANCE_SCORE = 1.2
FALLBACK_CHUNK_COUNT = 2

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "what", "when", "where", "which", "who", "why",
    "with", "you", "your", "about", "into", "than", "them", "they", "their",
    "tell", "me", "please", "can", "could", "would", "should",
}
SUMMARY_TERMS = {
    "summary", "summarize", "overview", "main", "topic", "gist", "document",
    "brief", "highlevel", "high", "level",
}
FOLLOW_UP_TERMS = {
    "it", "this", "that", "those", "these", "they", "them", "he", "she",
    "more", "further", "continue", "elaborate", "detail", "details",
    "explain", "again", "also", "its",
}


# ─── Text Extraction ──────────────────────────────────────────────────────────

def validate_upload(filename: str, content_type: str | None, content: bytes) -> str:
    """Validate the uploaded file and return the normalized extension."""
    if not filename:
        raise ValueError("A file name is required.")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Only PDF and TXT files are allowed.")

    if not content:
        raise ValueError("Uploaded file is empty.")

    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File too large. Maximum size is 10 MB.")

    normalized_content_type = (content_type or "").split(";")[0].strip().lower()
    allowed_types = ALLOWED_CONTENT_TYPES.get(ext, set())
    if normalized_content_type and normalized_content_type not in allowed_types:
        logger.warning(
            "Upload content-type mismatch for %s: %s",
            filename,
            normalized_content_type,
        )

    return ext


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
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return content.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace").strip()
    except Exception as e:
        raise ValueError(f"Failed to read TXT file: {e}") from e


def _extract_pdf(content: bytes) -> str:
    try:
        import pdfplumber  # noqa

        pages = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                cleaned = text.strip()
                if cleaned:
                    pages.append(f"[Page {index}]\n{cleaned}")
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
    """Split text into overlapping chunks of roughly 500-800 words."""
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    words = cleaned.split()
    if len(words) <= TARGET_CHUNK_WORDS:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    step = TARGET_CHUNK_WORDS - CHUNK_OVERLAP_WORDS

    while start < len(words):
        end = min(start + TARGET_CHUNK_WORDS, len(words))
        chunk_words = words[start:end]
        if len(chunk_words) < MIN_CHUNK_WORDS and chunks:
            chunks[-1] = f"{chunks[-1]}\n\n{' '.join(chunk_words)}".strip()
            break

        chunks.append(" ".join(chunk_words).strip())
        if end >= len(words):
            break
        start += step

    return chunks


def _clean_text(text: str) -> str:
    """Normalize whitespace and remove junk characters."""
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n +", "\n", text)
    return text.strip()


# ─── Retrieval ────────────────────────────────────────────────────────────────

def build_retrieval_query(query: str, history: list[dict[str, str]] | None = None) -> str:
    """Expand short follow-up questions with recent user context."""
    if not history:
        return query

    prior_user_messages = [
        message["content"].strip()
        for message in history
        if message.get("role") == "user" and message.get("content")
    ]
    if not prior_user_messages:
        return query

    current_terms = _query_terms(query)
    is_follow_up = (
        len(current_terms) <= 4
        or any(term in FOLLOW_UP_TERMS for term in _tokenize(query))
    )
    if not is_follow_up:
        return query

    previous_questions = prior_user_messages[-2:]
    expanded_parts = previous_questions + [query]
    return " ".join(part for part in expanded_parts if part).strip()


def retrieve_chunks(query: str, chunks: list[str], top_k: int = TOP_K_CHUNKS) -> list[str]:
    """Return the most relevant chunks for a query using lightweight scoring."""
    if not chunks:
        return []

    query_terms = _query_terms(query)
    raw_query_terms = _tokenize(query)

    if not query_terms or any(term in SUMMARY_TERMS for term in raw_query_terms):
        return chunks[: min(top_k, len(chunks))]

    scored_chunks: list[tuple[float, int, str]] = []
    for index, chunk in enumerate(chunks):
        score = _score_chunk(query, query_terms, chunk)
        scored_chunks.append((score, index, chunk))

    if not scored_chunks:
        return chunks[: min(FALLBACK_CHUNK_COUNT, len(chunks))]

    scored_chunks.sort(key=lambda item: (-item[0], item[1]))
    strong_matches = [item for item in scored_chunks if item[0] >= MIN_RELEVANCE_SCORE]
    if strong_matches:
        return [chunk for _, _, chunk in strong_matches[:top_k]]

    positive_matches = [item for item in scored_chunks if item[0] > 0]
    if positive_matches:
        return [chunk for _, _, chunk in positive_matches[: min(top_k, len(positive_matches))]]

    return chunks[: min(FALLBACK_CHUNK_COUNT, len(chunks))]


def format_chunks_for_prompt(chunks: list[str]) -> str:
    """Format retrieved chunks into a compact prompt block."""
    sections = [f"[Chunk {index + 1}]\n{chunk}" for index, chunk in enumerate(chunks)]
    return "\n\n".join(sections)


def _score_chunk(query: str, query_terms: list[str], chunk: str) -> float:
    chunk_terms = _tokenize(chunk)
    if not chunk_terms:
        return 0.0

    chunk_counter = Counter(chunk_terms)
    overlap = [term for term in query_terms if term in chunk_counter]
    if not overlap:
        return 0.0

    coverage_score = len(set(overlap)) / max(len(set(query_terms)), 1)
    frequency_score = sum(min(chunk_counter[term], 3) for term in overlap) / len(query_terms)

    normalized_query = _normalize_for_match(query)
    normalized_chunk = _normalize_for_match(chunk)
    phrase_bonus = 1.5 if normalized_query and normalized_query in normalized_chunk else 0.0

    ordered_bonus = 0.0
    if len(query_terms) >= 2:
        joined_terms = " ".join(query_terms[:4])
        if joined_terms and joined_terms in normalized_chunk:
            ordered_bonus = 0.75

    return (coverage_score * 3.0) + frequency_score + phrase_bonus + ordered_bonus


def _query_terms(query: str) -> list[str]:
    tokens = _tokenize(query)
    return [token for token in tokens if token not in STOPWORDS]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _normalize_for_match(text: str) -> str:
    return " ".join(_tokenize(text))
