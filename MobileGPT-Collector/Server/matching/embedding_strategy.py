"""Embedding-based matching strategy using cosine similarity."""

import json
import os
from typing import Optional
from loguru import logger
import numpy as np

from ..data.models import MatchResult
from ..utils.embedding import get_openai_embedding
from .base import MatchingStrategy
from .page_registry import PageRegistry


class EmbeddingStrategy(MatchingStrategy):
    """Embedding cosine similarity matching strategy.

    Generates embeddings from hierarchy_xml using OpenAI's text-embedding-3-large
    and matches pages by cosine similarity with a configurable threshold.
    """

    def __init__(self, model: str = "text-embedding-3-large", threshold: float = 0.95):
        self.model = model
        self.threshold = threshold
        # In-memory embedding index: {bundle_id: np.ndarray}
        self._embeddings: dict[str, np.ndarray] = {}

    @property
    def name(self) -> str:
        return "embedding"

    def find_best_match(
        self,
        parsed_xml: str,
        hierarchy_xml: str,
        query_page_id: str,
        page_registry: PageRegistry,
    ) -> Optional[MatchResult]:
        if not self._embeddings:
            return None

        # Generate embedding for current screen
        query_embedding = np.array(get_openai_embedding(hierarchy_xml, model=self.model))

        # Compare with all stored embeddings
        best_bundle_id = None
        best_similarity = 0.0

        for bundle_id, stored_embedding in self._embeddings.items():
            similarity = self._cosine_similarity(query_embedding, stored_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_bundle_id = bundle_id

        if best_bundle_id is not None and best_similarity > self.threshold:
            # Determine match type based on similarity
            if best_similarity > 0.99:
                match_type = "EQSET"
            else:
                match_type = "SUBSET"

            # Get supported subtasks from registry
            page_knowledge = page_registry.get(best_bundle_id)
            supported = [s.name for s in page_knowledge.subtasks] if page_knowledge else []

            return MatchResult(
                query_page_id=query_page_id,
                candidate_bundle_id=best_bundle_id,
                match_type=match_type,
                supported_subtasks=supported,
                match_ratio=best_similarity,
                threshold=self.threshold,
            )

        return None

    def on_bundle_created(self, bundle_id: str, hierarchy_xml: str) -> None:
        """Store embedding for the new bundle."""
        try:
            embedding = np.array(get_openai_embedding(hierarchy_xml, model=self.model))
            self._embeddings[bundle_id] = embedding
            logger.debug(f"Stored embedding for bundle {bundle_id}")
        except Exception as e:
            logger.error(f"Failed to generate embedding for bundle {bundle_id}: {e}")

    def save(self, data_dir: str, app_name: str) -> None:
        """Save embedding index to disk."""
        app_dir = os.path.join(data_dir, app_name)
        os.makedirs(app_dir, exist_ok=True)
        path = os.path.join(app_dir, "embedding_index.json")

        data = {
            bid: emb.tolist()
            for bid, emb in self._embeddings.items()
        }
        with open(path, 'w') as f:
            json.dump({"model": self.model, "threshold": self.threshold, "embeddings": data}, f)

        logger.debug(f"Saved embedding index: {len(data)} entries")

    def load(self, data_dir: str, app_name: str) -> None:
        """Load embedding index from disk."""
        path = os.path.join(data_dir, app_name, "embedding_index.json")
        if not os.path.exists(path):
            return

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            self._embeddings = {
                bid: np.array(emb)
                for bid, emb in data.get("embeddings", {}).items()
            }
            logger.info(f"Loaded embedding index: {len(self._embeddings)} entries")
        except Exception as e:
            logger.error(f"Failed to load embedding index: {e}")

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
