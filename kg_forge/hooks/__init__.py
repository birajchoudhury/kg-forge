"""
Hook system for extending the ingest pipeline.
"""

from .registry import HookRegistry, EntityRecord, get_global_registry
from .examples import *

__all__ = [
    "HookRegistry",
    "EntityRecord",
    "get_global_registry"
]