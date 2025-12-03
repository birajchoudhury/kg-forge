"""Deduplication backend implementations."""

from .interface import DedupBackend, create_dedup_backend

__all__ = [
    "DedupBackend",
    "create_dedup_backend"
]