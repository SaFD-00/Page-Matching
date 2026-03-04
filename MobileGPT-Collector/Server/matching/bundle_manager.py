"""Bundle management for MobileCollector format."""

import json
import os
from typing import Optional
from loguru import logger

from ..data.models import BundleInfo, Subtask, UIAttributes, PageKnowledge
from .page_registry import PageRegistry


class BundleManager:
    """Manages bundle CRUD operations and disk storage."""

    def __init__(self, data_dir: str, app_name: str, page_registry: PageRegistry):
        self.data_dir = data_dir
        self.app_name = app_name
        self.registry = page_registry
        self._bundles: dict[int, BundleInfo] = {}
        self._page_index_to_bundle: dict[int, int] = {}

    @property
    def app_dir(self) -> str:
        return os.path.join(self.data_dir, self.app_name)

    def _get_next_bundle_num(self) -> int:
        """Get next available bundle number."""
        if not os.path.exists(self.app_dir):
            return 0
        existing = [int(d) for d in os.listdir(self.app_dir)
                    if os.path.isdir(os.path.join(self.app_dir, d)) and d.isdigit()]
        if existing:
            return max(existing) + 1
        return 0

    def create_bundle(self, subtasks: list[Subtask], keyuis: dict[str, list[UIAttributes]]) -> int:
        """Create a new bundle. Returns bundle_num."""
        bundle_num = self._get_next_bundle_num()
        bundle_dir = os.path.join(self.app_dir, str(bundle_num))
        os.makedirs(bundle_dir, exist_ok=True)

        bundle_info = BundleInfo(
            bundle_id=str(bundle_num),
            bundle_num=bundle_num,
            app_name=self.app_name,
            pages=[],
            representative_page=0,
            subtasks=subtasks,
            keyuis=keyuis
        )
        self._bundles[bundle_num] = bundle_info

        # Register in PageRegistry
        page_knowledge = PageKnowledge(
            bundle_id=str(bundle_num),
            app_name=self.app_name,
            subtasks=subtasks,
            keyuis=keyuis
        )
        self.registry.add(page_knowledge)

        logger.info(f"Created bundle {bundle_num} with {len(subtasks)} subtasks")
        return bundle_num

    def add_page_to_bundle(self, bundle_num: int, page_index: int) -> int:
        """Add a page to existing bundle. Returns page_num within bundle."""
        if bundle_num not in self._bundles:
            logger.warning(f"Bundle {bundle_num} not found")
            return 0

        bundle = self._bundles[bundle_num]
        page_num = len(bundle.pages)
        bundle.pages.append(page_index)
        self._page_index_to_bundle[page_index] = bundle_num

        # Create page directory
        page_dir = os.path.join(self.app_dir, str(bundle_num), str(page_num))
        os.makedirs(page_dir, exist_ok=True)

        logger.debug(f"Added page {page_num} (index {page_index}) to bundle {bundle_num}")
        return page_num

    def expand_bundle(self, bundle_num: int, new_subtasks: list[Subtask], new_keyuis: dict[str, list[UIAttributes]]) -> None:
        """Expand bundle with new subtasks (SUPERSET case)."""
        if bundle_num not in self._bundles:
            return

        bundle = self._bundles[bundle_num]
        existing_names = {s.name for s in bundle.subtasks}

        for subtask in new_subtasks:
            if subtask.name not in existing_names:
                bundle.subtasks.append(subtask)
                existing_names.add(subtask.name)

        bundle.keyuis.update(new_keyuis)

        # Update PageRegistry
        bundle_id = str(bundle_num)
        for subtask in new_subtasks:
            keyui_attrs = new_keyuis.get(subtask.name)
            self.registry.add_subtask(bundle_id, subtask, keyui_attrs)

        logger.debug(f"Expanded bundle {bundle_num} with {len(new_subtasks)} new subtasks")

    def get_bundle_for_page(self, page_index: int) -> Optional[int]:
        """Get bundle number for a page index."""
        return self._page_index_to_bundle.get(page_index)

    def get_bundle_info(self, bundle_num: int) -> Optional[BundleInfo]:
        return self._bundles.get(bundle_num)

    def get_page_dir(self, bundle_num: int, page_num: int) -> str:
        return os.path.join(self.app_dir, str(bundle_num), str(page_num))

    @property
    def bundle_count(self) -> int:
        return len(self._bundles)

    @property
    def total_pages(self) -> int:
        return sum(len(b.pages) for b in self._bundles.values())

    def save_bundle_map(self) -> None:
        """Save bundle map to disk."""
        os.makedirs(self.app_dir, exist_ok=True)
        data = {
            "bundles": {
                str(num): {
                    "bundle_num": info.bundle_num,
                    "pages": info.pages,
                    "representative_page": info.representative_page,
                    "subtasks": [s.model_dump() for s in info.subtasks],
                }
                for num, info in self._bundles.items()
            },
            "page_index_to_bundle": {str(k): v for k, v in self._page_index_to_bundle.items()}
        }
        path = os.path.join(self.app_dir, "bundle_map.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_bundle_map(self) -> bool:
        """Load bundle map from disk. Returns True if loaded."""
        path = os.path.join(self.app_dir, "bundle_map.json")
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for num_str, info in data.get("bundles", {}).items():
                num = int(num_str)
                self._bundles[num] = BundleInfo(
                    bundle_id=num_str,
                    bundle_num=num,
                    app_name=self.app_name,
                    pages=info.get("pages", []),
                    representative_page=info.get("representative_page", 0),
                    subtasks=[Subtask(**s) for s in info.get("subtasks", [])],
                )

            self._page_index_to_bundle = {
                int(k): v for k, v in data.get("page_index_to_bundle", {}).items()
            }
            logger.info(f"Loaded bundle map: {len(self._bundles)} bundles")
            return True
        except Exception as e:
            logger.error(f"Failed to load bundle map: {e}")
            return False
