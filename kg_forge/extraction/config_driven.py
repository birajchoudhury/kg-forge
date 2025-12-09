"""Config-driven LLM entity extraction.

This module provides a generic LLM-based entity extraction system that uses
entity config JSON to drive the extraction process. It distinguishes between
core entities and occurrence entities, and validates dependencies.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMClient:
    """Abstract LLM client interface."""
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate LLM response.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User message with content to process
            
        Returns:
            Raw LLM response text
        """
        raise NotImplementedError("Subclasses must implement generate()")


def build_system_prompt() -> str:
    """Build the static system prompt template.
    
    This prompt explains to the LLM how to use the entity config JSON
    and what output format to produce.
    
    Returns:
        System prompt string explaining the extraction task
    """
    return """You are an expert entity extraction system. Your task is to extract structured entities from documents according to a provided entity configuration.

**CRITICAL INSTRUCTIONS:**

1. You will receive an ENTITY CONFIG JSON that defines:
   - Entity types with "kind" (core or occurrence)
   - Properties for each entity type
   - Relations between entity types
   - Dependencies (occurrence entities must link to required core entities)

2. You MUST output ONLY valid JSON with this exact structure:
   {
     "core_entities": [
       {
         "entity_id": "unique-id",
         "type": "EntityTypeName",
         "properties": {"propName": "value"},
         "span": {"page": 1, "start_char": 123, "end_char": 145}
       }
     ],
     "occurrence_entities": [
       {
         "entity_id": "unique-id",
         "type": "EntityTypeName",
         "properties": {"propName": "value"},
         "links": {"roleName": "linked-entity-id"},
         "span": {"page": 1, "start_char": 200, "end_char": 250}
       }
     ]
   }

3. CORE ENTITIES:
   - These are entities with kind == "core" in the config
   - They represent primary domain objects (e.g., Contract, Person, Product)
   - They do NOT have "links" field

4. OCCURRENCE ENTITIES:
   - These are entities with kind == "occurrence" in the config
   - They represent events or instances involving core entities
   - They MUST have a "links" field mapping role names to core entity IDs
   - Check "depends_on" in config for required links and cardinality

5. PROPERTIES:
   - Extract property values according to "properties" in the config
   - Use the specified data types (string, number, boolean, date, datetime)
   - Only include properties defined in the config

6. SPAN INFORMATION:
   - For each entity, provide the location in the document
   - "page": page number (1-indexed, or null if not applicable)
   - "start_char": character offset where entity mention starts
   - "end_char": character offset where entity mention ends

7. ENTITY IDs:
   - Create unique IDs for each entity (e.g., "contract-1", "execution-2")
   - Use these IDs consistently in the "links" field

8. VALIDATION:
   - Ensure all occurrence entities have required links (check depends_on cardinality)
   - If cardinality includes "1" (e.g., "1", "1..*"), the link is mandatory
   - Only extract entities whose types are defined in the config

**RESPONSE FORMAT:**
Return ONLY the JSON object. Do NOT include markdown code blocks, explanations, or any other text.
"""


def build_user_prompt(
    entity_config: Dict[str, Any],
    doc_id: str,
    doc_title: str,
    doc_text: str
) -> str:
    """Build the user prompt with entity config and document content.
    
    Args:
        entity_config: Entity configuration JSON
        doc_id: Document identifier
        doc_title: Document title
        doc_text: Full document text
        
    Returns:
        User prompt string with config and document
    """
    config_json = json.dumps(entity_config, indent=2)
    
    prompt = f"""ENTITY CONFIG JSON:

{config_json}

DOCUMENT METADATA:
- Document ID: {doc_id}
- Document Title: {doc_title}

DOCUMENT TEXT:

{doc_text}

Now extract all entities from the document according to the entity config. Remember:
- Separate core entities from occurrence entities based on "kind" field
- Include all required properties
- For occurrence entities, populate "links" with references to core entities
- Validate that required dependencies (cardinality "1" or "1..*") are satisfied
- Provide accurate span information (page, start_char, end_char)

Return ONLY the JSON extraction result.
"""
    
    return prompt


def extract_entities_from_document(
    entity_config: Dict[str, Any],
    doc_id: str,
    doc_title: str,
    doc_text: str,
    llm_client: LLMClient
) -> Dict[str, Any]:
    """Extract entities from document using config-driven LLM extraction.
    
    This is the main entry point for config-driven extraction. It:
    1. Builds prompts from the entity config
    2. Calls the LLM
    3. Parses and validates the response
    4. Returns structured extraction results
    
    Args:
        entity_config: Entity configuration JSON with structure:
            {
              "entities": {
                "<EntityName>": {
                  "kind": "core" | "occurrence",
                  "label": "...",
                  "properties": {"propName": {"type": "..."}},
                  "relations": {"relName": {"target": "..."}},
                  "depends_on": [{"role": "...", "entity": "...", "cardinality": "..."}]
                }
              }
            }
        doc_id: Document identifier
        doc_title: Document title
        doc_text: Full document text content
        llm_client: LLM client implementing generate(system_prompt, user_prompt)
        
    Returns:
        Dictionary with structure:
        {
          "core_entities": [
            {
              "entity_id": "...",
              "type": "...",
              "properties": {...},
              "span": {"page": 1, "start_char": 123, "end_char": 145}
            }
          ],
          "occurrence_entities": [
            {
              "entity_id": "...",
              "type": "...",
              "properties": {...},
              "links": {"role": "linked-entity-id"},
              "span": {"page": 1, "start_char": 200, "end_char": 250}
            }
          ]
        }
        
    Raises:
        ValueError: If entity config is invalid
        json.JSONDecodeError: If LLM response is not valid JSON
        ValidationError: If extracted data doesn't meet config requirements
    """
    logger.info(f"Starting config-driven extraction for document: {doc_id}")
    
    # Step 1: Validate entity config
    _validate_entity_config(entity_config)
    
    # Step 2: Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(entity_config, doc_id, doc_title, doc_text)
    
    logger.debug(f"Built prompts", extra={
        "doc_id": doc_id,
        "system_prompt_length": len(system_prompt),
        "user_prompt_length": len(user_prompt),
        "entity_types_count": len(entity_config.get("entities", {}))
    })
    
    # Step 3: Call LLM
    try:
        response_text = llm_client.generate(system_prompt, user_prompt)
        logger.debug(f"Received LLM response", extra={
            "doc_id": doc_id,
            "response_length": len(response_text)
        })
    except Exception as e:
        logger.error(f"LLM generation failed", extra={
            "doc_id": doc_id,
            "error": str(e)
        })
        raise
    
    # Step 4: Parse JSON response
    try:
        extraction_result = _parse_llm_response(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON", extra={
            "doc_id": doc_id,
            "error": str(e),
            "response_preview": response_text[:500]
        })
        # Try to extract JSON from markdown code blocks
        extraction_result = _extract_json_from_markdown(response_text)
    
    # Step 5: Validate extraction result
    _validate_extraction_result(extraction_result, entity_config)
    
    logger.info(f"Extraction completed successfully", extra={
        "doc_id": doc_id,
        "core_entities": len(extraction_result.get("core_entities", [])),
        "occurrence_entities": len(extraction_result.get("occurrence_entities", []))
    })
    
    return extraction_result


def _validate_entity_config(entity_config: Dict[str, Any]) -> None:
    """Validate that entity config has required structure.
    
    Args:
        entity_config: Entity configuration to validate
        
    Raises:
        ValueError: If config is invalid
    """
    if not isinstance(entity_config, dict):
        raise ValueError("entity_config must be a dictionary")
    
    if "entities" not in entity_config:
        raise ValueError("entity_config must have 'entities' key")
    
    if not isinstance(entity_config["entities"], dict):
        raise ValueError("entity_config['entities'] must be a dictionary")
    
    # Validate each entity type
    for entity_name, entity_def in entity_config["entities"].items():
        if "kind" not in entity_def:
            raise ValueError(f"Entity '{entity_name}' missing 'kind' field")
        
        if entity_def["kind"] not in ["core", "occurrence"]:
            raise ValueError(f"Entity '{entity_name}' has invalid kind: {entity_def['kind']}")


def _parse_llm_response(response_text: str) -> Dict[str, Any]:
    """Parse LLM response as JSON.
    
    Args:
        response_text: Raw LLM response
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        json.JSONDecodeError: If response is not valid JSON
    """
    # Try direct parsing first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        return _extract_json_from_markdown(response_text)


def _extract_json_from_markdown(text: str) -> Dict[str, Any]:
    """Extract JSON from markdown code blocks or other formatting.
    
    Args:
        text: Text that may contain JSON
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    # Try to find JSON between ```json and ``` or ``` and ```
    import re
    
    # Look for markdown code blocks
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(json_block_pattern, text, re.DOTALL)
    
    if matches:
        return json.loads(matches[0])
    
    # Try to find JSON by looking for first { and last }
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_str = text[first_brace:last_brace + 1]
        return json.loads(json_str)
    
    raise json.JSONDecodeError("No valid JSON found in response", text, 0)


def _validate_extraction_result(
    extraction_result: Dict[str, Any],
    entity_config: Dict[str, Any]
) -> None:
    """Validate that extraction result matches expected structure.
    
    Args:
        extraction_result: Parsed extraction result
        entity_config: Entity configuration
        
    Raises:
        ValueError: If result doesn't meet requirements
    """
    # Check required top-level keys
    if "core_entities" not in extraction_result:
        raise ValueError("Extraction result missing 'core_entities' key")
    
    if "occurrence_entities" not in extraction_result:
        raise ValueError("Extraction result missing 'occurrence_entities' key")
    
    # Validate core entities
    for entity in extraction_result["core_entities"]:
        _validate_entity(entity, entity_config, is_occurrence=False)
    
    # Validate occurrence entities
    for entity in extraction_result["occurrence_entities"]:
        _validate_entity(entity, entity_config, is_occurrence=True)
        _validate_dependencies(entity, entity_config, extraction_result["core_entities"])


def _validate_entity(
    entity: Dict[str, Any],
    entity_config: Dict[str, Any],
    is_occurrence: bool
) -> None:
    """Validate a single entity.
    
    Args:
        entity: Entity dictionary
        entity_config: Entity configuration
        is_occurrence: Whether this should be an occurrence entity
        
    Raises:
        ValueError: If entity is invalid
    """
    # Check required fields
    required_fields = ["entity_id", "type", "properties"]
    for field in required_fields:
        if field not in entity:
            raise ValueError(f"Entity missing required field: {field}")
    
    # Check entity type exists in config
    entity_type = entity["type"]
    if entity_type not in entity_config["entities"]:
        raise ValueError(f"Unknown entity type: {entity_type}")
    
    # Check kind matches
    expected_kind = "occurrence" if is_occurrence else "core"
    actual_kind = entity_config["entities"][entity_type].get("kind", "core")
    
    if actual_kind != expected_kind:
        raise ValueError(
            f"Entity '{entity['entity_id']}' has type '{entity_type}' with kind '{actual_kind}' "
            f"but was placed in {expected_kind} entities list"
        )
    
    # Check occurrence entities have links
    if is_occurrence and "links" not in entity:
        raise ValueError(f"Occurrence entity '{entity['entity_id']}' missing 'links' field")


def _validate_dependencies(
    occurrence_entity: Dict[str, Any],
    entity_config: Dict[str, Any],
    core_entities: List[Dict[str, Any]]
) -> None:
    """Validate that occurrence entity satisfies dependency requirements.
    
    Args:
        occurrence_entity: Occurrence entity to validate
        entity_config: Entity configuration
        core_entities: List of extracted core entities
        
    Raises:
        ValueError: If dependencies are not satisfied
    """
    entity_type = occurrence_entity["type"]
    entity_def = entity_config["entities"][entity_type]
    
    # Get dependencies
    dependencies = entity_def.get("depends_on", [])
    links = occurrence_entity.get("links", {})
    
    # Check each dependency
    for dep in dependencies:
        role = dep["role"]
        required_entity_type = dep["entity"]
        cardinality = dep["cardinality"]
        
        # Check if required link exists
        is_required = cardinality in ["1", "1..*"]
        
        if is_required and role not in links:
            raise ValueError(
                f"Occurrence entity '{occurrence_entity['entity_id']}' missing required link "
                f"'{role}' (cardinality: {cardinality})"
            )
        
        # Validate linked entity exists and has correct type
        if role in links:
            linked_id = links[role]
            linked_entity = next(
                (e for e in core_entities if e["entity_id"] == linked_id),
                None
            )
            
            if linked_entity is None:
                raise ValueError(
                    f"Occurrence entity '{occurrence_entity['entity_id']}' links to "
                    f"non-existent entity '{linked_id}'"
                )
            
            if linked_entity["type"] != required_entity_type:
                raise ValueError(
                    f"Occurrence entity '{occurrence_entity['entity_id']}' links to "
                    f"entity '{linked_id}' of type '{linked_entity['type']}' "
                    f"but expected type '{required_entity_type}'"
                )
