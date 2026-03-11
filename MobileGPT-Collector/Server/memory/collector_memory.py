"""Independent memory system for MobileCollector."""

import os
from typing import Optional
from loguru import logger

from ..data.models import Subtask, UIAttributes, ExplorationState, MatchResult
from ..matching.page_registry import PageRegistry
from ..matching.page_matcher import PageMatcher
from ..matching.bundle_manager import BundleManager
from ..matching.base import MatchingStrategy
from ..matching.factory import create_strategy
from ..storage.page_storage import PageStorage
from .state_persistence import StatePersistence


class CollectorMemory:
    """Independent memory system combining PageRegistry, BundleManager, and PageStorage."""

    def __init__(self, data_dir: str, app_name: str, threshold: float = 1.0,
                 matching: str = "keyui-mobilegpt"):
        self.data_dir = data_dir
        self.app_name = app_name
        self.threshold = threshold
        self.matching_name = matching

        # Core components
        self.registry = PageRegistry()
        self.bundle_manager = BundleManager(data_dir, app_name, self.registry)
        self.page_storage = PageStorage(data_dir)
        self.state_persistence = StatePersistence(data_dir, app_name)

        # Create matching strategy
        strategy_kwargs = {}
        if matching == "keyui-mobilegpt":
            strategy_kwargs["match_threshold"] = threshold if threshold != 0.7 else 0.7
        elif matching == "embedding":
            strategy_kwargs["threshold"] = threshold if threshold != 0.7 else 0.95
        self.matching_strategy: MatchingStrategy = create_strategy(matching, **strategy_kwargs)

        # Keep page_matcher for backward compatibility (used by V2 strategy internally)
        self.page_matcher = PageMatcher(self.registry, threshold=threshold)

        # Page counter (global across all bundles)
        self._page_counter = 0

    def initialize(self) -> Optional[ExplorationState]:
        """Initialize memory. Loads existing state if available."""
        # Try to load existing state
        state = self.state_persistence.load_state()
        if state:
            # Load registry
            registry = self.state_persistence.load_registry()
            if registry:
                self.registry = registry
                self.bundle_manager = BundleManager(self.data_dir, self.app_name, self.registry)
                self.bundle_manager.load_bundle_map()
                self.page_matcher = PageMatcher(
                    self.registry, threshold=self.threshold,
                )
                self._page_counter = state.page_counter

                # Load strategy-specific data (e.g., embedding index)
                self.matching_strategy.load(self.data_dir, self.app_name)

            logger.info(f"Resumed exploration: {state.total_pages_collected} pages, {state.bundle_count} bundles")
            return state

        logger.info(f"Starting new exploration for {self.app_name}")
        return None

    def process_new_screen(
        self,
        raw_xml: str,
        screenshot_path: str,
        subtasks: list[Subtask],
        keyuis: dict[str, list[UIAttributes]],
        encoded_xml: str,
        parsed_xml: str,
        hierarchy_xml: str,
        pretty_xml: str,
    ) -> tuple[int, int, int, Optional[MatchResult]]:
        """Process a new screen: match, store, and return results.

        Returns:
            (page_index, bundle_num, page_num, match_result)
        """
        page_index = self._page_counter
        self._page_counter += 1

        # Find best match using the configured strategy
        match_result = self.matching_strategy.find_best_match(
            parsed_xml, hierarchy_xml, str(page_index), self.registry,
        )

        if match_result is None:
            # NEW page - create new bundle
            bundle_num = self.bundle_manager.create_bundle(subtasks, keyuis)
            page_num = self.bundle_manager.add_page_to_bundle(bundle_num, page_index)

            # Notify strategy of new bundle (e.g., for embedding storage)
            self.matching_strategy.on_bundle_created(str(bundle_num), hierarchy_xml)
        else:
            bundle_num = int(match_result.candidate_bundle_id)

            if match_result.match_type == "SUPERSET":
                # Extract new subtasks and expand bundle
                new_subtasks = self.page_matcher.extract_new_subtasks(encoded_xml, match_result)
                from ..agents.keyui_selector import KeyUISelector
                selector = KeyUISelector()
                new_keyuis = selector.select_all(new_subtasks, parsed_xml)
                self.bundle_manager.expand_bundle(bundle_num, new_subtasks, new_keyuis)

            page_num = self.bundle_manager.add_page_to_bundle(bundle_num, page_index)

        # Save page data
        self.page_storage.save_page(
            app_name=self.app_name,
            bundle_num=bundle_num,
            page_num=page_num,
            raw_xml=raw_xml,
            parsed_xml=parsed_xml,
            hierarchy_xml=hierarchy_xml,
            encoded_xml=encoded_xml,
            pretty_xml=pretty_xml,
            screenshot_path=screenshot_path,
            subtasks=subtasks,
            keyuis=keyuis
        )

        logger.info(
            f"Page {page_index} -> bundle {bundle_num}/page {page_num} "
            f"({match_result.match_type if match_result else 'NEW'})"
        )

        return page_index, bundle_num, page_num, match_result

    def save_state(self, state: ExplorationState) -> None:
        """Save current state."""
        state.page_counter = self._page_counter
        state.bundle_count = self.bundle_manager.bundle_count
        state.total_pages_collected = self.bundle_manager.total_pages
        self.state_persistence.save_state(state)
        self.state_persistence.save_registry(self.registry)
        self.bundle_manager.save_bundle_map()

        # Save strategy-specific data (e.g., embedding index)
        self.matching_strategy.save(self.data_dir, self.app_name)

    def get_page_counter(self) -> int:
        return self._page_counter
