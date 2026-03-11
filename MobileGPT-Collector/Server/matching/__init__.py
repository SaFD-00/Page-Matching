"""Matching modules for MobileGPT-Collector Server."""

from .page_registry import PageRegistry
from .bundle_manager import BundleManager
from .ui_matcher import UIMatcher
from .base import MatchingStrategy
from .factory import create_strategy, STRATEGY_NAMES

__all__ = [
    "PageRegistry",
    "BundleManager",
    "UIMatcher",
    "MatchingStrategy",
    "create_strategy",
    "STRATEGY_NAMES",
]
