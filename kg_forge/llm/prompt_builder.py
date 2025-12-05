"""
Prompt builder for LLM extraction.

Constructs prompts by merging entity definitions with templates.
"""
from pathlib import Path
from typing import Dict, Any, List
import logging

from kg_forge.ontology.base import OntologyPack
from kg_forge.entities.definitions import EntityDefinition

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds extraction prompts from ontology and templates."""
    
    def __init__(self, ontology: OntologyPack):
        """Initialize prompt builder with ontology pack.
        
        Args:
            ontology: Active ontology pack with entity definitions
        """
        self.ontology = ontology
    
    def build_extraction_prompt(self, document_content: str, 
                              prompt_template: str = None) -> str:
        """Build complete extraction prompt for document.
        
        Args:
            document_content: Curated text content to extract from
            prompt_template: Optional custom prompt template
        
        Returns:
            Complete prompt string ready for LLM
        """
        # Get the prompt template
        if prompt_template is None:
            prompt_template = self._get_default_template()
        
        # Build entity definitions section
        entity_definitions_text = self._build_entity_definitions_section()
        
        # Replace placeholders in template
        prompt = prompt_template.replace("{{ENTITY_TYPE_DEFINITIONS}}", entity_definitions_text)
        prompt = prompt.replace("{{DOCUMENT_CONTENT}}", document_content)
        
        logger.debug(f"Built extraction prompt: {len(prompt)} characters", extra={
            "definitions_count": len(self.ontology.get_entity_definitions()),
            "document_length": len(document_content)
        })
        
        return prompt
    
    def _get_default_template(self) -> str:
        """Get default extraction prompt template.
        
        Returns:
            Default template string with placeholders
        """
        return """You are an expert entity extraction system. Your task is to identify entities and relationships in technical documentation.

Extract entities and relationships from the provided document according to the entity type definitions below.

**CRITICAL: You must respond with ONLY valid JSON. Do not include any explanatory text, markdown formatting, or commentary before or after the JSON. Your entire response must be parseable JSON.**

**INSTRUCTIONS:**
1. Only extract entities that match the defined types
2. Be precise with entity names - use the exact text from the document
3. Include character offsets (start_offset, end_offset) for each mention
4. For relationships, identify connections between entities based on the schema
5. If no entities are found, return empty arrays
6. Return ONLY the JSON object - no other text

**ENTITY TYPE DEFINITIONS:**

{{ENTITY_TYPE_DEFINITIONS}}

**DOCUMENT CONTENT:**

{{DOCUMENT_CONTENT}}

**REQUIRED OUTPUT FORMAT (return ONLY this JSON, nothing else):**

{
  "entities": [
    {
      "type": "EntityType",
      "name": "Entity Name",
      "start_offset": 123,
      "end_offset": 135,
      "confidence": 0.95,
      "context": "surrounding text for context"
    }
  ],
  "relations": [
    {
      "source_entity": "Entity Name 1",
      "target_entity": "Entity Name 2",
      "relation_type": "RELATION_TYPE",
      "confidence": 0.9,
      "context": "text showing the relationship"
    }
  ]
}"""
    
    def _build_entity_definitions_section(self) -> str:
        """Build the entity definitions section of the prompt.
        
        Returns:
            Formatted entity definitions text
        """
        definitions = self.ontology.get_entity_definitions()
        
        if not definitions:
            return "No entity types defined."
        
        sections = []
        
        for definition in definitions:
            section = self._format_entity_definition(definition)
            sections.append(section)
        
        return "\n\n".join(sections)
    
    def _format_entity_definition(self, definition: EntityDefinition) -> str:
        """Format a single entity definition for the prompt.
        
        Args:
            definition: Entity definition to format
        
        Returns:
            Formatted definition text
        """
        lines = [f"## {definition.name or definition.entity_id}"]
        
        if definition.description:
            lines.append(f"**Description:** {definition.description}")
        
        # Add relations if defined
        if definition.relations:
            lines.append("**Relationships:**")
            for relation in definition.relations:
                lines.append(f"- Can have {relation.to_label} relationship with {relation.target_type}")
        
        # Add examples if available
        if definition.examples:
            lines.append("**Examples:**")
            for example in definition.examples:
                if example.title:
                    lines.append(f"- {example.title}")
                    if example.description:
                        lines.append(f"  {example.description}")
        
        return "\n".join(lines)
    
    def build_validation_prompt(self, extracted_data: Dict[str, Any]) -> str:
        """Build a prompt to validate extracted data.
        
        Args:
            extracted_data: Previously extracted entities and relations
        
        Returns:
            Validation prompt string
        """
        return f"""Please validate the following extracted entities and relationships.

Check for:
1. Entity types match the defined ontology
2. Relationship types are valid for the connected entity types  
3. Entity names are precise and correctly extracted
4. No duplicate entities or relationships

EXTRACTED DATA:
{extracted_data}

ONTOLOGY DEFINITIONS:
{self._build_entity_definitions_section()}

Return validation results in JSON format:
{{
  "valid": true/false,
  "errors": ["list of validation errors"],
  "suggestions": ["list of improvement suggestions"]
}}
"""
    
    def get_available_entity_types(self) -> List[str]:
        """Get list of available entity types from ontology.
        
        Returns:
            List of entity type identifiers
        """
        definitions = self.ontology.get_entity_definitions()
        return [defn.entity_id for defn in definitions]
    
    def get_available_relation_types(self) -> List[str]:
        """Get list of available relation types from ontology.
        
        Returns:
            List of relation type identifiers
        """
        relation_types = set()
        definitions = self.ontology.get_entity_definitions()
        
        for definition in definitions:
            if definition.relations:
                for relation in definition.relations:
                    relation_types.add(relation.to_label)
        
        return list(relation_types)
    
    def estimate_prompt_tokens(self, document_content: str) -> int:
        """Estimate number of tokens in the complete prompt.
        
        Args:
            document_content: Document content to include
        
        Returns:
            Estimated token count (rough approximation)
        """
        prompt = self.build_extraction_prompt(document_content)
        
        # Rough approximation: 4 characters = 1 token
        estimated_tokens = len(prompt) // 4
        
        return estimated_tokens