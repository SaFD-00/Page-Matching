"""Storage modules for MobileGPT-Collector Server."""

from .encoder import XmlEncoder
from .page_storage import PageStorage

__all__ = [
    "XmlEncoder",
    "PageStorage",
]
