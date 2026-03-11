"""Abstract base class for page matching strategies."""

from abc import ABC, abstractmethod
from typing import Optional

from ..data.models import MatchResult
from .page_registry import PageRegistry


class MatchingStrategy(ABC):
    """Abstract base class for page matching strategies."""

    @abstractmethod
    def find_best_match(
        self,
        parsed_xml: str,
        hierarchy_xml: str,
        query_page_id: str,
        page_registry: PageRegistry,
    ) -> Optional[MatchResult]:
        """Find the best matching bundle for a query screen.

        Args:
            parsed_xml: Parsed XML with semantic tags
            hierarchy_xml: Structure-only XML (for embedding)
            query_page_id: ID of the query page
            page_registry: Registry of known pages/bundles

        Returns:
            MatchResult if a match is found, None otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""
        pass

    def on_bundle_created(self, bundle_id: str, hierarchy_xml: str) -> None:
        """Called when a new bundle is created. Override for strategies that need per-bundle data."""
        pass

    def save(self, data_dir: str, app_name: str) -> None:
        """Persist strategy-specific data to disk."""
        pass

    def load(self, data_dir: str, app_name: str) -> None:
        """Load strategy-specific data from disk."""
        pass
