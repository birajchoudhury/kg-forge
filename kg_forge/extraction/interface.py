"""
Extraction backend interface definition.

Defines the protocol that all extraction backends must implement.
"""
from typing import Protocol, runtime_checkable
from pathlib import Path

from kg_forge.models.lexical import LexicalGraph
from kg_forge.ontology.schema import OntologySchema


@runtime_checkable
class ExtractionBackend(Protocol):
    """Protocol for entity and relation extraction backends.
    
    All extraction backends (LLM, spaCy, fake, etc.) must implement this interface.
    Backends take curated document text and an ontology pack, and return a lexical graph.
    """
    
    def extract(self, content: str, ontology: OntologySchema, doc_id: str) -> LexicalGraph:
        """Extract entities and relations from document content.
        
        Args:
            content: Curated text content of the document
            ontology: Normalized ontology schema with entity and relation definitions
            doc_id: Unique identifier for the document being processed
        
        Returns:
            LexicalGraph containing mentions and relations found in the content
        
        Raises:
            ExtractionError: When extraction fails due to backend-specific issues
            ValidationError: When the produced LexicalGraph is invalid
        """
        ...
    
    def get_backend_name(self) -> str:
        """Get the name of this extraction backend.
        
        Returns:
            Backend identifier (e.g., 'llm', 'spacy', 'fake')
        """
        ...
    
    def get_backend_info(self) -> dict:
        """Get detailed information about this backend.
        
        Returns:
            Dictionary containing backend metadata like model versions,
            configuration parameters, capabilities, etc.
        """
        ...
    
    def validate_configuration(self) -> bool:
        """Check if the backend is properly configured.
        
        Returns:
            True if backend is ready for extraction, False otherwise
        
        Note:
            Should check dependencies, credentials, model availability, etc.
            Used during initialization to fail fast on configuration issues.
        """
        ...


class BaseExtractionBackend:
    """Base class with common functionality for extraction backends.
    
    Provides shared utilities like mention ID generation, validation, and logging.
    Concrete backends should inherit from this class and implement the abstract methods.
    """
    
    def __init__(self, backend_name: str):
        """Initialize base extraction backend.
        
        Args:
            backend_name: Identifier for this backend type
        """
        self.backend_name = backend_name
        self._mention_counter = 0
        self._relation_counter = 0
    
    def get_backend_name(self) -> str:
        """Get the name of this extraction backend."""
        return self.backend_name
    
    def _generate_mention_id(self, doc_id: str) -> str:
        """Generate unique mention ID within document scope."""
        self._mention_counter += 1
        return f"{doc_id}_mention_{self._mention_counter}"
    
    def _generate_relation_id(self, doc_id: str) -> str:
        """Generate unique relation ID within document scope."""
        self._relation_counter += 1
        return f"{doc_id}_relation_{self._relation_counter}"
    
    def _reset_counters(self):
        """Reset ID counters for new document processing."""
        self._mention_counter = 0
        self._relation_counter = 0
    
    def _validate_ontology_compatibility(self, ontology: OntologySchema, entity_type: str) -> bool:
        """Check if entity type is defined in the ontology.
        
        Args:
            ontology: Normalized ontology schema
            entity_type: Entity type to validate
            
        Returns:
            True if entity type is valid, False otherwise
        """
        return entity_type in ontology.entities
    
    def _validate_relation_compatibility(self, ontology: OntologySchema, relation_type: str, 
                                       src_entity_type: str, dst_entity_type: str) -> bool:
        """Check if relation type is allowed between the given entity types.
        
        Args:
            ontology: Normalized ontology schema
            relation_type: Relation type to validate
            src_entity_type: Source entity type
            dst_entity_type: Destination entity type
            
        Returns:
            True if relation is valid according to ontology, False otherwise
        """
        return ontology.validate_relation(relation_type, src_entity_type, dst_entity_type)
    
    def extract(self, content: str, ontology: OntologySchema, doc_id: str, namespace: str = None) -> LexicalGraph:
        """Extract entities and relations from content.
        
        Base implementation that sets up common state and delegates to _do_extract.
        
        Args:
            content: Curated text content
            ontology: Normalized ontology schema
            doc_id: Document identifier
            namespace: Optional namespace for organizing output
        """
        self._reset_counters()
        return self._do_extract(content, ontology, doc_id, namespace)
    
    def _do_extract(self, content: str, ontology: OntologySchema, doc_id: str, namespace: str = None) -> LexicalGraph:
        """Perform the actual extraction work.
        
        Must be implemented by concrete backend classes.
        
        Args:
            content: Curated text content
            ontology: Normalized ontology schema
            doc_id: Document identifier
            namespace: Optional namespace for organizing output
        """
        raise NotImplementedError("Subclasses must implement _do_extract")
    
    def get_backend_info(self) -> dict:
        """Get backend information.
        
        Base implementation - subclasses should extend this.
        """
        return {
            'backend_name': self.backend_name,
            'base_class': 'BaseExtractionBackend'
        }
    
    def validate_configuration(self) -> bool:
        """Validate backend configuration.
        
        Base implementation always returns True - subclasses should override.
        """
        return True


def create_extraction_backend(backend_name: str, config: dict = None) -> ExtractionBackend:
    """Factory function to create extraction backends by name.
    
    Args:
        backend_name: Name of backend to create ('llm', 'spacy', 'hybrid', 'fake')
        config: Optional configuration parameters
    
    Returns:
        Configured extraction backend instance
    
    Raises:
        ValueError: If backend_name is not recognized
        ImportError: If backend dependencies are not available
    """
    config = config or {}
    
    if backend_name == "llm":
        from kg_forge.extraction.llm_backend import LLMExtractionBackend
        return LLMExtractionBackend(**config)
    elif backend_name == "spacy":
        from kg_forge.extraction.spacy_backend import SpacyLexicalBackend
        return SpacyLexicalBackend(**config)
    elif backend_name == "hybrid":
        from kg_forge.extraction.hybrid_backend import HybridExtractionBackend
        return HybridExtractionBackend(**config)
    elif backend_name == "fake":
        from kg_forge.extraction.fake_backend import FakeExtractionBackend
        return FakeExtractionBackend(**config)
    else:
        raise ValueError(f"Unknown extraction backend: {backend_name}")