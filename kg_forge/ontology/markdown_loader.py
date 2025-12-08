"""Markdown ontology loader (legacy format).

This module implements loading of markdown-based ontology files and converting
them to the normalized OntologySchema representation. This format is supported
for backward compatibility only - new ontologies should use TTL format.
"""

from pathlib import Path
from typing import Dict, List, Optional
import logging

from kg_forge.entities.models import EntityDefinition
from kg_forge.entities.definitions import EntityDefinitionLoader
from .schema import OntologySchema, EntityType, RelationType, Property

logger = logging.getLogger(__name__)


class MarkdownOntologyLoader:
    """Load ontologies from markdown files (legacy format)."""
    
    def load_from_directory(self, entities_dir: Path) -> OntologySchema:
        """Load ontology from markdown files in entities_extract/ directory.
        
        Args:
            entities_dir: Directory containing .md entity definition files
            
        Returns:
            Normalized OntologySchema
        """
        loader = EntityDefinitionLoader()
        logger.info(f"Loading markdown ontology from {entities_dir}")
        
        # Load entity definitions using EntityDefinitionLoader
        entity_defs = loader.load_entity_definitions(entities_dir)
        
        if not entity_defs:
            raise ValueError(f"No entity definitions found in {entities_dir}")
        
        # Convert to OntologySchema
        return self._convert_to_schema(entity_defs)
    
    def _convert_to_schema(self, entity_defs: List[EntityDefinition]) -> OntologySchema:
        """Convert legacy EntityDefinitions to OntologySchema.
        
        Args:
            entity_defs: List of EntityDefinition objects from markdown files
            
        Returns:
            Normalized OntologySchema
        """
        entities = {}
        relations = {}
        
        # First pass: convert entity definitions
        for entity_def in entity_defs:
            entity_type = self._convert_entity(entity_def)
            entities[entity_type.name] = entity_type
        
        # Second pass: extract relations from all entity definitions
        for entity_def in entity_defs:
            source_type = entity_def.id
            
            for relation_def in entity_def.relations:
                # Create relation type if it doesn't exist
                relation_name = relation_def.to_label
                
                if relation_name not in relations:
                    # New relation - create it
                    relations[relation_name] = RelationType(
                        name=relation_name,
                        iri=self._generate_synthetic_iri("relation", relation_name),
                        head_types=[source_type],
                        tail_types=[relation_def.target_type],
                        description=f"Relation from {source_type} to {relation_def.target_type}",
                        properties=[]
                    )
                else:
                    # Existing relation - add source/target types if not present
                    relation = relations[relation_name]
                    if source_type not in relation.head_types:
                        relation.head_types.append(source_type)
                    if relation_def.target_type not in relation.tail_types:
                        relation.tail_types.append(relation_def.target_type)
                
                # Also create reverse relation if specified
                if relation_def.from_label and relation_def.from_label != relation_def.to_label:
                    reverse_name = relation_def.from_label
                    
                    if reverse_name not in relations:
                        relations[reverse_name] = RelationType(
                            name=reverse_name,
                            iri=self._generate_synthetic_iri("relation", reverse_name),
                            head_types=[relation_def.target_type],
                            tail_types=[source_type],
                            description=f"Reverse relation from {relation_def.target_type} to {source_type}",
                            properties=[]
                        )
                    else:
                        relation = relations[reverse_name]
                        if relation_def.target_type not in relation.head_types:
                            relation.head_types.append(relation_def.target_type)
                        if source_type not in relation.tail_types:
                            relation.tail_types.append(source_type)
        
        metadata = {
            "format": "markdown",
            "source": "legacy_markdown_files",
            "entity_count": len(entities),
            "relation_count": len(relations)
        }
        
        logger.info(f"Converted {len(entities)} entity types and {len(relations)} relation types from markdown")
        
        return OntologySchema(
            entities=entities,
            relations=relations,
            metadata=metadata
        )
    
    def _convert_entity(self, entity_def: EntityDefinition) -> EntityType:
        """Convert EntityDefinition to EntityType.
        
        Args:
            entity_def: EntityDefinition from markdown file
            
        Returns:
            Normalized EntityType
        """
        # Extract example titles
        examples = [ex.title for ex in entity_def.examples if ex.title]
        
        # Generate synthetic IRI for backward compatibility
        iri = self._generate_synthetic_iri("entity", entity_def.id)
        
        # Use name if available, otherwise use ID
        name = entity_def.name or entity_def.id
        
        # Use description if available, otherwise generate default
        description = entity_def.description or f"Entity type: {name}"
        
        return EntityType(
            name=entity_def.id,  # Use ID as canonical name
            iri=iri,
            description=description,
            properties=[],  # Markdown format doesn't define explicit properties
            examples=examples
        )
    
    def _generate_synthetic_iri(self, type_name: str, identifier: str) -> str:
        """Generate synthetic IRI for markdown-based entities/relations.
        
        Args:
            type_name: "entity" or "relation"
            identifier: Entity or relation identifier
            
        Returns:
            Synthetic IRI (e.g., "urn:kg-forge:entity:Product")
        """
        return f"urn:kg-forge:{type_name}:{identifier}"
