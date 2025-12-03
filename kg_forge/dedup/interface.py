"""
Deduplication backend interface and protocols.

Defines the common interface for entity deduplication backends
that process LexicalGraph to produce DedupedLexicalGraph.
"""

from typing import Protocol
from kg_forge.models.lexical import LexicalGraph
from kg_forge.models.dedup import DedupedLexicalGraph


class DedupBackend(Protocol):
    """
    Protocol for entity deduplication backends.
    
    All deduplication implementations (Splink, Zingg, no-dedup) must implement
    this interface to process raw extraction results into canonical entities.
    """
    
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Apply entity resolution to group mentions into canonical entities.
        
        Args:
            lexical_graph: Raw extraction results with mentions and relations
            namespace: Current processing namespace for context
            
        Returns:
            DedupedLexicalGraph with canonical entities and updated relations
            
        Raises:
            DedupError: When deduplication processing fails
        """
        ...
    
    def get_backend_name(self) -> str:
        """
        Get the name of this deduplication backend.
        
        Returns:
            Backend identifier (e.g., 'splink', 'zingg', 'none', 'ensemble')
        """
        ...
    
    def get_backend_info(self) -> dict:
        """
        Get detailed information about this backend.
        
        Returns:
            Dictionary containing backend metadata like version info,
            configuration parameters, and capabilities
        """
        ...
    
    def validate_configuration(self) -> bool:
        """
        Validate backend configuration and dependencies.
        
        Returns:
            True if backend is properly configured and ready to use
        """
        ...


def create_dedup_backend(backend_name: str, config: dict = None) -> DedupBackend:
    """
    Factory function to create deduplication backends by name.
    
    Args:
        backend_name: Name of backend to create ('splink', 'zingg', 'none', 'both')
        config: Optional configuration parameters
    
    Returns:
        Configured deduplication backend instance
    
    Raises:
        ValueError: If backend_name is not recognized
        ImportError: If backend dependencies are not available
    """
    config = config or {}
    
    if backend_name == "splink":
        from kg_forge.dedup.splink_backend import SpLinkDedupBackend
        return SpLinkDedupBackend(**config)
    elif backend_name == "zingg":
        from kg_forge.dedup.zingg_backend import ZinggDedupBackend  
        return ZinggDedupBackend(**config)
    elif backend_name == "none":
        from kg_forge.dedup.no_dedup_backend import NoDedupBackend
        return NoDedupBackend(**config)
    elif backend_name == "both":
        from kg_forge.dedup.ensemble_backend import EnsembleDedupBackend
        return EnsembleDedupBackend(**config)
    else:
        raise ValueError(f"Unknown deduplication backend: {backend_name}")