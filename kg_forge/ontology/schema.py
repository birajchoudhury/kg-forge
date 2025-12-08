"""Normalized ontology schema representation and helper methods.

This module defines the OntologySchema dataclass that serves as the normalized
internal representation of ontologies, regardless of whether they come from TTL
or Markdown sources.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import json


@dataclass
class Property:
    """Entity or relation property definition."""
    name: str
    description: Optional[str] = None
    datatype: Optional[str] = None  # e.g., "string", "integer", "date"
    required: bool = False


@dataclass
class EntityType:
    """Normalized entity type definition."""
    name: str                       # e.g., "Product", "Team"
    iri: str                        # e.g., "http://example.org/ont#Product"
    description: str                # Natural language description
    properties: List[Property] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)  # Example entity names
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "iri": self.iri,
            "description": self.description,
            "properties": [
                {
                    "name": p.name,
                    "description": p.description,
                    "datatype": p.datatype,
                    "required": p.required
                } for p in self.properties
            ],
            "examples": self.examples
        }


@dataclass
class RelationType:
    """Normalized relation type definition."""
    name: str                       # e.g., "WORKS_ON"
    iri: str                        # e.g., "http://example.org/ont#worksOn"
    head_types: List[str]          # Allowed source entity types
    tail_types: List[str]          # Allowed target entity types
    description: str                # Natural language description
    properties: List[Property] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "iri": self.iri,
            "head_types": self.head_types,
            "tail_types": self.tail_types,
            "description": self.description,
            "properties": [
                {
                    "name": p.name,
                    "description": p.description,
                    "datatype": p.datatype,
                    "required": p.required
                } for p in self.properties
            ]
        }


@dataclass
class OntologySchema:
    """Normalized ontology schema used throughout the system.
    
    This is the single source of truth for ontology information, produced by
    both TTLOntologyLoader and MarkdownOntologyLoader.
    """
    entities: Dict[str, EntityType]
    relations: Dict[str, RelationType]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_gliner_config(self) -> Dict[str, str]:
        """Generate GLiNER label config with natural language descriptions.
        
        Returns:
            Dict mapping entity type names to descriptions.
            Example: {"Product": "A software product or service offering", ...}
        """
        return {
            entity_type: entity.description
            for entity_type, entity in self.entities.items()
        }
    
    def to_glirel_config(self) -> Dict[str, Dict[str, Any]]:
        """Generate GLiREL relation config with type constraints.
        
        Returns:
            Dict mapping relation names to constraint dictionaries.
            Example: {
                "WORKS_ON": {
                    "description": "Indicates that a team works on a product",
                    "head_types": ["Team"],
                    "tail_types": ["Product"]
                },
                ...
            }
        """
        return {
            relation_name: {
                "description": relation.description,
                "head_types": relation.head_types,
                "tail_types": relation.tail_types
            }
            for relation_name, relation in self.relations.items()
        }
    
    def to_llm_prompt_snippet(self) -> str:
        """Generate compact JSON for LLM prompts.
        
        Returns:
            JSON string containing entity types and relation types with descriptions.
        """
        prompt_data = {
            "entity_types": {
                entity_type: {
                    "description": entity.description,
                    "examples": entity.examples[:5] if entity.examples else []
                }
                for entity_type, entity in self.entities.items()
            },
            "relation_types": {
                relation_name: {
                    "description": relation.description,
                    "allowed_patterns": [
                        f"({head}) -> {relation_name} -> ({tail})"
                        for head in relation.head_types
                        for tail in relation.tail_types
                    ]
                }
                for relation_name, relation in self.relations.items()
            }
        }
        return json.dumps(prompt_data, indent=2)
    
    def get_entity_type(self, name: str) -> Optional[EntityType]:
        """Get entity type by name."""
        return self.entities.get(name)
    
    def get_relation_type(self, name: str) -> Optional[RelationType]:
        """Get relation type by name."""
        return self.relations.get(name)
    
    def validate_relation(self, relation_name: str, head_type: str, tail_type: str) -> bool:
        """Check if a relation is valid between two entity types.
        
        Args:
            relation_name: Name of the relation type
            head_type: Source entity type
            tail_type: Target entity type
            
        Returns:
            True if the relation is allowed, False otherwise
        """
        relation = self.relations.get(relation_name)
        if not relation:
            return False
        
        return (head_type in relation.head_types and
                tail_type in relation.tail_types)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entities": {
                name: entity.to_dict()
                for name, entity in self.entities.items()
            },
            "relations": {
                name: relation.to_dict()
                for name, relation in self.relations.items()
            },
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OntologySchema':
        """Create OntologySchema from dictionary."""
        entities = {}
        for name, entity_data in data.get("entities", {}).items():
            properties = [
                Property(**prop) for prop in entity_data.get("properties", [])
            ]
            entities[name] = EntityType(
                name=entity_data["name"],
                iri=entity_data["iri"],
                description=entity_data["description"],
                properties=properties,
                examples=entity_data.get("examples", [])
            )
        
        relations = {}
        for name, relation_data in data.get("relations", {}).items():
            properties = [
                Property(**prop) for prop in relation_data.get("properties", [])
            ]
            relations[name] = RelationType(
                name=relation_data["name"],
                iri=relation_data["iri"],
                head_types=relation_data["head_types"],
                tail_types=relation_data["tail_types"],
                description=relation_data["description"],
                properties=properties
            )
        
        return cls(
            entities=entities,
            relations=relations,
            metadata=data.get("metadata", {})
        )
