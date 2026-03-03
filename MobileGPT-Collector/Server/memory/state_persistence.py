"""Exploration state persistence."""

import json
import os
from datetime import datetime
from typing import Optional
from loguru import logger

from ..data.models import ExplorationState
from ..matching.page_registry import PageRegistry


class StatePersistence:
    """Save and load exploration state for resume capability."""

    def __init__(self, data_dir: str, app_name: str):
        self.data_dir = data_dir
        self.app_name = app_name

    @property
    def app_dir(self) -> str:
        return os.path.join(self.data_dir, self.app_name)

    @property
    def state_path(self) -> str:
        return os.path.join(self.app_dir, "exploration_state.json")

    @property
    def registry_path(self) -> str:
        return os.path.join(self.app_dir, "page_registry.json")

    def save_state(self, state: ExplorationState) -> None:
        """Save exploration state to disk."""
        os.makedirs(self.app_dir, exist_ok=True)
        state.last_updated = datetime.now().isoformat()
        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(state.model_dump(), f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved exploration state: {self.state_path}")

    def load_state(self) -> Optional[ExplorationState]:
        """Load exploration state from disk."""
        if not os.path.exists(self.state_path):
            return None
        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            state = ExplorationState(**data)
            logger.info(f"Loaded exploration state: {state.total_pages_collected} pages, {state.bundle_count} bundles")
            return state
        except Exception as e:
            logger.error(f"Failed to load exploration state: {e}")
            return None

    def save_registry(self, registry: PageRegistry) -> None:
        """Save page registry to disk."""
        os.makedirs(self.app_dir, exist_ok=True)
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(registry.to_dict(), f, indent=2, ensure_ascii=False)

    def load_registry(self) -> Optional[PageRegistry]:
        """Load page registry from disk."""
        if not os.path.exists(self.registry_path):
            return None
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return PageRegistry.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load page registry: {e}")
            return None

    def has_saved_state(self) -> bool:
        """Check if saved state exists."""
        return os.path.exists(self.state_path)
