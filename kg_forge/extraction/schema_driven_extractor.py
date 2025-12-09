"""
Schema-driven entity extraction using LLM.

This module implements a generic extraction pipeline that:
- Takes an entity configuration derived from an ontology
- Builds system and user prompts for the LLM
- Parses and validates the LLM's JSON response
- Returns structured entities with properties and links
"""
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LLMClient:
    """Abstract interface for LLM clients."""
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response from the LLM.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User message with task details
            
        Returns:
            LLM response as string
        """
        raise NotImplementedError("Subclasses must implement generate()")


def build_system_prompt() -> str:
    """Build the system prompt for schema-driven extraction.
    
    Returns:
        System prompt string instructing the LLM how to extract entities
    """
    return """You are an expert entity extraction system. You will receive:
1. An ENTITY CONFIG JSON that defines the entity types, their properties, and relationships
2. A DOCUMENT TEXT from which to extract entities

Your task is to extract entity instances from the document according to the entity configuration.

ENTITY CONFIG STRUCTURE:
The entity_config contains an "entities" object where each key is an entity type name with:
- "kind": either "core" (independent entities) or "occurrence" (entities that depend on core entities)
- "label": human-readable description
- "properties": object defining property names and their types (string, number, boolean, date, datetime, other)
- "relations": object defining named relationships to other entity types
- "depends_on": array of dependency specifications (only for occurrence entities), each with:
    * "role": the name of the dependency relationship
    * "entity": the target entity type name
    * "cardinality": "1" (required one), "0..1" (optional one), "1..*" (required many), "0..*" (optional many)

OUTPUT FORMAT:
You MUST respond with ONLY a valid JSON object with this exact structure:

{
  "core_entities": [
    {
      "entity_id": "unique_string_id",
      "type": "EntityTypeName",
      "properties": {
        "propertyName": value_or_null
      },
      "span": {
        "start_offset": integer_or_null,
        "end_offset": integer_or_null
      }
    }
  ],
  "occurrence_entities": [
    {
      "entity_id": "unique_string_id",
      "type": "EntityTypeName",
      "properties": {
        "propertyName": value_or_null
      },
      "links": {
        "roleName": "entity_id_of_related_core_entity"
      },
      "span": {
        "start_offset": integer_or_null,
        "end_offset": integer_or_null
      }
    }
  ]
}

CRITICAL RULES:
1. Output ONLY the JSON object - no markdown code blocks, no explanations, no preamble
2. Use ONLY entity type names that appear in the entity_config["entities"]
3. Do NOT create entities of meta-types like "CoreEntity" or "OccurrenceEntity"
4. Only use properties defined in the entity_config for each entity type
5. For occurrence entities, populate "links" with the dependency roles defined in "depends_on"
6. If a dependency has cardinality "1" or "1..*", the corresponding role MUST be present in "links"
7. If a dependency has cardinality "0..1" or "0..*", the role is optional in "links"
8. Each entity_id must be unique within the document
9. The span offsets are character positions in the document text (0-indexed)
10. If you cannot determine span offsets, use null for both start_offset and end_offset
11. If no entities are found, return: {"core_entities": [], "occurrence_entities": []}
12. All property values should match their declared types or be null if not found

EXTRACTION STRATEGY:
1. Read the entity_config carefully to understand what to extract
2. Scan the document text for instances of each entity type
3. Extract property values from the document for each entity
4. For occurrence entities, identify which core entities they link to via the dependency roles
5. Ensure all required dependencies (cardinality "1" or "1..*") are satisfied
6. Generate unique entity_id values (e.g., "contract_1", "signature_event_1")
7. Calculate span offsets if possible based on where text appears in the document

Remember: Your response must be valid, parseable JSON with no additional text."""


def build_user_prompt(
    entity_config: Dict[str, Any],
    doc_id: str,
    doc_title: str,
    doc_text: str
) -> str:
    """Build the user prompt with entity config and document.
    
    Args:
        entity_config: Entity configuration dictionary
        doc_id: Document identifier
        doc_title: Document title
        doc_text: Full document text
        
    Returns:
        User prompt string
    """
    entity_config_json = json.dumps(entity_config, indent=2)
    
    return f"""ENTITY CONFIG JSON:
{entity_config_json}

DOCUMENT METADATA:
- doc_id: {doc_id}
- doc_title: {doc_title}

DOCUMENT TEXT:
{doc_text}

Now extract all core and occurrence entities according to the ENTITY CONFIG.
Remember to follow the output JSON shape specified in the system prompt
and respond with ONLY valid JSON."""


def _parse_json_response(response_text: str) -> Dict[str, Any]:
    """Parse JSON from LLM response, handling common formatting issues.
    
    Args:
        response_text: Raw LLM response
        
    Returns:
        Parsed JSON object
        
    Raises:
        ValueError: If JSON cannot be parsed
    """
    # Try direct parsing first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks or other text
    response_text = response_text.strip()
    
    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        lines = response_text.split('\n')
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = '\n'.join(lines).strip()
    
    # Try parsing again
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Last resort: find first { and last }
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    
    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        raise ValueError(
            f"Could not find valid JSON object in response. "
            f"Response started with: {response_text[:100]}"
        )
    
    json_substring = response_text[start_idx:end_idx + 1]
    try:
        return json.loads(json_substring)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON from LLM response: {e}. "
            f"Extracted substring: {json_substring[:200]}"
        )


def _normalize_entity(
    entity: Dict[str, Any],
    entity_type_config: Dict[str, Any],
    is_occurrence: bool
) -> Dict[str, Any]:
    """Normalize and validate a single entity.
    
    Args:
        entity: Raw entity dict from LLM
        entity_type_config: Configuration for this entity type
        is_occurrence: Whether this is an occurrence entity
        
    Returns:
        Normalized entity dict
        
    Raises:
        ValueError: If entity is invalid
    """
    # Validate entity_id
    if "entity_id" not in entity or not entity["entity_id"]:
        raise ValueError(f"Entity missing required 'entity_id': {entity}")
    
    # Ensure properties exists
    if "properties" not in entity:
        entity["properties"] = {}
    elif not isinstance(entity["properties"], dict):
        raise ValueError(f"Entity properties must be a dict: {entity}")
    
    # Ensure span exists
    if "span" not in entity or not isinstance(entity["span"], dict):
        entity["span"] = {"start_offset": None, "end_offset": None}
    else:
        # Ensure span has required keys
        if "start_offset" not in entity["span"]:
            entity["span"]["start_offset"] = None
        if "end_offset" not in entity["span"]:
            entity["span"]["end_offset"] = None
    
    # Filter properties to only those defined in config
    defined_properties = entity_type_config.get("properties", {})
    filtered_properties = {
        k: v for k, v in entity["properties"].items()
        if k in defined_properties
    }
    entity["properties"] = filtered_properties
    
    # For occurrence entities, validate links
    if is_occurrence:
        if "links" not in entity:
            entity["links"] = {}
        elif not isinstance(entity["links"], dict):
            raise ValueError(f"Occurrence entity links must be a dict: {entity}")
        
        # Check required dependencies
        depends_on = entity_type_config.get("depends_on", [])
        for dep in depends_on:
            role = dep["role"]
            cardinality = dep.get("cardinality", "0..1")
            
            # If cardinality requires the link, validate it exists
            if cardinality in ["1", "1..*"]:
                if role not in entity["links"] or not entity["links"][role]:
                    raise ValueError(
                        f"Occurrence entity type '{entity['type']}' requires "
                        f"link '{role}' (cardinality: {cardinality}), but it's missing "
                        f"in entity: {entity['entity_id']}"
                    )
    
    return entity


def _normalize_entities(
    entities: List[Dict[str, Any]],
    entity_config: Dict[str, Any],
    is_occurrence: bool
) -> List[Dict[str, Any]]:
    """Normalize and validate a list of entities.
    
    Args:
        entities: List of raw entity dicts from LLM
        entity_config: Full entity configuration
        is_occurrence: Whether these are occurrence entities
        
    Returns:
        List of normalized and validated entities
    """
    normalized = []
    entity_types = entity_config.get("entities", {})
    
    for entity in entities:
        # Validate type exists
        entity_type = entity.get("type")
        if not entity_type:
            logger.warning(f"Skipping entity without type: {entity}")
            continue
        
        if entity_type not in entity_types:
            logger.warning(
                f"Skipping entity with unknown type '{entity_type}'. "
                f"Available types: {list(entity_types.keys())}"
            )
            continue
        
        # Get type configuration
        type_config = entity_types[entity_type]
        
        # Skip meta-types like CoreEntity or OccurrenceEntity
        if entity_type in ["CoreEntity", "OccurrenceEntity"]:
            logger.warning(f"Skipping meta-type entity: {entity_type}")
            continue
        
        # Verify kind matches expectation
        expected_kind = "occurrence" if is_occurrence else "core"
        actual_kind = type_config.get("kind", "core")
        if actual_kind != expected_kind:
            logger.warning(
                f"Entity type '{entity_type}' has kind '{actual_kind}' but was "
                f"placed in '{expected_kind}_entities'. Moving to correct list."
            )
            # Still normalize it - caller can move it to the right list
        
        try:
            normalized_entity = _normalize_entity(entity, type_config, is_occurrence)
            normalized.append(normalized_entity)
        except ValueError as e:
            logger.error(f"Failed to normalize entity: {e}")
            # Skip invalid entities rather than failing the whole extraction
            continue
    
    return normalized


def extract_entities_from_document(
    entity_config: Dict[str, Any],
    doc_id: str,
    doc_title: str,
    doc_text: str,
    llm_client: LLMClient
) -> Dict[str, Any]:
    """Extract entities from document using LLM and entity configuration.
    
    Args:
        entity_config: Entity configuration dictionary with entity types,
            properties, and dependencies
        doc_id: Document identifier
        doc_title: Document title
        doc_text: Full document text
        llm_client: LLM client for generation
        
    Returns:
        Dictionary with 'core_entities' and 'occurrence_entities' lists
        
    Raises:
        ValueError: If LLM response cannot be parsed or validated
    """
    # Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(entity_config, doc_id, doc_title, doc_text)
    
    # Call LLM
    logger.debug(f"Calling LLM for entity extraction from document: {doc_id}")
    response_text = llm_client.generate(system_prompt, user_prompt)
    
    # Parse JSON response
    try:
        data = _parse_json_response(response_text)
    except ValueError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise
    
    # Validate response structure
    if not isinstance(data, dict):
        raise ValueError(f"LLM response must be a dict, got: {type(data)}")
    
    if "core_entities" not in data or "occurrence_entities" not in data:
        raise ValueError(
            f"LLM response must have 'core_entities' and 'occurrence_entities' keys. "
            f"Got keys: {list(data.keys())}"
        )
    
    if not isinstance(data["core_entities"], list):
        raise ValueError(
            f"'core_entities' must be a list, got: {type(data['core_entities'])}"
        )
    
    if not isinstance(data["occurrence_entities"], list):
        raise ValueError(
            f"'occurrence_entities' must be a list, got: {type(data['occurrence_entities'])}"
        )
    
    # Normalize and validate entities
    normalized_core = _normalize_entities(
        data["core_entities"],
        entity_config,
        is_occurrence=False
    )
    
    normalized_occurrence = _normalize_entities(
        data["occurrence_entities"],
        entity_config,
        is_occurrence=True
    )
    
    # Check if any entities were misclassified and move them
    entity_types = entity_config.get("entities", {})
    
    # Move core entities that should be occurrences
    core_to_move = []
    for entity in normalized_core:
        entity_type = entity["type"]
        if entity_types.get(entity_type, {}).get("kind") == "occurrence":
            core_to_move.append(entity)
    
    for entity in core_to_move:
        normalized_core.remove(entity)
        # Re-normalize as occurrence
        entity_type_config = entity_types[entity["type"]]
        try:
            renormalized = _normalize_entity(entity, entity_type_config, is_occurrence=True)
            normalized_occurrence.append(renormalized)
        except ValueError as e:
            logger.error(f"Failed to move misclassified entity: {e}")
    
    # Move occurrence entities that should be core
    occurrence_to_move = []
    for entity in normalized_occurrence:
        entity_type = entity["type"]
        if entity_types.get(entity_type, {}).get("kind") == "core":
            occurrence_to_move.append(entity)
    
    for entity in occurrence_to_move:
        normalized_occurrence.remove(entity)
        # Re-normalize as core (remove links)
        if "links" in entity:
            del entity["links"]
        entity_type_config = entity_types[entity["type"]]
        try:
            renormalized = _normalize_entity(entity, entity_type_config, is_occurrence=False)
            normalized_core.append(renormalized)
        except ValueError as e:
            logger.error(f"Failed to move misclassified entity: {e}")
    
    logger.info(
        f"Extracted {len(normalized_core)} core entities and "
        f"{len(normalized_occurrence)} occurrence entities from {doc_id}"
    )
    
    return {
        "core_entities": normalized_core,
        "occurrence_entities": normalized_occurrence,
    }
