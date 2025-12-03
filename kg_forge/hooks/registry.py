"""
Hook registry for ingest pipeline customization.

Provides a registry pattern for hooks that can modify processing
at key points in the ingest pipeline.
"""

import logging
from datetime import datetime
from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass
from kg_forge.models.document import ParsedDocument
from kg_forge.utils.interactive import InteractiveSession

logger = logging.getLogger(__name__)


@dataclass
class EntityRecord:
    """Record of an entity processed during ingest."""
    entity_type: str
    name: str
    confidence: float
    doc_id: str
    namespace: str
    created_at: Optional[datetime] = None


class HookRegistry:
    """Registry for pipeline hooks."""
    
    def __init__(self):
        self._before_store_hooks: List[Callable] = []
        self._after_batch_hooks: List[Callable] = []
    
    def register_before_store(self, func: Callable):
        """
        Register process_before_store hook.
        
        Hook signature:
        def process_before_store(content: ParsedDocument, metadata: dict, kg_client) -> dict:
            # Modify metadata before storing in graph
            return metadata
        """
        self._before_store_hooks.append(func)
        logger.debug(f"Registered before_store hook: {func.__name__}")
    
    def register_after_batch(self, func: Callable):
        """
        Register process_after_batch hook.
        
        Hook signature:
        def process_after_batch(entities: List[EntityRecord], kg_client, interactive: InteractiveSession | None) -> None:
            # Process all entities after batch completion
            pass
        """
        self._after_batch_hooks.append(func)
        logger.debug(f"Registered after_batch hook: {func.__name__}")
    
    def execute_before_store(self, content: ParsedDocument, metadata: dict, kg_client) -> dict:
        """Execute all before_store hooks."""
        processed_metadata = metadata.copy()
        
        for hook in self._before_store_hooks:
            try:
                result = hook(content, processed_metadata, kg_client)
                if isinstance(result, dict):
                    processed_metadata.update(result)
            except Exception as e:
                logger.warning(f"Hook {hook.__name__} failed: {e}")
        
        return processed_metadata
    
    def execute_after_batch(self, entities: List[EntityRecord], kg_client, interactive_session: Optional[InteractiveSession] = None):
        """Execute all after_batch hooks."""
        for hook in self._after_batch_hooks:
            try:
                hook(entities, kg_client, interactive_session)
            except Exception as e:
                logger.warning(f"Hook {hook.__name__} failed: {e}")
    
    def clear_hooks(self):
        """Clear all registered hooks."""
        self._before_store_hooks.clear()
        self._after_batch_hooks.clear()


# Global registry instance
_global_registry = HookRegistry()


def get_global_registry() -> HookRegistry:
    """Get the global hook registry."""
    return _global_registry


def register_before_store(func: Callable):
    """Decorator to register before_store hook."""
    _global_registry.register_before_store(func)
    return func


def register_after_batch(func: Callable):
    """Decorator to register after_batch hook.""" 
    _global_registry.register_after_batch(func)
    return func