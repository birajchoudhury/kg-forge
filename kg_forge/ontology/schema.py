"""Normalized ontology schema representation and helper methods.

This module defines the OntologySchema dataclass that serves as the normalized
internal representation of ontologies, regardless of whether they come from TTL
or Markdown sources.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import json


@dataclass
class Dependency:
    """Entity dependency specification for occurrence entities.
    
    Represents a required relationship between an occurrence entity
    and a core entity, with cardinality constraints.
    """
    role: str           # e.g., "contract", "template"
    entity: str         # e.g., "Contract", "Template"  
    cardinality: str    # "1", "0..1", "1..*", "0..*"
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "entity": self.entity,
            "cardinality": self.cardinality
        }


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
    kind: str = "core"              # "core" or "occurrence"
    properties: List[Property] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)  # Example entity names
    depends_on: List[Dependency] = field(default_factory=list)  # Dependencies for occurrence entities
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "iri": self.iri,
            "description": self.description,
            "kind": self.kind,
            "properties": [
                {
                    "name": p.name,
                    "description": p.description,
                    "datatype": p.datatype,
                    "required": p.required
                } for p in self.properties
            ],
            "examples": self.examples,
            "depends_on": [dep.to_dict() for dep in self.depends_on]
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
    
    def to_entity_config(self) -> Dict[str, Any]:
        """Generate entity config JSON for config-driven LLM extraction.
        
        This method produces a simplified JSON structure optimized for LLM prompts
        that includes entity kind, properties, relations, and dependencies.
        
        Returns:
            Dictionary with structure:
            {
                "entities": {
                    "<EntityName>": {
                        "kind": "core" | "occurrence",
                        "label": "Entity label",
                        "description": "Entity description",
                        "properties": {
                            "<propName>": {"type": "string|number|..."}
                        },
                        "relations": {
                            "<relationName>": {"target": "<TargetEntity>", "description": "..."}
                        },
                        "depends_on": [
                            {"role": "...", "entity": "...", "cardinality": "..."}
                        ]
                    }
                }
            }
        """
        config = {"entities": {}}
        
        for entity_name, entity in self.entities.items():
            # Convert properties from list to dict
            properties_dict = {}
            for prop in entity.properties:
                properties_dict[prop.name] = {
                    "type": prop.datatype or "string"
                }
                if prop.description:
                    properties_dict[prop.name]["description"] = prop.description
                if prop.required:
                    properties_dict[prop.name]["required"] = True
            
            # Find relations where this entity is the source (head)
            relations_dict = {}
            for rel_name, relation in self.relations.items():
                if entity_name in relation.head_types:
                    # For each valid target
                    for tail_type in relation.tail_types:
                        relations_dict[rel_name] = {
                            "target": tail_type
                        }
                        if relation.description:
                            relations_dict[rel_name]["description"] = relation.description
                        # Only store first target to keep it simple
                        # (In practice, most relations have single target type)
                        break
            
            # Build entity config
            config["entities"][entity_name] = {
                "kind": entity.kind,
                "label": entity.name,
                "description": entity.description,
                "properties": properties_dict,
                "relations": relations_dict,
                "depends_on": [dep.to_dict() for dep in entity.depends_on]
            }
        
        return config
    
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
    
    def get_dependencies(self, entity_name: str) -> List[Dependency]:
        """Get dependencies for an entity.
        
        Args:
            entity_name: Name of the entity type
            
        Returns:
            List of dependencies (empty if entity is core or has no dependencies)
        """
        entity = self.entities.get(entity_name)
        if entity and entity.kind == "occurrence":
            return entity.depends_on
        return []
    
    def is_occurrence_entity(self, entity_name: str) -> bool:
        """Check if an entity is an occurrence entity.
        
        Args:
            entity_name: Name of the entity type
            
        Returns:
            True if entity is occurrence type, False otherwise
        """
        entity = self.entities.get(entity_name)
        return entity.kind == "occurrence" if entity else False
    
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
            dependencies = [
                Dependency(**dep) for dep in entity_data.get("depends_on", [])
            ]
            entities[name] = EntityType(
                name=entity_data["name"],
                iri=entity_data["iri"],
                description=entity_data["description"],
                kind=entity_data.get("kind", "core"),
                properties=properties,
                examples=entity_data.get("examples", []),
                depends_on=dependencies
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
