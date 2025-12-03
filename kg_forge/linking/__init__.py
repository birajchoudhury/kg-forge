"""Entity linking backend implementations."""

from .interface import EntityLinkerBackend, create_entity_linker

__all__ = [
    "EntityLinkerBackend",
    "create_entity_linker"
]