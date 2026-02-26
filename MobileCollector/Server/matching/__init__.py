"""Matching modules for MobileCollector Server."""

from .page_registry import PageRegistry
from .bundle_manager import BundleManager
from .ui_matcher import UIMatcher

__all__ = [
    "PageRegistry",
    "BundleManager",
    "UIMatcher",
]
