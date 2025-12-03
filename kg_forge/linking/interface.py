"""
Entity linking backend interface and protocols.

Defines the common interface for entity linking backends that map
canonical entities to existing KG entities or mark them for creation.
"""

from typing import Protocol, List
from kg_forge.models.dedup import CanonicalLexicalEntity, LinkResult


class EntityLinkerBackend(Protocol):
    """
    Protocol for entity linking backends.
    
    All entity linking implementations must implement this interface
    to map canonical entities from deduplication to existing KG entities.
    """
    
    def link_entities(self, canonical_entities: List[CanonicalLexicalEntity], namespace: str) -> List[LinkResult]:
        """
        Link canonical entities to existing KG entities or mark for creation.
        
        Args:
            canonical_entities: Deduplicated entities to link
            namespace: Current processing namespace for scoping
            
        Returns:
            List of LinkResult objects with linking decisions
            
        Raises:
            LinkingError: When entity linking processing fails
        """
        ...
    
    def get_backend_name(self) -> str:
        """
        Get the name of this entity linking backend.
        
        Returns:
            Backend identifier (e.g., 'default', 'advanced', 'ml_linker')
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


def create_entity_linker(backend_name: str, neo4j_client, config: dict = None) -> EntityLinkerBackend:
    """
    Factory function to create entity linking backends by name.
    
    Args:
        backend_name: Name of backend to create ('default', 'advanced')
        neo4j_client: Neo4j client for KG access
        config: Optional configuration parameters
    
    Returns:
        Configured entity linking backend instance
    
    Raises:
        ValueError: If backend_name is not recognized
        ImportError: If backend dependencies are not available
    """
    config = config or {}
    
    if backend_name == "default":
        from kg_forge.linking.default_linker import DefaultEntityLinker
        return DefaultEntityLinker(neo4j_client, **config)
    elif backend_name == "advanced":
        # Future: more sophisticated linker
        from kg_forge.linking.default_linker import DefaultEntityLinker
        return DefaultEntityLinker(neo4j_client, **config)
    else:
        raise ValueError(f"Unknown entity linking backend: {backend_name}")