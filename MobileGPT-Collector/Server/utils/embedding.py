"""OpenAI embedding utilities."""

import ast
from typing import Optional

import numpy as np
from openai import OpenAI
from loguru import logger

from ..config import OPENAI_API_KEY, EMBEDDING_MODEL


def get_openai_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Generate OpenAI embedding vector for text."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding


def cosine_similarity(a, b) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class DescriptionEmbeddingCache:
    """Cache for subtask description embeddings to avoid redundant API calls."""

    def __init__(self):
        self._cache: dict[str, list[float]] = {}

    def get_embedding(self, description: str) -> list[float]:
        """Get embedding for a single description, using cache if available."""
        if description not in self._cache:
            self._cache[description] = get_openai_embedding(description, model=EMBEDDING_MODEL)
        return self._cache[description]

    def get_embeddings_batch(self, descriptions: list[str]) -> list[list[float]]:
        """Get embeddings for multiple descriptions, batching uncached ones."""
        uncached = [d for d in descriptions if d not in self._cache]
        if uncached:
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)
                unique_uncached = list(dict.fromkeys(uncached))
                response = client.embeddings.create(
                    input=[t.replace("\n", " ") for t in unique_uncached],
                    model=EMBEDDING_MODEL,
                )
                for i, item in enumerate(response.data):
                    self._cache[unique_uncached[i]] = item.embedding
            except Exception as e:
                logger.warning(f"Batch embedding failed, falling back to individual: {e}")
                for desc in unique_uncached:
                    try:
                        self._cache[desc] = get_openai_embedding(desc, model=EMBEDDING_MODEL)
                    except Exception as inner_e:
                        logger.error(f"Embedding failed for '{desc[:50]}...': {inner_e}")
                        self._cache[desc] = []
        return [self.get_embedding(desc) for desc in descriptions]

    def clear(self):
        """Clear the cache."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


def safe_literal_eval(val) -> Optional[list]:
    """Safely convert string representation of list back to list."""
    if isinstance(val, (list, np.ndarray)):
        return val
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            return None
    return None
